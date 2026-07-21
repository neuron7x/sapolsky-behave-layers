"""WP5 adaptive-compute identifiability analysis.

Applies the identifiability certificate to the compute-budget utility U_lambda[d][K] over the
trained seeds, with a monotone-compute null and an additive null. Verdict per PREREGISTRATION.
Deterministic given the raw runs.
"""
from __future__ import annotations

import glob
import json
import math
from pathlib import Path
from typing import Any

from experiments.common.identifiability_inference import gap_lower_confidence_bound, plugin_gap

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "artifacts/wp5-adaptive-compute-identifiability/raw_runs"
OUT = ROOT / "artifacts/wp5-adaptive-compute-identifiability"

LAMBDAS = [0.0, 0.5, 1.0]
DELTA = 0.05


def _runs() -> list[dict[str, Any]]:
    return [json.load(open(f)) for f in sorted(glob.glob(str(RAW / "seed*.json")))]


def _depths_ks(runs):
    return [str(d) for d in runs[0]["depths"]], [str(k) for k in runs[0]["k_choices"]]


def _acc_matrix(run, depths, ks):
    return [[run["acc"][d][k] for k in ks] for d in depths]


def _apply(acc, kind, ks):
    if kind == "real":
        return acc
    if kind == "monotone":
        out = []
        for row in acc:
            best = -1e9
            newrow = []
            for v in row:                       # cumulative max over K (more compute never hurts)
                best = max(best, v)
                newrow.append(best)
            out.append(newrow)
        return out
    if kind == "additive":
        n_c, n_a = len(acc), len(acc[0])
        grand = sum(acc[c][a] for c in range(n_c) for a in range(n_a)) / (n_c * n_a)
        row = [sum(acc[c]) / n_a for c in range(n_c)]
        col = [sum(acc[c][a] for c in range(n_c)) / n_c for a in range(n_a)]
        return [[row[c] + col[a] - grand for a in range(n_a)] for c in range(n_c)]
    raise ValueError(kind)


def _var(v):
    if len(v) < 2:
        return 0.0
    mu = sum(v) / len(v)
    return sum((x - mu) ** 2 for x in v) / (len(v) - 1)


def _certificate(mats, lam, ks):
    n = len(mats)
    n_c, n_a = len(mats[0]), len(mats[0][0])
    costs = [int(k) for k in ks]
    kmax = max(costs)
    uhat, se = [], 0.0
    for ci in range(n_c):
        row = []
        for ai in range(n_a):
            vals = [mats[s][ci][ai] - lam * costs[ai] / kmax for s in range(n)]
            row.append(sum(vals) / n)
            se = max(se, math.sqrt(_var(vals)) / math.sqrt(n))
        uhat.append(row)
    ghat = plugin_gap(uhat)
    return gap_lower_confidence_bound(ghat, se, n_c, n_a, DELTA), ghat


def analyze() -> dict[str, Any]:
    runs = _runs()
    depths, ks = _depths_ks(runs)
    real = [_acc_matrix(r, depths, ks) for r in runs]

    # diagonal check (mechanism is real)
    diag = [min(r["acc"][d][d] for d in depths) for r in runs]
    offdiag = [max(r["acc"][d][k] for d in depths for k in ks if d != k) for r in runs]
    diagonal_ok = min(diag) >= 0.9 and max(offdiag) <= 0.3

    def cert_for(kind):
        mats = [_apply(m, kind, ks) for m in real]
        return {str(lam): {"gap_lower_bound": _certificate(mats, lam, ks)[0],
                           "gap_hat": _certificate(mats, lam, ks)[1]} for lam in LAMBDAS}

    real_c = cert_for("real")
    mono_c = cert_for("monotone")
    add_c = cert_for("additive")

    real_identifiable = all(real_c[str(lam)]["gap_lower_bound"] > 0.0 for lam in LAMBDAS)
    nulls_vanish = (mono_c["0.0"]["gap_lower_bound"] <= 0.0) and (add_c["0.0"]["gap_lower_bound"] <= 0.0)

    if not diagonal_ok or not nulls_vanish:
        verdict = "AC1_VOID" if (not diagonal_ok or not nulls_vanish) else "AC1_NOT_IDENTIFIABLE"
        if diagonal_ok and not real_identifiable and nulls_vanish:
            verdict = "AC1_NOT_IDENTIFIABLE"
    elif real_identifiable:
        verdict = "AC1_IDENTIFIABLE"
    else:
        verdict = "AC1_NOT_IDENTIFIABLE"

    return {
        "experiment": "wp5_adaptive_compute",
        "verdict": verdict,
        "tier": "SYNTHETIC — second real mechanism (adaptive compute), identifiability",
        "n_seeds": len(runs), "lambdas": LAMBDAS, "delta": DELTA,
        "diagonal_ok": diagonal_ok, "worst_diagonal": min(diag), "worst_offdiagonal": max(offdiag),
        "real": real_c, "monotone_null": mono_c, "additive_null": add_c,
        "real_identifiable_all_lambda": real_identifiable,
        "nulls_vanish": nulls_vanish,
        "prohibited_extrapolations": ["learned compute-controller (follow-up)", "real-workload",
                                      "L7 compute-equivalent Pareto", "independent replication"],
    }


def main() -> None:
    r = analyze()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verdict.json").write_text(json.dumps(r, indent=2))
    print(f"WP5 ADAPTIVE-COMPUTE VERDICT: {r['verdict']}")
    print(f"  diagonal_ok={r['diagonal_ok']} (worst diag {r['worst_diagonal']:.3f}, "
          f"worst off-diag {r['worst_offdiagonal']:.3f})")
    for lam in LAMBDAS:
        print(f"  lambda={lam}:  real G_lo={r['real'][str(lam)]['gap_lower_bound']:+.4f}  "
              f"monotone-null={r['monotone_null'][str(lam)]['gap_lower_bound']:+.4f}  "
              f"additive-null={r['additive_null'][str(lam)]['gap_lower_bound']:+.4f}")


if __name__ == "__main__":
    main()
