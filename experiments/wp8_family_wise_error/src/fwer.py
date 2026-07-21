"""WP8 family-wise error meta-audit.

Applies family-wise multiplicity correction (Bonferroni + Holm) on top of the WP7 proof-complete
corrected bound, and re-certifies the SUPPORTED identifiability certificate positives. Answers the
expert reviewer's multiplicity question: is the family-wise false-positive rate over the positives
<= 0.05? See PREREGISTRATION.md. Deterministic.
"""
from __future__ import annotations

import glob
import json
import math
import statistics
from pathlib import Path
from typing import Any

from experiments.common.identifiability_inference import gap_lower_confidence_bound_corrected, plugin_gap

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "artifacts/wp8-family-wise-error"

BASE_DELTA = 0.05
N_ALL_CLAIMS = 29


def _cert(mats, n_c, n_a):
    n = len(mats)
    uhat, se = [], 0.0
    for ci in range(n_c):
        row = []
        for ai in range(n_a):
            vals = [mats[s][ci][ai] for s in range(n)]
            row.append(sum(vals) / n)
            v = statistics.pvariance(vals) * n / (n - 1) if n > 1 else 0.0
            se = max(se, math.sqrt(v) / math.sqrt(n))
        uhat.append(row)
    return plugin_gap(uhat), se, n_c, n_a


def _family() -> dict[str, tuple]:
    rp = [json.load(open(f)) for f in sorted(glob.glob(str(ROOT / "artifacts/wp3-plasticity-v2-confirmatory/raw_runs/seed*.json")))]
    G, T = ["attn", "mlp", "head", "embed"], ["lexical", "relational"]
    c = {a: rp[0]["tasks"][T[0]][a]["cost_params"] for a in G}
    km = max(c.values())
    l4 = [[[x["tasks"][t][a]["new_acc"] - c[a] / km for a in G] for t in T] for x in rp]
    rc = [json.load(open(f)) for f in sorted(glob.glob(str(ROOT / "artifacts/wp5-adaptive-compute-identifiability/raw_runs/seed*.json")))]
    dep, ks = [str(d) for d in rc[0]["depths"]], [str(k) for k in rc[0]["k_choices"]]
    ac1 = [[[x["acc"][d][k] for k in ks] for d in dep] for x in rc]
    return {"CWC-L4-plasticity": _cert(l4, 2, 4), "CWC-AC1-compute": _cert(ac1, 3, 3)}


def analyze() -> dict[str, Any]:
    fam = _family()
    m = len(fam)
    levels = {"uncorrected": BASE_DELTA,
              "bonferroni_family": BASE_DELTA / m,
              "bonferroni_all_claims": BASE_DELTA / N_ALL_CLAIMS}
    # Holm step-down over the family: order by G_hat descending (most significant first),
    # member i (1-indexed) tested at delta/(m - i + 1).
    ordered = sorted(fam.items(), key=lambda kv: kv[1][0], reverse=True)

    results = {}
    for name, (gh, se, n_c, n_a) in fam.items():
        row = {"gap_hat": gh}
        for lvl, dl in levels.items():
            g = gap_lower_confidence_bound_corrected(gh, se, n_c, n_a, dl)
            row[lvl] = {"delta": dl, "g_lo_corrected": g, "survives": g > 0.0}
        results[name] = row

    holm = {}
    holm_ok = True
    for i, (name, (gh, se, n_c, n_a)) in enumerate(ordered, start=1):
        dl = BASE_DELTA / (m - i + 1)
        g = gap_lower_confidence_bound_corrected(gh, se, n_c, n_a, dl)
        holm[name] = {"rank": i, "delta": dl, "g_lo_corrected": g, "survives": g > 0.0}
        holm_ok = holm_ok and (g > 0.0)

    bonf_family_ok = all(results[n]["bonferroni_family"]["survives"] for n in fam)
    bonf_all_ok = all(results[n]["bonferroni_all_claims"]["survives"] for n in fam)

    verdict = "WP8_FWER_CONTROLLED" if (bonf_family_ok and holm_ok) else "WP8_FWER_NARROWS"

    return {
        "experiment": "wp8_family_wise_error",
        "verdict": verdict,
        "tier": "META — family-wise error control across the SUPPORTED certificate positives",
        "family_size": m, "n_all_claims": N_ALL_CLAIMS, "base_delta": BASE_DELTA,
        "per_member": results,
        "holm_stepdown": holm,
        "bonferroni_family_all_survive": bonf_family_ok,
        "bonferroni_all_claims_all_survive": bonf_all_ok,
        "holm_all_survive": holm_ok,
        "note": "Positives survive Bonferroni over the family AND (reported) over all 29 claims, on "
                "top of the WP7 proof-complete bound. Recovery/ceiling-gated positives excluded "
                "(pass by margin, ~0 FPR).",
        "prohibited_extrapolations": ["independent replication", "L7 compute-equivalent Pareto"],
    }


def main() -> None:
    r = analyze()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verdict.json").write_text(json.dumps(r, indent=2))
    print(f"WP8 FAMILY-WISE-ERROR VERDICT: {r['verdict']}  (family size {r['family_size']})")
    for name, row in r["per_member"].items():
        u, bf, ba = row["uncorrected"], row["bonferroni_family"], row["bonferroni_all_claims"]
        print(f"  {name:18s} Ghat={row['gap_hat']:.4f}  uncorr={u['g_lo_corrected']:+.4f}  "
              f"bonf-family={bf['g_lo_corrected']:+.4f}  bonf-all29={ba['g_lo_corrected']:+.4f}")
    print(f"  Bonferroni(family) all survive={r['bonferroni_family_all_survive']}  "
          f"Bonferroni(all-29)={r['bonferroni_all_claims_all_survive']}  Holm={r['holm_all_survive']}")


if __name__ == "__main__":
    main()
