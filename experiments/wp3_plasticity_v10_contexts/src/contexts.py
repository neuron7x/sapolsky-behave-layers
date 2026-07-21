"""L4h generalization to more contexts.

Scales the number of contexts |C| (each with its own best arm) at CONSTANT per-context budget
and checks whether identifiability (certificate G_lo) and governor recovery hold, isolating
context interference from budget dilution. See PREREGISTRATION.md. Deterministic.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from experiments.common.identifiability_inference import _Rng, gap_lower_confidence_bound, plugin_gap

OUT = Path(__file__).resolve().parents[3] / "artifacts/wp3-plasticity-v10-contexts"

CONTEXTS = [2, 3, 4, 6]
DELTA_MARGIN = 0.20
SIGMA = 0.10
PER_CONTEXT_EPISODES = 3000
CONTROLLER_SEEDS = 8
LR = 0.2
DELTA = 0.05
N_EVAL = 400            # noiseless expected utility is exact; eval seeds emulate held-out draws


def _means(n_ctx: int) -> list[list[float]]:
    m = []
    for c in range(n_ctx):
        row = [0.0] * n_ctx
        row[c] = 1.0                              # best arm for context c
        row[(c + 1) % n_ctx] = 1.0 - DELTA_MARGIN  # runner-up
        m.append(row)
    return m


def _softmax(theta: list[float]) -> list[float]:
    mx = max(theta)
    ex = [math.exp(t - mx) for t in theta]
    z = sum(ex)
    return [e / z for e in ex]


def _certificate(means: list[list[float]], n_ctx: int) -> dict[str, float | bool]:
    # noiseless expected-utility matrix; per-cell se from the sampling model sigma/sqrt(N_EVAL)
    se = SIGMA / math.sqrt(N_EVAL)
    ghat = plugin_gap(means)
    glo = gap_lower_confidence_bound(ghat, se, n_ctx, n_ctx, DELTA)
    return {"gap_hat": ghat, "gap_lower_bound": glo, "identifiable": glo > 0.0}


def _governor_recovery(means: list[list[float]], n_ctx: int) -> float:
    oracle = sum(max(means[c]) for c in range(n_ctx)) / n_ctx
    best_fixed = max(sum(means[c][a] for c in range(n_ctx)) / n_ctx for a in range(n_ctx))
    gap = oracle - best_fixed
    if gap <= 1e-9:
        return 0.0
    recs = []
    for cs in range(CONTROLLER_SEEDS):
        rng = _Rng(0xC70 ^ (cs * 613 + n_ctx))
        theta = [[0.0] * n_ctx for _ in range(n_ctx)]
        base = [0.0] * n_ctx
        total = PER_CONTEXT_EPISODES * n_ctx
        for ep in range(total):
            c = ep % n_ctx
            pi = _softmax(theta[c])
            u = rng._unit()
            cum = 0.0
            a = n_ctx - 1
            for i, pr in enumerate(pi):
                cum += pr
                if u <= cum:
                    a = i
                    break
            reward = means[c][a] + SIGMA * rng.gauss()
            base[c] = 0.99 * base[c] + 0.01 * reward
            adv = reward - base[c]
            for j in range(n_ctx):
                theta[c][j] += LR * adv * ((1.0 - pi[j]) if j == a else -pi[j])
        arm = [max(range(n_ctx), key=lambda a: theta[c][a]) for c in range(n_ctx)]
        realised = sum(means[c][arm[c]] for c in range(n_ctx)) / n_ctx
        recs.append((realised - best_fixed) / gap)
    return min(recs)


def analyze() -> dict[str, Any]:
    per = {}
    for nc in CONTEXTS:
        means = _means(nc)
        cert = _certificate(means, nc)
        rec = _governor_recovery(means, nc)
        per[str(nc)] = {**cert, "worst_governor_recovery": rec,
                        "ok": bool(cert["identifiable"]) and rec >= 0.8}
    generalizes = all(per[str(nc)]["ok"] for nc in CONTEXTS)
    verdict = "L4H_GENERALIZES" if generalizes else "L4H_CONTEXT_INTERFERENCE"
    return {
        "experiment": "wp3_plasticity_v10_contexts",
        "verdict": verdict,
        "tier": "SYNTHETIC-PARAMETRIC — generalization of identifiability+governor to more contexts",
        "contexts": CONTEXTS, "delta_margin": DELTA_MARGIN, "sigma": SIGMA,
        "per_context_episodes": PER_CONTEXT_EPISODES,
        "per_context_count": per,
        "generalizes": generalizes,
        "prohibited_extrapolations": ["real-workload behavior", "L7 compute-equivalent Pareto",
                                      "energy or latency advantage", "independent replication"],
    }


def main() -> None:
    r = analyze()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verdict.json").write_text(json.dumps(r, indent=2))
    print(f"L4h CONTEXT-SCALING VERDICT: {r['verdict']}")
    for nc in CONTEXTS:
        p = r["per_context_count"][str(nc)]
        print(f"  |C|={nc}  G_lo={p['gap_lower_bound']:+.4f}  identifiable={p['identifiable']}  "
              f"gov_recovery={p['worst_governor_recovery']:.3f}  ok={p['ok']}")


if __name__ == "__main__":
    main()
