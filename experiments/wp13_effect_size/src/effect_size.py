"""WP13 effect sizes, bootstrap CIs, and retrospective power for the positives.

Goes beyond the one-sided G_lo>0 gate: reports the oracle-gap effect size with a seed-bootstrap
95% CI, a standardized effect, and the sample-complexity/power for each certificate positive. See
PREREGISTRATION.md. Deterministic (seeded bootstrap).
"""
from __future__ import annotations

import glob
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any

from experiments.common.identifiability_inference import plugin_gap, sample_complexity

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "artifacts/wp13-effect-size"
N_BOOT = 2000
DELTA = 0.05


def _agg_gap(per_seed):
    n = len(per_seed)
    n_c, n_a = len(per_seed[0]), len(per_seed[0][0])
    uhat = [[sum(per_seed[s][ci][ai] for s in range(n)) / n for ai in range(n_a)] for ci in range(n_c)]
    return plugin_gap(uhat)


def _sigma_max(per_seed):
    n = len(per_seed)
    n_c, n_a = len(per_seed[0]), len(per_seed[0][0])
    sm = 0.0
    for ci in range(n_c):
        for ai in range(n_a):
            vals = [per_seed[s][ci][ai] for s in range(n)]
            sm = max(sm, math.sqrt(statistics.pvariance(vals) * n / (n - 1)) if n > 1 else 0.0)
    return sm


def _bootstrap_ci(per_seed, seed):
    rng = random.Random(seed)
    n = len(per_seed)
    gaps = []
    for _ in range(N_BOOT):
        idx = [rng.randrange(n) for _ in range(n)]
        gaps.append(_agg_gap([per_seed[i] for i in idx]))
    gaps.sort()
    lo = gaps[int(0.025 * N_BOOT)]
    hi = gaps[int(0.975 * N_BOOT)]
    return lo, hi


def _l4():
    rp = [json.load(open(f)) for f in sorted(glob.glob(str(ROOT / "artifacts/wp3-plasticity-v2-confirmatory/raw_runs/seed*.json")))]
    G, T = ["attn", "mlp", "head", "embed"], ["lexical", "relational"]
    c = {a: rp[0]["tasks"][T[0]][a]["cost_params"] for a in G}
    km = max(c.values())
    return [[[x["tasks"][t][a]["new_acc"] - c[a] / km for a in G] for t in T] for x in rp], 2, 4


def _ac1():
    rc = [json.load(open(f)) for f in sorted(glob.glob(str(ROOT / "artifacts/wp5-adaptive-compute-identifiability/raw_runs/seed*.json")))]
    dep, ks = [str(d) for d in rc[0]["depths"]], [str(k) for k in rc[0]["k_choices"]]
    return [[[x["acc"][d][k] for k in ks] for d in dep] for x in rc], 3, 3


def _member(name, per_seed, n_c, n_a, seed):
    gh = _agg_gap(per_seed)
    sig = _sigma_max(per_seed)
    lo, hi = _bootstrap_ci(per_seed, seed)
    nstar = sample_complexity(gh, sig, n_c, n_a, DELTA) if gh > 0 and sig > 0 else None
    return {"claim": name, "n_seeds": len(per_seed), "effect_gap": gh,
            "bootstrap_ci95": [lo, hi], "ci_lower_positive": lo > 0.0,
            "sigma_max": sig, "standardized_effect": (gh / sig if sig > 1e-9 else float("inf")),
            "sample_complexity_nstar": nstar, "n_exceeds_nstar": (nstar is not None and len(per_seed) >= nstar)}


def analyze() -> dict[str, Any]:
    l4, l4c, l4a = _l4()
    ac1, ac1c, ac1a = _ac1()
    members = [_member("CWC-L4-plasticity", l4, l4c, l4a, 101),
               _member("CWC-AC1-compute", ac1, ac1c, ac1a, 202)]
    all_ci_positive = all(m["ci_lower_positive"] for m in members)
    verdict = "EFFECT_SIZES_CI_POSITIVE" if all_ci_positive else "EFFECT_SIZE_CI_CROSSES_ZERO"
    return {
        "experiment": "wp13_effect_size",
        "verdict": verdict,
        "tier": "META — effect sizes, bootstrap CIs, retrospective power for the positives",
        "n_boot": N_BOOT, "delta": DELTA,
        "members": members,
        "all_bootstrap_ci_lower_positive": all_ci_positive,
        "note": "Seed-bootstrap 95% CI of the oracle gap complements the one-sided G_lo. Both positives "
                "have CI lower bound > 0 and n_seeds >= sample-complexity n*. Standardized effect = gap/sigma.",
        "prohibited_extrapolations": ["independent replication"],
    }


def main() -> None:
    r = analyze()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verdict.json").write_text(json.dumps(r, indent=2))
    print(f"WP13 EFFECT-SIZE VERDICT: {r['verdict']}")
    for m in r["members"]:
        ci = m["bootstrap_ci95"]
        print(f"  {m['claim']:18s} gap={m['effect_gap']:.4f}  CI95=[{ci[0]:+.4f},{ci[1]:+.4f}]  "
              f"std-effect={m['standardized_effect']:.1f}  n*={m['sample_complexity_nstar']}  "
              f"n>=n*={m['n_exceeds_nstar']}")


if __name__ == "__main__":
    main()
