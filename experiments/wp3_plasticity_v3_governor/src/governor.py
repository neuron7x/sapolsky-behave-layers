"""L4a learned-governor study.

A per-context softmax policy trained by REINFORCE (moving-average baseline) on the REAL
measured cost-budget utilities, learning from the reward of the sampled arm ONLY (never
the oracle). Trained on seeds 5-12, evaluated on held-out seeds 13-20. A NULL falsifier
(both contexts collapsed to one reward row) must yield ~0 recovery. See PREREGISTRATION.md.

Deterministic: fixed PRNG per controller seed. No torch — the rewards are the frozen
measured utilities; this is the controller layer on top of them.
"""
from __future__ import annotations

import glob
import json
import math
import random
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "artifacts/wp3-plasticity-v2-confirmatory/raw_runs"
OUT = ROOT / "artifacts/wp3-plasticity-v3-governor"

GROUPS = ["attn", "mlp", "head", "embed"]
TASKS = ["lexical", "relational"]
LAMBDA = 1.0
TRAIN_SEEDS = list(range(5, 13))     # 5..12
EVAL_SEEDS = list(range(13, 21))     # 13..20 held out
CONTROLLER_SEEDS = 8
N_EPISODES = 4000
LR = 0.2
RECOVERY_THRESHOLD = 0.80
NULL_RECOVERY_MAX = 0.10


def _utilities() -> dict[int, list[list[float]]]:
    """seed -> [context][arm] measured U_lambda."""
    runs = {int(Path(f).stem.replace("seed", "")): json.load(open(f))
            for f in sorted(glob.glob(str(RAW / "seed*.json")))}
    any_run = next(iter(runs.values()))
    cost = {a: any_run["tasks"][TASKS[0]][a]["cost_params"] for a in GROUPS}
    kmax = max(cost.values())
    out: dict[int, list[list[float]]] = {}
    for s, r in runs.items():
        out[s] = [[r["tasks"][t][a]["new_acc"] - LAMBDA * cost[a] / kmax for a in GROUPS] for t in TASKS]
    return out


def _collapse_null(util: dict[int, list[list[float]]]) -> dict[int, list[list[float]]]:
    """Both contexts get the lexical row => no context-conditioning can help."""
    return {s: [rows[0][:], rows[0][:]] for s, rows in util.items()}


def _softmax(theta: list[float]) -> list[float]:
    m = max(theta)
    ex = [math.exp(t - m) for t in theta]
    z = sum(ex)
    return [e / z for e in ex]


def _train_policy(util: dict[int, list[list[float]]], ctrl_seed: int) -> list[list[int]]:
    """REINFORCE; returns the greedy arm per context."""
    rng = random.Random(0xA17 ^ ctrl_seed)
    n_a = len(GROUPS)
    theta = [[0.0] * n_a for _ in TASKS]
    baseline = [0.0 for _ in TASKS]
    for _ in range(N_EPISODES):
        c = rng.randrange(len(TASKS))
        pi = _softmax(theta[c])
        # sample an arm
        u = rng.random()
        cum = 0.0
        a = n_a - 1
        for i, p in enumerate(pi):
            cum += p
            if u <= cum:
                a = i
                break
        seed = rng.choice(TRAIN_SEEDS)
        reward = util[seed][c][a]
        baseline[c] = 0.99 * baseline[c] + 0.01 * reward
        adv = reward - baseline[c]
        for j in range(n_a):
            grad = (1.0 - pi[j]) if j == a else (-pi[j])
            theta[c][j] += LR * adv * grad
    return [[max(range(n_a), key=lambda a: theta[c][a])] for c in range(len(TASKS))]


def _mean_over(seeds: list[int], util: dict[int, list[list[float]]], arm_per_ctx: list[int]) -> float:
    tot = 0.0
    for c in range(len(TASKS)):
        vals = [util[s][c][arm_per_ctx[c]] for s in seeds]
        tot += sum(vals) / len(vals)
    return tot / len(TASKS)


