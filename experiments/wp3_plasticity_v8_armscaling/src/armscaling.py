"""L4f arm-count scaling of the collapse exponent.

Tests L4e's account ("dead arms inject diffusion") as a monotone law: sweeps the number of
arms K and fits the budget exponent for each. Prediction: the exponent shallows monotonically
toward the diffusion limit -0.5 as K grows, from the 2-arm drift limit ~-1. See PREREGISTRATION.
Deterministic (Box-Muller over a fixed LCG).
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from experiments.common.identifiability_inference import _Rng
from experiments.wp3_plasticity_v5_thinmargin.src.thinmargin import _delta_star, _softmax

OUT = Path(__file__).resolve().parents[3] / "artifacts/wp3-plasticity-v8-armscaling"

DELTAS = [0.40, 0.30, 0.20, 0.15, 0.10, 0.07, 0.05, 0.03, 0.02, 0.015, 0.01, 0.008, 0.005, 0.003, 0.001]
CONTROLLER_SEEDS = 24
BUDGETS = [1500, 3000, 6000, 12000]
ARMS = [2, 3, 4, 6, 8]
SIGMA0 = 0.10
LR = 0.2


def _means(k: int, delta: float) -> list[list[float]]:
    """context 0 best = arm0, context 1 best = arm1, runner-up 1-delta, arms 2..k-1 dead."""
    row0 = [1.0, 1.0 - delta] + [0.0] * (k - 2)
    row1 = [1.0 - delta, 1.0] + [0.0] * (k - 2)
    return [row0, row1]


def _train_greedy(means: list[list[float]], k: int, sigma: float, n_episodes: int, ctrl_seed: int) -> list[int]:
    rng = _Rng(0xF1F ^ (ctrl_seed * 1637 + k * 101 + n_episodes))
    theta = [[0.0] * k for _ in range(2)]
    baseline = [0.0, 0.0]
    for ep in range(n_episodes):
        c = ep & 1
        pi = _softmax(theta[c])
        u = rng._unit()
        cum = 0.0
        a = k - 1
        for i, pr in enumerate(pi):
            cum += pr
            if u <= cum:
                a = i
                break
        reward = means[c][a] + sigma * rng.gauss()
        baseline[c] = 0.99 * baseline[c] + 0.01 * reward
        adv = reward - baseline[c]
        for j in range(k):
            grad = (1.0 - pi[j]) if j == a else (-pi[j])
            theta[c][j] += LR * adv * grad
    return [max(range(k), key=lambda a: theta[c][a]) for c in range(2)]


def _recovery(means: list[list[float]], arm: list[int], delta: float) -> float:
    realised = (means[0][arm[0]] + means[1][arm[1]]) / 2.0
    best_fixed = 1.0 - delta / 2.0
    return (realised - best_fixed) / (delta / 2.0) if delta > 1e-12 else 0.0


def _dstar(k: int, n_episodes: int) -> float:
    recs = []
    for delta in DELTAS:
        means = _means(k, delta)
        r = [_recovery(means, _train_greedy(means, k, SIGMA0, n_episodes, cs), delta)
             for cs in range(CONTROLLER_SEEDS)]
        recs.append(sum(r) / len(r))
    return _delta_star(DELTAS, recs)


def _loglog_slope(xs: list[float], ys: list[float]) -> float:
    lx = [math.log(x) for x in xs]
    ly = [math.log(y) for y in ys]
    n = len(lx)
    sx, sy, sxy, sxx = sum(lx), sum(ly), sum(a * b for a, b in zip(lx, ly)), sum(a * a for a in lx)
    return (n * sxy - sx * sy) / (n * sxx - sx * sx)


def analyze() -> dict[str, Any]:
    per_arm = {}
    any_nan = False
    for k in ARMS:
        dstar = {n: _dstar(k, n) for n in BUDGETS}
        nanflag = any(math.isnan(v) for v in dstar.values())
        any_nan = any_nan or nanflag
        exp = float("nan") if nanflag else _loglog_slope(BUDGETS, [dstar[n] for n in BUDGETS])
        per_arm[k] = {"delta_star": dstar, "exponent": exp}

    exps = [per_arm[k]["exponent"] for k in ARMS]
    if any_nan:
        verdict = "L4F_INSTRUMENT_LIMITED"
        monotone = shallows = False
    else:
        monotone = all(exps[i + 1] >= exps[i] - 0.10 for i in range(len(exps) - 1))
        shallows = (exps[-1] - exps[0]) >= 0.25
        drift_at_2 = exps[0] <= -0.9
        exp_range = max(exps) - min(exps)
        if monotone and shallows and drift_at_2:
            verdict = "L4F_ARM_SCALING_MAPPED"
        elif exp_range < 0.15:
            verdict = "L4F_NO_ARM_DEPENDENCE"
        else:
            verdict = "L4F_NON_MONOTONE"

    return {
        "experiment": "wp3_plasticity_v8_armscaling",
        "verdict": verdict,
        "tier": "SYNTHETIC-PARAMETRIC — arm-count dependence of the governor-collapse exponent",
        "controller_seeds": CONTROLLER_SEEDS, "budgets": BUDGETS, "arms": ARMS, "sigma0": SIGMA0,
        "per_arm": {str(k): per_arm[k] for k in ARMS},
        "exponents": {str(k): per_arm[k]["exponent"] for k in ARMS},
        "monotone_shallowing": monotone if not any_nan else None,
        "shallows_by_0.25": shallows if not any_nan else None,
        "prediction": "exponent shallows monotonically from drift limit (~-1) toward diffusion (~-0.5) as K grows",
        "prohibited_extrapolations": ["real-workload behavior", "L7 compute-equivalent Pareto",
                                      "energy or latency advantage", "independent replication"],
    }


def main() -> None:
    r = analyze()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verdict.json").write_text(json.dumps(r, indent=2))
    print(f"L4f ARM-SCALING VERDICT: {r['verdict']}")
    for k in ARMS:
        e = r["per_arm"][str(k)]["exponent"]
        print(f"  K={k}  exponent={e:.3f}")
    print(f"  monotone shallowing = {r['monotone_shallowing']}  shallows>=0.25 = {r['shallows_by_0.25']}")


if __name__ == "__main__":
    main()
