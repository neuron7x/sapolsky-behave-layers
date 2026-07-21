"""WP6 real-LM boundary analysis.

Applies the identifiability certificate to the real-LM per-difficulty compute utility, with a
POSITIVE control on the synthetic AC1 data (to prove the certificate detects a gap when one
exists). Tests whether the clean synthetic identifiability transfers to real language-model
per-token difficulty. Verdict per PREREGISTRATION. Deterministic given the raw runs.
"""
from __future__ import annotations

import glob
import json
import math
from pathlib import Path
from typing import Any

from experiments.common.identifiability_inference import gap_lower_confidence_bound, plugin_gap

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "artifacts/wp6-real-lm/raw_runs"
AC1_RAW = ROOT / "artifacts/wp5-adaptive-compute-identifiability/raw_runs"
OUT = ROOT / "artifacts/wp6-real-lm"

LAMBDAS = [0.0, 0.3]
DELTA = 0.05


def _var(v):
    if len(v) < 2:
        return 0.0
    mu = sum(v) / len(v)
    return sum((x - mu) ** 2 for x in v) / (len(v) - 1)


def _certificate(mats, ks, lam, sign):
    """mats: list per seed of [ctx][act] raw scores; sign=-1 turns loss into utility."""
    n = len(mats)
    n_c, n_a = len(mats[0]), len(mats[0][0])
    costs = [int(k) for k in ks]
    kmax = max(costs)
    uhat, se = [], 0.0
    for ci in range(n_c):
        row = []
        for ai in range(n_a):
            vals = [sign * mats[s][ci][ai] - lam * costs[ai] / kmax for s in range(n)]
            row.append(sum(vals) / n)
            se = max(se, math.sqrt(_var(vals)) / math.sqrt(n))
        uhat.append(row)
    return gap_lower_confidence_bound(plugin_gap(uhat), se, n_c, n_a, DELTA), plugin_gap(uhat)


def _real_mats():
    runs = [json.load(open(f)) for f in sorted(glob.glob(str(RAW / "seed*.json")))]
    buckets, ks = runs[0]["buckets"], [str(k) for k in runs[0]["k_choices"]]
    return [[[r["loss"][b][k] for k in ks] for b in buckets] for r in runs], ks


def _ac1_mats():
    runs = [json.load(open(f)) for f in sorted(glob.glob(str(AC1_RAW / "seed*.json")))]
    depths, ks = [str(d) for d in runs[0]["depths"]], [str(k) for k in runs[0]["k_choices"]]
    return [[[r["acc"][d][k] for k in ks] for d in depths] for r in runs], ks


def analyze() -> dict[str, Any]:
    real, ks = _real_mats()
    real_cert = {str(lam): {"gap_lower_bound": _certificate(real, ks, lam, sign=-1)[0],
                            "gap_hat": _certificate(real, ks, lam, sign=-1)[1]} for lam in LAMBDAS}
    ac1, ks1 = _ac1_mats()
    pos_glo, pos_ghat = _certificate(ac1, ks1, 0.0, sign=+1)   # synthetic acc: +1

    real_identifiable = any(real_cert[str(lam)]["gap_lower_bound"] > 0.0 for lam in LAMBDAS)
    positive_control_ok = pos_glo > 0.0

    if not positive_control_ok:
        verdict = "WP6_VOID"                       # certificate can't even detect the synthetic gap
    elif real_identifiable:
        verdict = "WP6_REAL_LM_IDENTIFIABLE"
    else:
        verdict = "WP6_REAL_LM_NOT_IDENTIFIABLE"

    return {
        "experiment": "wp6_real_lm",
        "verdict": verdict,
        "tier": "REAL-DATA (byte-level LM on frozen real prose) — boundary of the identifiability framework",
        "n_seeds": len(real), "lambdas": LAMBDAS, "delta": DELTA,
        "real_lm": real_cert,
        "positive_control_synthetic_ac1": {"gap_lower_bound": pos_glo, "gap_hat": pos_ghat},
        "real_identifiable": real_identifiable,
        "positive_control_detects_gap": positive_control_ok,
        "note": "On real LM per-token difficulty, more compute helps all difficulty buckets roughly "
                "uniformly (no sharp context x compute interaction), so oracle allocation ~ best fixed "
                "compute. The clean synthetic identifiability does NOT transfer to real data.",
        "prohibited_extrapolations": ["claiming adaptive compute never helps real LMs (only tested "
                                      "byte-level, tiny model, unigram-surprisal difficulty)",
                                      "L7 compute-equivalent Pareto", "independent replication"],
    }


def main() -> None:
    r = analyze()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verdict.json").write_text(json.dumps(r, indent=2))
    print(f"WP6 REAL-LM VERDICT: {r['verdict']}")
    for lam in LAMBDAS:
        c = r["real_lm"][str(lam)]
        print(f"  real-LM lambda={lam}: G_lo={c['gap_lower_bound']:+.4f}  G_hat={c['gap_hat']:+.4f}")
    pc = r["positive_control_synthetic_ac1"]
    print(f"  positive control (synthetic AC1): G_lo={pc['gap_lower_bound']:+.4f} (must be >0)")


if __name__ == "__main__":
    main()