def _oracle_realised(seeds: list[int], util: dict[int, list[list[float]]]) -> float:
    tot = 0.0
    for c in range(len(TASKS)):
        vals = [max(util[s][c]) for s in seeds]
        tot += sum(vals) / len(vals)
    return tot / len(TASKS)


def _best_fixed_arm(seeds: list[int], util: dict[int, list[list[float]]]) -> int:
    n_a = len(GROUPS)
    return max(range(n_a), key=lambda a: _mean_over(seeds, util, [a] * len(TASKS)))


def _evaluate(util: dict[int, list[list[float]]]) -> dict[str, Any]:
    oracle = _oracle_realised(EVAL_SEEDS, util)
    fixed_arm = _best_fixed_arm(TRAIN_SEEDS, util)                       # chosen on TRAIN
    best_fixed = _mean_over(EVAL_SEEDS, util, [fixed_arm, fixed_arm])    # evaluated on held-out
    random_real = sum(_mean_over(EVAL_SEEDS, util, [a, a]) for a in range(len(GROUPS))) / len(GROUPS)
    learned_per_seed = []
    recoveries = []
    for cs in range(CONTROLLER_SEEDS):
        arm = _train_policy(util, cs)
        learned = _mean_over(EVAL_SEEDS, util, [arm[0][0], arm[1][0]])
        learned_per_seed.append(learned)
        denom = oracle - best_fixed
        recoveries.append((learned - best_fixed) / denom if abs(denom) > 1e-9 else 0.0)
    worst_learned = min(learned_per_seed)
    worst_recovery = min(recoveries)
    return {
        "oracle": oracle, "best_fixed": best_fixed, "best_fixed_arm": GROUPS[fixed_arm],
        "random": random_real, "learned_per_seed": learned_per_seed,
        "worst_learned": worst_learned, "worst_recovery": worst_recovery,
        "learned_beats_fixed_worst": worst_learned > best_fixed,
        "random_below_fixed": random_real < best_fixed,
    }


def run() -> dict[str, Any]:
    util = _utilities()
    real = _evaluate(util)
    null = _evaluate(_collapse_null(util))

    falsifier_ok = null["worst_recovery"] <= NULL_RECOVERY_MAX
    instrument_ok = real["random_below_fixed"] and falsifier_ok
    recovered = real["learned_beats_fixed_worst"] and real["worst_recovery"] >= RECOVERY_THRESHOLD

    if not instrument_ok:
        verdict = "L4A_VOID"
    elif recovered:
        verdict = "L4A_SUPPORTED"
    else:
        verdict = "L4A_NOT_SUPPORTED"

    return {
        "experiment": "wp3_plasticity_v3_governor",
        "verdict": verdict,
        "tier": "SYNTHETIC, given-context, wide-margin (reward-only learned governor)",
        "train_seeds": TRAIN_SEEDS, "eval_seeds": EVAL_SEEDS,
        "controller_seeds": CONTROLLER_SEEDS, "episodes": N_EPISODES, "lambda": LAMBDA,
        "recovery_threshold": RECOVERY_THRESHOLD, "null_recovery_max": NULL_RECOVERY_MAX,
        "real": real, "null_falsifier": null,
        "prohibited_extrapolations": [
            "inferred-context or surface-independent routing", "L7 compute-equivalent Pareto",
            "energy or latency advantage", "real-workload generalization", "independent replication",
        ],
    }


def main() -> None:
    r = run()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verdict.json").write_text(json.dumps(r, indent=2))
    re = r["real"]
    print(f"L4a GOVERNOR VERDICT: {r['verdict']}")
    print(f"  held-out: oracle={re['oracle']:.4f} best_fixed={re['best_fixed']:.4f} "
          f"({re['best_fixed_arm']}) random={re['random']:.4f}")
    print(f"  learned worst={re['worst_learned']:.4f}  worst_recovery={re['worst_recovery']:.3f}  "
          f"(threshold {r['recovery_threshold']})")
    print(f"  NULL falsifier worst_recovery={r['null_falsifier']['worst_recovery']:.3f} "
          f"(must be <= {r['null_recovery_max']})")


if __name__ == "__main__":
    main()
