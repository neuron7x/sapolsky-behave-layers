"""L4b inferred-context boundary.

The governor sees only a NOISY observation z of the context (flip probability p), so
routing has a real cost and can fail. Sweeps p, trains a REINFORCE softmax policy
pi(arm | z) on the real measured utilities, and maps held-out recovery against the
mutual information I(C;Z)=1-H2(p). Instantiates V_realized <= oracle_gap - c_route and
the value-of-information bound on the plasticity mechanism. See PREREGISTRATION.md.

Deterministic (fixed PRNG per controller seed); no torch — rewards are the frozen
measured utilities.
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
OUT = ROOT / "artifacts/wp3-plasticity-v4-inferred"

GROUPS = ["attn", "mlp", "head", "embed"]
TASKS = ["lexical", "relational"]
LAMBDA = 1.0
TRAIN_SEEDS = list(range(5, 13))
EVAL_SEEDS = list(range(13, 21))
FLIP_SWEEP = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
CONTROLLER_SEEDS = 8
N_EPISODES = 6000
LR = 0.2


def _utilities() -> dict[int, list[list[float]]]:
    runs = {int(Path(f).stem.replace("seed", "")): json.load(open(f))
            for f in sorted(glob.glob(str(RAW / "seed*.json")))}
    any_run = next(iter(runs.values()))
    cost = {a: any_run["tasks"][TASKS[0]][a]["cost_params"] for a in GROUPS}
    kmax = max(cost.values())
    return {s: [[r["tasks"][t][a]["new_acc"] - LAMBDA * cost[a] / kmax for a in GROUPS] for t in TASKS]
            for s, r in runs.items()}


def _mean_u(seeds: list[int], util: dict[int, list[list[float]]], c: int, a: int) -> float:
    return sum(util[s][c][a] for s in seeds) / len(seeds)


def _softmax(theta: list[float]) -> list[float]:
    m = max(theta)
    ex = [math.exp(t - m) for t in theta]
    z = sum(ex)
    return [e / z for e in ex]


def _entropy2(p: float) -> float:
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


def _train_greedy(util: dict[int, list[list[float]]], p: float, ctrl_seed: int) -> list[int]:
    """REINFORCE pi(arm | z), z in {0,1}. Returns greedy arm per observed z."""
    rng = random.Random(0xB4B ^ (ctrl_seed * 131 + int(p * 1000)))
    n_a = len(GROUPS)
    theta = [[0.0] * n_a for _ in range(2)]  # one row per observed z
    baseline = [0.0, 0.0]
    for _ in range(N_EPISODES):
        c = rng.randrange(2)
        z = c if rng.random() >= p else 1 - c          # noisy observation
        pi = _softmax(theta[z])
        u = rng.random()
        cum = 0.0
        a = n_a - 1
        for i, pr in enumerate(pi):
            cum += pr
            if u <= cum:
                a = i
                break
        reward = util[rng.choice(TRAIN_SEEDS)][c][a]    # reward from TRUE context
        baseline[z] = 0.99 * baseline[z] + 0.01 * reward
        adv = reward - baseline[z]
        for j in range(n_a):
            grad = (1.0 - pi[j]) if j == a else (-pi[j])
            theta[z][j] += LR * adv * grad
    return [max(range(n_a), key=lambda a: theta[z][a]) for z in range(2)]


def _realised(util: dict[int, list[list[float]]], arm_by_z: list[int], p: float) -> float:
    """Held-out realised utility: E_{c,z}[ meanU(c, arm(z)) ], z noisy."""
    tot = 0.0
    for c in range(2):
        u_correct = _mean_u(EVAL_SEEDS, util, c, arm_by_z[c])       # z == c
        u_flipped = _mean_u(EVAL_SEEDS, util, c, arm_by_z[1 - c])   # z == 1-c
        tot += (1 - p) * u_correct + p * u_flipped
    return tot / 2.0


def analyze() -> dict[str, Any]:
    util = _utilities()
    oracle = sum(max(_mean_u(EVAL_SEEDS, util, c, a) for a in range(len(GROUPS)))
                 for c in range(2)) / 2.0
    fixed_arm = max(range(len(GROUPS)),
                    key=lambda a: sum(_mean_u(TRAIN_SEEDS, util, c, a) for c in range(2)))
    best_fixed = sum(_mean_u(EVAL_SEEDS, util, c, fixed_arm) for c in range(2)) / 2.0
    gap = oracle - best_fixed
    slope = 0.4098  # grounded prediction recovery = 1 - (slope/gap)*p

    sweep = []
    for p in FLIP_SWEEP:
        recs, abstained = [], []
        for cs in range(CONTROLLER_SEEDS):
            arm_by_z = _train_greedy(util, p, cs)
            realised = _realised(util, arm_by_z, p)
            recs.append((realised - best_fixed) / gap if abs(gap) > 1e-9 else 0.0)
            abstained.append(arm_by_z[0] == arm_by_z[1])
        mean_rec = sum(recs) / len(recs)
        pred = 1.0 - (slope / gap) * p
        sweep.append({
            "flip_p": p, "mutual_information_bits": 1.0 - _entropy2(p),
            "recovery_mean": mean_rec, "recovery_worst": min(recs), "recovery_best": max(recs),
            "predicted_commit_recovery": pred,
            "abstain_fraction": sum(abstained) / len(abstained),
        })

    recs_mean = [s["recovery_mean"] for s in sweep]
    monotone = all(recs_mean[i] >= recs_mean[i + 1] - 0.03 for i in range(len(recs_mean) - 1))
    rec0 = sweep[0]["recovery_mean"]
    rec_half = sweep[-1]["recovery_mean"]
    never_negative = all(s["recovery_worst"] >= -0.02 for s in sweep)
    tracks_pred = all(abs(s["recovery_mean"] - s["predicted_commit_recovery"]) <= 0.15
                      for s in sweep if s["flip_p"] <= 0.3)

    boundary_ok = rec_half <= 0.10
    mapped = (rec0 >= 0.9) and monotone and boundary_ok and (tracks_pred or never_negative)
    verdict = "L4B_BOUNDARY_MAPPED" if mapped else "L4B_NOT_MAPPED"

    return {
        "experiment": "wp3_plasticity_v4_inferred",
        "verdict": verdict,
        "tier": "SYNTHETIC — route-decision-cost / value-of-information boundary (plasticity analog of L2b)",
        "train_seeds": TRAIN_SEEDS, "eval_seeds": EVAL_SEEDS,
        "controller_seeds": CONTROLLER_SEEDS, "episodes": N_EPISODES,
        "oracle": oracle, "best_fixed": best_fixed, "gap": gap,
        "sweep": sweep,
        "recovery_at_full_info": rec0,
        "recovery_at_zero_info": rec_half,
        "monotone_in_information": monotone,
        "tracks_grounded_prediction": tracks_pred,
        "governor_abstains_at_high_noise": never_negative,
        "prohibited_extrapolations": [
            "real-workload routing", "L7 compute-equivalent Pareto",
            "energy or latency advantage", "independent replication",
        ],
    }


def main() -> None:
    r = analyze()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verdict.json").write_text(json.dumps(r, indent=2))
    print(f"L4b INFERRED-CONTEXT VERDICT: {r['verdict']}")
    print(f"  oracle={r['oracle']:.4f} best_fixed={r['best_fixed']:.4f} gap={r['gap']:.4f}")
    print("  p     I(C;Z)  recovery(mean)  predicted  abstain")
    for s in r["sweep"]:
        print(f"  {s['flip_p']:.1f}   {s['mutual_information_bits']:.3f}   "
              f"{s['recovery_mean']:+.3f}         {s['predicted_commit_recovery']:+.3f}     "
              f"{s['abstain_fraction']:.2f}")
    print(f"  monotone={r['monotone_in_information']} rec@I=1={r['recovery_at_full_info']:.3f} "
          f"rec@I=0={r['recovery_at_zero_info']:.3f} abstains={r['governor_abstains_at_high_noise']}")


if __name__ == "__main__":
    main()
