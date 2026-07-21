"""WP5-AC2 learned compute-controller.

A reward-only REINFORCE policy pi(K|d) over the AC1 utilities: does it recover the oracle
compute-allocation (K=d) out-of-sample? The compute-axis analog of the L4a plasticity governor.
See PREREGISTRATION_CONTROLLER.md. Deterministic.
"""
from __future__ import annotations

import glob
import json
import math
import random
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "artifacts/wp5-adaptive-compute-identifiability/raw_runs"
OUT = ROOT / "artifacts/wp5-adaptive-compute-controller"

LAMBDA = 0.5
TRAIN_SEEDS = [0, 1, 2, 3]
EVAL_SEEDS = [4, 5, 6, 7]
CONTROLLER_SEEDS = 8
N_EPISODES = 4000
LR = 0.2


def _utils() -> tuple[dict[int, list[list[float]]], list[str], list[str]]:
    runs = [json.load(open(f)) for f in sorted(glob.glob(str(RAW / "seed*.json")))]
    depths = [str(d) for d in runs[0]["depths"]]
    ks = [str(k) for k in runs[0]["k_choices"]]
    kmax = max(int(k) for k in ks)
    util = {r["seed"]: [[r["acc"][d][k] - LAMBDA * int(k) / kmax for k in ks] for d in depths]
            for r in runs}
    return util, depths, ks


def _collapse(util):
    return {s: [m[0][:] for _ in m] for s, m in util.items()}


def _softmax(theta):
    mx = max(theta)
    ex = [math.exp(t - mx) for t in theta]
    z = sum(ex)
    return [e / z for e in ex]


def _mean(util, seeds, c, a):
    return sum(util[s][c][a] for s in seeds) / len(seeds)


def _recovery(util, n_ctx, n_act) -> tuple[float, float, float, float]:
    oracle = sum(max(_mean(util, EVAL_SEEDS, c, a) for a in range(n_act)) for c in range(n_ctx)) / n_ctx
    fixed = max(range(n_act), key=lambda a: sum(_mean(util, TRAIN_SEEDS, c, a) for c in range(n_ctx)))
    best_fixed = sum(_mean(util, EVAL_SEEDS, c, fixed) for c in range(n_ctx)) / n_ctx
    rand = sum(_mean(util, EVAL_SEEDS, c, a) for c in range(n_ctx) for a in range(n_act)) / (n_ctx * n_act)
    gap = oracle - best_fixed
    if gap <= 1e-9:
        return 0.0, oracle, best_fixed, rand
    recs = []
    for cs in range(CONTROLLER_SEEDS):
        rng = random.Random(0xAC2 ^ cs)
        theta = [[0.0] * n_act for _ in range(n_ctx)]
        base = [0.0] * n_ctx
        for ep in range(N_EPISODES):
            c = ep % n_ctx
            pi = _softmax(theta[c])
            u = rng.random()
            cum = 0.0
            a = n_act - 1
            for i, pr in enumerate(pi):
                cum += pr
                if u <= cum:
                    a = i
                    break
            reward = util[rng.choice(TRAIN_SEEDS)][c][a]
            base[c] = 0.99 * base[c] + 0.01 * reward
            adv = reward - base[c]
            for j in range(n_act):
                theta[c][j] += LR * adv * ((1.0 - pi[j]) if j == a else -pi[j])
        arm = [max(range(n_act), key=lambda a: theta[c][a]) for c in range(n_ctx)]
        realised = sum(_mean(util, EVAL_SEEDS, c, arm[c]) for c in range(n_ctx)) / n_ctx
        recs.append((realised - best_fixed) / gap)
    return min(recs), oracle, best_fixed, rand


def analyze() -> dict[str, Any]:
    util, depths, ks = _utils()
    n_ctx, n_act = len(depths), len(ks)
    worst_rec, oracle, best_fixed, rand = _recovery(util, n_ctx, n_act)
    null_rec, _, _, _ = _recovery(_collapse(util), n_ctx, n_act)

    random_below_fixed = rand < best_fixed
    recovered = worst_rec >= 0.8
    null_ok = null_rec <= 0.10
    if not (random_below_fixed and null_ok):
        verdict = "AC2_VOID"
    elif recovered:
        verdict = "AC2_CONTROLLER_RECOVERS"
    else:
        verdict = "AC2_NOT_RECOVERED"

    return {
        "experiment": "wp5_adaptive_compute_controller",
        "verdict": verdict,
        "tier": "SYNTHETIC — learned reward-only compute-controller (given difficulty)",
        "lambda": LAMBDA, "train_seeds": TRAIN_SEEDS, "eval_seeds": EVAL_SEEDS,
        "controller_seeds": CONTROLLER_SEEDS,
        "worst_recovery": worst_rec, "oracle": oracle, "best_fixed": best_fixed, "random": rand,
        "null_recovery": null_rec,
        "random_below_fixed": random_below_fixed, "recovered": recovered, "null_ok": null_ok,
        "prohibited_extrapolations": ["inferred-difficulty routing", "real-workload",
                                      "L7 compute-equivalent Pareto", "independent replication"],
    }


def main() -> None:
    r = analyze()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verdict.json").write_text(json.dumps(r, indent=2))
    print(f"WP5-AC2 CONTROLLER VERDICT: {r['verdict']}")
    print(f"  held-out: oracle={r['oracle']:.4f} best_fixed={r['best_fixed']:.4f} random={r['random']:.4f}")
    print(f"  worst recovery={r['worst_recovery']:.3f}  null_recovery={r['null_recovery']:.3f}")


if __name__ == "__main__":
    main()
