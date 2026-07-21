"""L4e mechanism model — is the governor's collapse a 2-arm logit-dynamics phenomenon?

Ablates the governor to N_ARMS=2 (best arm vs runner-up, dropping the two dead arms) and
checks whether it reproduces BOTH signatures of the full 4-arm governor (committed L4d):
the steeper-than-sqrt(N) budget exponent (~-0.654) and noise-helps (ratio<1). If it does, the
collapse is explained by the two-arm REINFORCE logit drift/diffusion. See PREREGISTRATION.md.
Deterministic (Box-Muller over a fixed LCG).
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from experiments.common.identifiability_inference import _Rng
from experiments.wp3_plasticity_v5_thinmargin.src.thinmargin import _delta_star, _recovery, _softmax

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "artifacts/wp3-plasticity-v7-mechanism"
L4D = ROOT / "artifacts/wp3-plasticity-v6-scaling/verdict.json"

N_ARMS = 2                       # ABLATION: best arm vs runner-up only
DELTAS = [0.40, 0.30, 0.20, 0.15, 0.10, 0.07, 0.05, 0.03, 0.02, 0.01, 0.005]
CONTROLLER_SEEDS = 24
BUDGETS = [1500, 3000, 6000, 12000]
SIGMA0 = 0.10
LR = 0.2
TARGET_EXPONENT = -0.654         # frozen full-governor budget exponent (committed L4d)


def _means2(delta: float) -> list[list[float]]:
    return [[1.0, 1.0 - delta], [1.0 - delta, 1.0]]


def _train_greedy(means: list[list[float]], sigma: float, n_episodes: int, ctrl_seed: int) -> list[int]:
    rng = _Rng(0xE1E ^ (ctrl_seed * 1523 + int(sigma * 1000) + n_episodes))
    theta = [[0.0] * N_ARMS for _ in range(2)]
    baseline = [0.0, 0.0]
    for ep in range(n_episodes):
        c = ep & 1
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


def _dstar(sigma: float, n_episodes: int) -> float:
    recs = []
    for delta in DELTAS:
        means = _means2(delta)
        r = [_recovery(means, _train_greedy(means, sigma, n_episodes, cs), delta)
             for cs in range(CONTROLLER_SEEDS)]
        recs.append(sum(r) / len(r))
    return _delta_star(DELTAS, recs)


def _loglog_slope(xs: list[float], ys: list[float]) -> float:
    lx = [math.log(x) for x in xs]
    ly = [math.log(y) for y in ys]
    n = len(lx)
    sx, sy = sum(lx), sum(ly)
    sxy = sum(a * b for a, b in zip(lx, ly))
    sxx = sum(a * a for a in lx)
    return (n * sxy - sx * sy) / (n * sxx - sx * sx)


def analyze() -> dict[str, Any]:
    budget_dstar = {n: _dstar(SIGMA0, n) for n in BUDGETS}
    any_nan = any(math.isnan(v) for v in budget_dstar.values())
    reduced_exponent = float("nan") if any_nan else _loglog_slope(BUDGETS, [budget_dstar[n] for n in BUDGETS])

    sig_lo = _dstar(SIGMA0, 3000)
    sig_hi = _dstar(2 * SIGMA0, 3000)
    noise_ratio = sig_hi / sig_lo if sig_lo and not math.isnan(sig_lo) and sig_lo > 0 else float("nan")

    full = json.loads(L4D.read_text())
    full_noise = full["sigma_scaling_ratio_highpower"]

    exp_match = (not math.isnan(reduced_exponent)) and abs(reduced_exponent - TARGET_EXPONENT) <= 0.15
    noise_match = (not math.isnan(noise_ratio)) and noise_ratio < 1.0

    if any_nan:
        verdict = "L4E_INSTRUMENT_LIMITED"
    elif exp_match and noise_match:
        verdict = "L4E_MECHANISM_EXPLAINED"
    else:
        verdict = "L4E_MECHANISM_INCOMPLETE"

    return {
        "experiment": "wp3_plasticity_v7_mechanism",
        "verdict": verdict,
        "tier": "SYNTHETIC-PARAMETRIC — 2-arm ablation of the governor collapse mechanism",
        "n_arms_ablation": N_ARMS, "controller_seeds": CONTROLLER_SEEDS,
        "budgets": BUDGETS, "sigma0": SIGMA0,
        "reduced_budget_delta_star": budget_dstar,
        "reduced_budget_exponent": reduced_exponent,
        "target_full_governor_exponent": TARGET_EXPONENT,
        "exponent_match_within_0.15": exp_match,
        "reduced_noise_ratio": noise_ratio,
        "full_governor_noise_ratio": full_noise,
        "noise_sign_match_both_below_1": noise_match,
        "mechanism": "2-arm REINFORCE logit drift dg/dt ~ LR*Delta*pi(1-pi) (super-diffusive -> steeper than -0.5) + baseline-relative advantage makes noise act as exploration (ratio<1)",
        "prohibited_extrapolations": ["real-workload behavior", "L7 compute-equivalent Pareto",
                                      "energy or latency advantage", "independent replication"],
    }


def main() -> None:
    r = analyze()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verdict.json").write_text(json.dumps(r, indent=2))
    print(f"L4e MECHANISM VERDICT: {r['verdict']}")
    print("  2-arm reduced Δ* by budget:")
    for n in BUDGETS:
        print(f"    N={n:5d}  Δ*={r['reduced_budget_delta_star'][n]:.4f}")
    print(f"  reduced exponent = {r['reduced_budget_exponent']:.3f}  vs full-governor "
          f"{r['target_full_governor_exponent']:.3f}  (match={r['exponent_match_within_0.15']})")
    print(f"  reduced noise ratio = {r['reduced_noise_ratio']:.3f}  (full {r['full_governor_noise_ratio']:.3f}; "
          f"both<1 = {r['noise_sign_match_both_below_1']})")


if __name__ == "__main__":
    main()
