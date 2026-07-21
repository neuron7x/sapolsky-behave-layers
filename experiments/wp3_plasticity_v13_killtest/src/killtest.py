"""L4k falsification boundary — the most decisive kill-conditions for the plasticity line.

The line's foundation is a genuine context x arm interaction. This destroys the interaction three
ways (additive, collapsed, arm-shuffle nulls) and confirms the gap vanishes each time while the
real control keeps it. If a null still showed a gap, the whole line would be falsified. See
PREREGISTRATION.md. Deterministic.
"""
from __future__ import annotations

import glob
import json
import math
import random
from pathlib import Path
from typing import Any

from experiments.common.identifiability_inference import gap_lower_confidence_bound, plugin_gap

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "artifacts/wp3-plasticity-v2-confirmatory/raw_runs"
OUT = ROOT / "artifacts/wp3-plasticity-v13-killtest"

GROUPS = ["attn", "mlp", "head", "embed"]
TASKS = ["lexical", "relational"]
LAMBDA = 1.0
DELTA = 0.05
TRAIN_SEEDS = list(range(5, 13))
EVAL_SEEDS = list(range(13, 21))
CONTROLLER_SEEDS = 8
N_EPISODES = 4000
LR = 0.2


def _per_seed_utils() -> dict[int, list[list[float]]]:
    runs = [json.load(open(f)) for f in sorted(glob.glob(str(RAW / "seed*.json")))]
    cost = {a: runs[0]["tasks"][TASKS[0]][a]["cost_params"] for a in GROUPS}
    km = max(cost.values())
    return {r["seed"]: [[r["tasks"][t][a]["new_acc"] - LAMBDA * cost[a] / km for a in GROUPS]
                        for t in TASKS] for r in runs}


def _mutate(util: dict[int, list[list[float]]], kind: str) -> dict[int, list[list[float]]]:
    if kind == "real":
        return util
    out = {}
    for s, m in util.items():
        if kind == "additive":
            n_t, n_a = len(m), len(m[0])
            grand = sum(m[t][a] for t in range(n_t) for a in range(n_a)) / (n_t * n_a)
            row = [sum(m[t]) / n_a for t in range(n_t)]
            col = [sum(m[t][a] for t in range(n_t)) / n_t for a in range(n_a)]
            out[s] = [[row[t] + col[a] - grand for a in range(n_a)] for t in range(n_t)]
        elif kind == "collapsed":
            out[s] = [m[0][:], m[0][:]]
        elif kind == "aligned_best":
            # move context 1's best arm onto context 0's best-arm index, so ONE fixed arm is
            # optimal for both contexts -> context-conditioning genuinely destroyed.
            n_a = len(GROUPS)
            i0 = max(range(n_a), key=lambda a: m[0][a])   # context 0 argmax
            i1 = max(range(n_a), key=lambda a: m[1][a])   # context 1 argmax
            row1 = m[1][:]
            row1[i0], row1[i1] = row1[i1], row1[i0]        # swap so context 1's max lands at i0
            out[s] = [m[0][:], row1]
    return out


def _var(v: list[float]) -> float:
    if len(v) < 2:
        return 0.0
    mu = sum(v) / len(v)
    return sum((x - mu) ** 2 for x in v) / (len(v) - 1)


def _certificate(util: dict[int, list[list[float]]]) -> float:
    seeds = sorted(util)
    n = len(seeds)
    uhat, se = [], 0.0
    for ti in range(len(TASKS)):
        row = []
        for ai in range(len(GROUPS)):
            vals = [util[s][ti][ai] for s in seeds]
            row.append(sum(vals) / n)
            se = max(se, math.sqrt(_var(vals)) / math.sqrt(n))
        uhat.append(row)
    return gap_lower_confidence_bound(plugin_gap(uhat), se, len(TASKS), len(GROUPS), DELTA)


def _softmax(theta: list[float]) -> list[float]:
    mx = max(theta)
    ex = [math.exp(t - mx) for t in theta]
    return [e / sum(ex) for e in ex]


def _mean_u(util, seeds, c, a):
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
        rng = random.Random(0x11 ^ cs)
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
    util = _per_seed_utils()
    conditions = {}
    for kind in ("real", "additive", "collapsed", "aligned_best"):
        u = _mutate(util, kind)
        glo = _certificate(u)
        rec = _governor_recovery(u)
        conditions[kind] = {"gap_lower_bound": glo, "governor_recovery": rec}

    real = conditions["real"]
    real_ok = real["gap_lower_bound"] > 0.0 and real["governor_recovery"] >= 0.8
    nulls_vanish = all(conditions[k]["gap_lower_bound"] <= 0.0 and conditions[k]["governor_recovery"] <= 0.10
                       for k in ("additive", "collapsed", "aligned_best"))
    verdict = "L4K_LINE_SURVIVES" if (real_ok and nulls_vanish) else "L4K_LINE_FALSIFIED"
    return {
        "experiment": "wp3_plasticity_v13_killtest",
        "verdict": verdict,
        "tier": "SYNTHETIC — falsification boundary / foundation check of the L4 line",
        "lambda": LAMBDA, "delta": DELTA,
        "conditions": conditions,
        "real_shows_gap": real_ok,
        "all_nulls_vanish": nulls_vanish,
        "prohibited_extrapolations": ["real-workload behavior", "L7 compute-equivalent Pareto",
                                      "external validity beyond synthetic"],
    }


def main() -> None:
    r = analyze()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verdict.json").write_text(json.dumps(r, indent=2))
    print(f"L4k FALSIFICATION-BOUNDARY VERDICT: {r['verdict']}")
    for kind, c in r["conditions"].items():
        print(f"  {kind:11s}  G_lo={c['gap_lower_bound']:+.4f}  gov_recovery={c['governor_recovery']:+.3f}")
    print(f"  real_shows_gap={r['real_shows_gap']}  all_nulls_vanish={r['all_nulls_vanish']}")


if __name__ == "__main__":
    main()
