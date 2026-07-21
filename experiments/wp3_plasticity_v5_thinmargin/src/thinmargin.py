"""L4c thin-margin credit-assignment collapse.

Stress-tests the learned governor: isolates the distinguishability (margin Delta between
the best arm and its runner-up) at a FIXED learning budget, sweeps Delta x noise, and finds
where REINFORCE credit assignment collapses. Tests the grounded prediction that the collapse
margin scales linearly with noise (the (sigma/Delta)^2 sample-complexity signature).
See PREREGISTRATION.md. Deterministic (Box-Muller over a fixed LCG).
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from experiments.common.identifiability_inference import _Rng

OUT = Path(__file__).resolve().parents[3] / "artifacts/wp3-plasticity-v5-thinmargin"

N_ARMS = 4
DELTAS = [0.40, 0.20, 0.10, 0.05, 0.02]
SIGMA0 = 0.10
SIGMAS = [SIGMA0, 2 * SIGMA0]
CONTROLLER_SEEDS = 8
N_EPISODES = 3000        # FIXED learning budget (the stress: no growth as Delta shrinks)
LR = 0.2


def _means(delta: float) -> list[list[float]]:
    """context 0 best = arm0, context 1 best = arm1; runner-up pays 1-delta."""
    return [
        [1.0, 1.0 - delta, 0.0, 0.0],
        [1.0 - delta, 1.0, 0.0, 0.0],
    ]


def _softmax(theta: list[float]) -> list[float]:
    m = max(theta)
    ex = [math.exp(t - m) for t in theta]
    z = sum(ex)
    return [e / z for e in ex]


def _train_greedy(means: list[list[float]], sigma: float, ctrl_seed: int) -> list[int]:
    rng = _Rng(0xC0DE ^ (ctrl_seed * 977 + int(sigma * 1000)))
    theta = [[0.0] * N_ARMS for _ in range(2)]
    baseline = [0.0, 0.0]
    for ep in range(N_EPISODES):
        c = ep & 1                                   # alternate contexts (fixed budget each)
        pi = _softmax(theta[c])
        u = rng._unit()
        cum = 0.0
        a = N_ARMS - 1
        for i, pr in enumerate(pi):
            cum += pr
            if u <= cum:
                a = i
                break
        reward = means[c][a] + sigma * rng.gauss()
        baseline[c] = 0.99 * baseline[c] + 0.01 * reward
        adv = reward - baseline[c]
        for j in range(N_ARMS):
            grad = (1.0 - pi[j]) if j == a else (-pi[j])
            theta[c][j] += LR * adv * grad
    return [max(range(N_ARMS), key=lambda a: theta[c][a]) for c in range(2)]


def _recovery(means: list[list[float]], arm: list[int], delta: float) -> float:
    realised = (means[0][arm[0]] + means[1][arm[1]]) / 2.0
    best_fixed = 1.0 - delta / 2.0
    gap = delta / 2.0
    return (realised - best_fixed) / gap if gap > 1e-12 else 0.0


def _delta_star(deltas: list[float], recoveries: list[float]) -> float:
    """Interpolate the Delta where recovery crosses 0.5 (deltas descending)."""
    for i in range(len(deltas) - 1):
        r_hi, r_lo = recoveries[i], recoveries[i + 1]
        if (r_hi - 0.5) * (r_lo - 0.5) <= 0 and r_hi != r_lo:
            f = (r_hi - 0.5) / (r_hi - r_lo)
            return deltas[i] + f * (deltas[i + 1] - deltas[i])
    return float("nan")


def analyze() -> dict[str, Any]:
    curves = {}
    delta_star = {}
    for sigma in SIGMAS:
        recs = []
        for delta in DELTAS:
            r = [_recovery(_means(delta), _train_greedy(_means(delta), sigma, cs), delta)
                 for cs in range(CONTROLLER_SEEDS)]
            recs.append(sum(r) / len(r))
        curves[f"sigma_{sigma:.2f}"] = [{"delta": d, "recovery": rr} for d, rr in zip(DELTAS, recs)]
        delta_star[f"sigma_{sigma:.2f}"] = _delta_star(DELTAS, recs)

    ds0 = delta_star[f"sigma_{SIGMA0:.2f}"]
    ds1 = delta_star[f"sigma_{2 * SIGMA0:.2f}"]
    scaling_ratio = ds1 / ds0 if ds0 and not math.isnan(ds0) and ds0 > 0 else float("nan")

    def _mono_collapse(curve):
        recs = [c["recovery"] for c in curve]  # delta descending -> recovery should be non-increasing
        monotone = all(recs[i] >= recs[i + 1] - 0.05 for i in range(len(recs) - 1))
        return monotone and recs[0] >= 0.9 and recs[-1] <= 0.3

    both_collapse = all(_mono_collapse(curves[k]) for k in curves)
    scaling_ok = not math.isnan(scaling_ratio) and 1.4 <= scaling_ratio <= 2.8

    if not both_collapse:
        # distinguish no-collapse (stays high) from other
        stays_high = all(curves[k][-1]["recovery"] > 0.3 for k in curves)
        verdict = "L4C_NO_COLLAPSE" if stays_high else "L4C_SCALING_VIOLATED"
    elif scaling_ok:
        verdict = "L4C_COLLAPSE_MAPPED"
    else:
        verdict = "L4C_SCALING_VIOLATED"

    return {
        "experiment": "wp3_plasticity_v5_thinmargin",
        "verdict": verdict,
        "tier": "SYNTHETIC-PARAMETRIC — governor credit-assignment limit",
        "n_episodes": N_EPISODES, "controller_seeds": CONTROLLER_SEEDS,
        "sigma0": SIGMA0, "deltas": DELTAS,
        "curves": curves,
        "delta_star": delta_star,
        "scaling_ratio_2sigma_over_sigma": scaling_ratio,
        "predicted_scaling": 2.0,
        "both_noise_levels_collapse": both_collapse,
        "sqrt_law_scaling_holds": scaling_ok,
        "prohibited_extrapolations": ["real-workload behavior", "L7 compute-equivalent Pareto",
                                      "energy or latency advantage", "independent replication"],
    }


def main() -> None:
    r = analyze()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verdict.json").write_text(json.dumps(r, indent=2))
    print(f"L4c THIN-MARGIN VERDICT: {r['verdict']}")
    for k, curve in r["curves"].items():
        row = "  ".join(f"Δ={c['delta']:.2f}:{c['recovery']:+.2f}" for c in curve)
        print(f"  {k}:  {row}   Δ*={r['delta_star'][k]:.3f}")
    print(f"  Δ*(2σ)/Δ*(σ) = {r['scaling_ratio_2sigma_over_sigma']:.2f}  (predicted ~2.0; sqrt-law "
          f"{'HOLDS' if r['sqrt_law_scaling_holds'] else 'no'})")


if __name__ == "__main__":
    main()
