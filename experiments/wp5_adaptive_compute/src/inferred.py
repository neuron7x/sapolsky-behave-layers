"""WP5-AC3 inferred-difficulty boundary.

The compute-controller sees only a noisy observation z of the difficulty, so the compute decision
has a real cost and can fail. Sweeps observation noise and maps held-out recovery against the
mutual information I(C;Z). Compute-axis analog of the L4b plasticity boundary. See
PREREGISTRATION_INFERRED.md. Deterministic.
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
OUT = ROOT / "artifacts/wp5-adaptive-compute-inferred"

LAMBDA = 0.5
TRAIN_SEEDS = [0, 1, 2, 3]
EVAL_SEEDS = [4, 5, 6, 7]
FLIP_SWEEP = [0.0, 0.1, 0.2, 0.35, 0.5, 0.667]
CONTROLLER_SEEDS = 8
N_EPISODES = 6000
LR = 0.2


def _utils():
    runs = [json.load(open(f)) for f in sorted(glob.glob(str(RAW / "seed*.json")))]
    depths = [str(d) for d in runs[0]["depths"]]
    ks = [str(k) for k in runs[0]["k_choices"]]
    kmax = max(int(k) for k in ks)
    util = {r["seed"]: [[r["acc"][d][k] - LAMBDA * int(k) / kmax for k in ks] for d in depths]
            for r in runs}
    return util, len(depths), len(ks)


def _info_bits(p: float, n: int = 3) -> float:
    if p <= 0.0:
        return math.log2(n)
    if p >= (n - 1) / n:
        return 0.0
    return math.log2(n) + (1 - p) * math.log2(1 - p) + p * math.log2(p / (n - 1))


def _softmax(theta):
    mx = max(theta)
    ex = [math.exp(t - mx) for t in theta]
    z = sum(ex)
    return [e / z for e in ex]


def _mean(util, seeds, c, a):
    return sum(util[s][c][a] for s in seeds) / len(seeds)


def _sweep(util, n_ctx, n_act):
    oracle = sum(max(_mean(util, EVAL_SEEDS, c, a) for a in range(n_act)) for c in range(n_ctx)) / n_ctx
    fixed = max(range(n_act), key=lambda a: sum(_mean(util, TRAIN_SEEDS, c, a) for c in range(n_ctx)))
    best_fixed = sum(_mean(util, EVAL_SEEDS, c, fixed) for c in range(n_ctx)) / n_ctx
    gap = oracle - best_fixed
    rows = []
    for p in FLIP_SWEEP:
        recs = []
        for cs in range(CONTROLLER_SEEDS):
            rng = random.Random(0xAC3 ^ (cs * 131 + int(p * 1000)))
            theta = [[0.0] * n_act for _ in range(n_ctx)]   # policy per OBSERVED z
            base = [0.0] * n_ctx
            for _ in range(N_EPISODES):
                d = rng.randrange(n_ctx)
                if rng.random() < p:                        # noisy observation
                    others = [c for c in range(n_ctx) if c != d]
                    z = rng.choice(others)
                else:
                    z = d
                pi = _softmax(theta[z])
                u = rng.random()
                cum = 0.0
                a = n_act - 1
                for i, pr in enumerate(pi):
                    cum += pr
                    if u <= cum:
                        a = i
                        break
                reward = util[rng.choice(TRAIN_SEEDS)][d][a]     # reward from TRUE difficulty
                base[z] = 0.99 * base[z] + 0.01 * reward
                adv = reward - base[z]
                for j in range(n_act):
                    theta[z][j] += LR * adv * ((1.0 - pi[j]) if j == a else -pi[j])
            arm_by_z = [max(range(n_act), key=lambda a: theta[z][a]) for z in range(n_ctx)]
            # realised: true d, observed z (noisy) -> action arm_by_z[z]
            realised = 0.0
            for d in range(n_ctx):
                for z in range(n_ctx):
                    pz = (1 - p) if z == d else (p / (n_ctx - 1))
                    realised += (1.0 / n_ctx) * pz * _mean(util, EVAL_SEEDS, d, arm_by_z[z])
            recs.append((realised - best_fixed) / gap if gap > 1e-9 else 0.0)
        rows.append({"flip_p": p, "info_bits": _info_bits(p, n_ctx),
                     "recovery_mean": sum(recs) / len(recs), "recovery_worst": min(recs)})
    return rows, oracle, best_fixed, gap


def analyze() -> dict[str, Any]:
    util, n_ctx, n_act = _utils()
    rows, oracle, best_fixed, gap = _sweep(util, n_ctx, n_act)
    recs = [r["recovery_mean"] for r in rows]
    rec0 = recs[0]
    rec_lo = recs[-1]
    monotone = all(recs[i] >= recs[i + 1] - 0.05 for i in range(len(recs) - 1))
    never_neg = all(r["recovery_worst"] >= -0.05 for r in rows)
    boundary = rec_lo <= 0.15
    mapped = rec0 >= 0.9 and monotone and boundary and never_neg
    verdict = "AC3_BOUNDARY_MAPPED" if mapped else "AC3_NOT_MAPPED"
    return {
        "experiment": "wp5_adaptive_compute_inferred",
        "verdict": verdict,
        "tier": "SYNTHETIC — route-decision-cost / value-of-information boundary on compute",
        "lambda": LAMBDA, "oracle": oracle, "best_fixed": best_fixed, "gap": gap,
        "sweep": rows,
        "recovery_full_info": rec0, "recovery_zero_info": rec_lo,
        "monotone_in_information": monotone, "controller_abstains": never_neg,
        "prohibited_extrapolations": ["real-workload", "L7 compute-equivalent Pareto",
                                      "independent replication"],
    }


def main() -> None:
    r = analyze()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verdict.json").write_text(json.dumps(r, indent=2))
    print(f"WP5-AC3 INFERRED-DIFFICULTY VERDICT: {r['verdict']}")
    print(f"  gap={r['gap']:.4f}")
    print("  p      I(C;Z)  recovery(mean)  worst")
    for row in r["sweep"]:
        print(f"  {row['flip_p']:.3f}  {row['info_bits']:.3f}   {row['recovery_mean']:+.3f}         "
              f"{row['recovery_worst']:+.3f}")
    print(f"  monotone={r['monotone_in_information']} rec@fullI={r['recovery_full_info']:.3f} "
          f"rec@0I={r['recovery_zero_info']:.3f} abstains={r['controller_abstains']}")


if __name__ == "__main__":
    main()
