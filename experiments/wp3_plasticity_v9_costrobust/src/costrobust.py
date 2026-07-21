"""L4g robustness of the plasticity oracle gap to the cost model.

Re-derives identifiability (certificate G_lo) and a reward-only governor's held-out recovery
under four monotone cost transforms (linear/sqrt/log/square) at fixed lambda, on the real
confirmatory seeds. ROBUST iff the gap survives every cost shape. See PREREGISTRATION.md.
Deterministic.
"""
from __future__ import annotations

import glob
import json
import math
import random
from pathlib import Path
from typing import Any, Callable

from experiments.common.identifiability_inference import gap_lower_confidence_bound, plugin_gap

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "artifacts/wp3-plasticity-v2-confirmatory/raw_runs"
OUT = ROOT / "artifacts/wp3-plasticity-v9-costrobust"

GROUPS = ["attn", "mlp", "head", "embed"]
TASKS = ["lexical", "relational"]
LAMBDA = 1.0
DELTA = 0.05
TRAIN_SEEDS = list(range(5, 13))
EVAL_SEEDS = list(range(13, 21))
CONTROLLER_SEEDS = 8
N_EPISODES = 4000
LR = 0.2

TRANSFORMS: dict[str, Callable[[float], float]] = {
    "linear": lambda x: x,
    "sqrt": lambda x: math.sqrt(x),
    "log": lambda x: math.log1p(x),
    "square": lambda x: x * x,
}


def _runs() -> dict[int, dict[str, Any]]:
    return {int(Path(f).stem.replace("seed", "")): json.load(open(f))
            for f in sorted(glob.glob(str(RAW / "seed*.json")))}


def _utils(runs: dict[int, dict[str, Any]], f: Callable[[float], float]) -> dict[int, list[list[float]]]:
    any_run = next(iter(runs.values()))
    raw_cost = {a: any_run["tasks"][TASKS[0]][a]["cost_params"] for a in GROUPS}
    fmax = f(max(raw_cost.values()))
    cnorm = {a: f(raw_cost[a]) / fmax for a in GROUPS}
    return {s: [[r["tasks"][t][a]["new_acc"] - LAMBDA * cnorm[a] for a in GROUPS] for t in TASKS]
            for s, r in runs.items()}


def _var(vals: list[float]) -> float:
    if len(vals) < 2:
        return 0.0
    m = sum(vals) / len(vals)
    return sum((v - m) ** 2 for v in vals) / (len(vals) - 1)


def _certificate(util: dict[int, list[list[float]]]) -> dict[str, float | bool]:
    seeds = sorted(util)
    n = len(seeds)
    uhat, max_se = [], 0.0
    for ti in range(len(TASKS)):
        row = []
        for ai in range(len(GROUPS)):
            vals = [util[s][ti][ai] for s in seeds]
            row.append(sum(vals) / n)
            max_se = max(max_se, math.sqrt(_var(vals)) / math.sqrt(n))
        uhat.append(row)
    ghat = plugin_gap(uhat)
    glo = gap_lower_confidence_bound(ghat, max_se, len(TASKS), len(GROUPS), DELTA)
    return {"gap_hat": ghat, "gap_lower_bound": glo, "identifiable": glo > 0.0}


def _softmax(theta: list[float]) -> list[float]:
    m = max(theta)
    ex = [math.exp(t - m) for t in theta]
    z = sum(ex)
    return [e / z for e in ex]


def _mean_u(util: dict[int, list[list[float]]], seeds: list[int], c: int, a: int) -> float:
    return sum(util[s][c][a] for s in seeds) / len(seeds)


def _governor_recovery(util: dict[int, list[list[float]]]) -> float:
    n_a = len(GROUPS)
    oracle = sum(max(_mean_u(util, EVAL_SEEDS, c, a) for a in range(n_a)) for c in range(2)) / 2.0
    fixed = max(range(n_a), key=lambda a: sum(_mean_u(util, TRAIN_SEEDS, c, a) for c in range(2)))
    best_fixed = sum(_mean_u(util, EVAL_SEEDS, c, fixed) for c in range(2)) / 2.0
    gap = oracle - best_fixed
    if gap <= 1e-9:
        return 0.0
    recs = []
    for cs in range(CONTROLLER_SEEDS):
        rng = random.Random(0x9A7 ^ cs)
        theta = [[0.0] * n_a for _ in range(2)]
        base = [0.0, 0.0]
        for ep in range(N_EPISODES):
            c = ep & 1
            pi = _softmax(theta[c])
            u = rng.random()
            cum = 0.0
            a = n_a - 1
            for i, pr in enumerate(pi):
                cum += pr
                if u <= cum:
                    a = i
                    break
            reward = util[rng.choice(TRAIN_SEEDS)][c][a]
            base[c] = 0.99 * base[c] + 0.01 * reward
            adv = reward - base[c]
            for j in range(n_a):
                theta[c][j] += LR * adv * ((1.0 - pi[j]) if j == a else -pi[j])
        arm = [max(range(n_a), key=lambda a: theta[c][a]) for c in range(2)]
        realised = sum(_mean_u(util, EVAL_SEEDS, c, arm[c]) for c in range(2)) / 2.0
        recs.append((realised - best_fixed) / gap)
    return min(recs)


def analyze() -> dict[str, Any]:
    runs = _runs()
    per = {}
    for name, f in TRANSFORMS.items():
        util = _utils(runs, f)
        cert = _certificate(util)
        rec = _governor_recovery(util)
        per[name] = {**cert, "worst_governor_recovery": rec,
                     "robust": bool(cert["identifiable"]) and rec >= 0.8}
    robust = all(per[n]["robust"] for n in TRANSFORMS)
    verdict = "L4G_ROBUST" if robust else "L4G_COST_SHAPE_DEPENDENT"
    return {
        "experiment": "wp3_plasticity_v9_costrobust",
        "verdict": verdict,
        "tier": "SYNTHETIC — validity/robustness of L4 identifiability to the cost model",
        "lambda": LAMBDA, "delta": DELTA,
        "per_transform": per,
        "all_transforms_robust": robust,
        "prohibited_extrapolations": ["real-workload behavior", "L7 compute-equivalent Pareto",
                                      "energy or latency advantage", "independent replication"],
    }


def main() -> None:
    r = analyze()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verdict.json").write_text(json.dumps(r, indent=2))
    print(f"L4g COST-ROBUST VERDICT: {r['verdict']}")
    for name, p in r["per_transform"].items():
        print(f"  {name:7s}  G_lo={p['gap_lower_bound']:+.4f}  identifiable={p['identifiable']}  "
              f"gov_recovery={p['worst_governor_recovery']:.3f}  robust={p['robust']}")


if __name__ == "__main__":
    main()
