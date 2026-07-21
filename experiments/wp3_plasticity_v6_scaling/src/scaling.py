"""L4d higher-power scaling revisit.

Settles the question L4c opened: is the governor's credit-assignment collapse margin
governed by the sample-complexity law? L4c falsified NOISE-scaling (confounded by REINFORCE
exploration). Here, at fixed noise, we scale the EPISODE BUDGET N to isolate the clean
prediction Delta* proportional to 1/sqrt(N); and re-test the noise-scaling at 24 seeds.
See PREREGISTRATION.md. Deterministic (Box-Muller over a fixed LCG).
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from experiments.common.identifiability_inference import _Rng
from experiments.wp3_plasticity_v5_thinmargin.src.thinmargin import _delta_star, _means, _recovery, _softmax

OUT = Path(__file__).resolve().parents[3] / "artifacts/wp3-plasticity-v6-scaling"

N_ARMS = 4
DELTAS = [0.40, 0.30, 0.20, 0.15, 0.10, 0.07, 0.05, 0.03, 0.02, 0.01, 0.005]
CONTROLLER_SEEDS = 24
BUDGETS = [1500, 3000, 6000, 12000]
SIGMA0 = 0.10
LR = 0.2


def _train_greedy(means: list[list[float]], sigma: float, n_episodes: int, ctrl_seed: int) -> list[int]:
    rng = _Rng(0xD00D ^ (ctrl_seed * 1409 + int(sigma * 1000) + n_episodes))
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


def _recovery_curve(sigma: float, n_episodes: int) -> list[float]:
    out = []
    for delta in DELTAS:
        means = _means(delta)
        r = [_recovery(means, _train_greedy(means, sigma, n_episodes, cs), delta)
             for cs in range(CONTROLLER_SEEDS)]
        out.append(sum(r) / len(r))
    return out


def analyze() -> dict[str, Any]:
    # P1 — budget scaling at fixed sigma
    budget_curves, budget_dstar = {}, {}
    for n in BUDGETS:
        recs = _recovery_curve(SIGMA0, n)
        budget_curves[f"N_{n}"] = [{"delta": d, "recovery": rr} for d, rr in zip(DELTAS, recs)]
        budget_dstar[f"N_{n}"] = _delta_star(DELTAS, recs)

    ds_lo = budget_dstar[f"N_{BUDGETS[0]}"]     # N=1500
    ds_hi = budget_dstar[f"N_{BUDGETS[-1]}"]    # N=12000
    budget_ratio = ds_hi / ds_lo if ds_lo and not math.isnan(ds_lo) and ds_lo > 0 else float("nan")
    dstar_seq = [budget_dstar[f"N_{n}"] for n in BUDGETS]
    monotone_decreasing = all(
        (math.isnan(dstar_seq[i]) or math.isnan(dstar_seq[i + 1]) or dstar_seq[i] >= dstar_seq[i + 1] - 0.01)
        for i in range(len(dstar_seq) - 1))
    predicted_ratio = 1.0 / math.sqrt(BUDGETS[-1] / BUDGETS[0])  # 1/sqrt(8)=0.354
    budget_confirmed = (not math.isnan(budget_ratio)) and monotone_decreasing and (0.25 <= budget_ratio <= 0.55)

    # P2 — sigma scaling re-test at high power, N=3000
    sig_lo = _delta_star(DELTAS, _recovery_curve(SIGMA0, 3000))
    sig_hi = _delta_star(DELTAS, _recovery_curve(2 * SIGMA0, 3000))
    sigma_ratio = sig_hi / sig_lo if sig_lo and not math.isnan(sig_lo) and sig_lo > 0 else float("nan")
    sigma_replicates_l4c = (not math.isnan(sigma_ratio)) and abs(sigma_ratio - 1.0) <= 0.4
    sigma_is_samplecomplexity = (not math.isnan(sigma_ratio)) and 1.4 <= sigma_ratio <= 2.8

    # A residual off-grid NaN is a measurement-range failure, NOT a scientific falsification.
    any_nan = any(math.isnan(dstar_seq[i]) for i in range(len(dstar_seq)))
    if budget_confirmed:
        verdict = "L4D_BUDGET_SCALING_CONFIRMED"
    elif any_nan:
        verdict = "L4D_INSTRUMENT_LIMITED"
    else:
        verdict = "L4D_BUDGET_SCALING_VIOLATED"

    return {
        "experiment": "wp3_plasticity_v6_scaling",
        "verdict": verdict,
        "tier": "SYNTHETIC-PARAMETRIC — governor credit-assignment scaling",
        "controller_seeds": CONTROLLER_SEEDS, "deltas": DELTAS, "budgets": BUDGETS, "sigma0": SIGMA0,
        "budget_curves": budget_curves,
        "budget_delta_star": budget_dstar,
        "budget_ratio_N12000_over_N1500": budget_ratio,
        "predicted_budget_ratio_1_over_sqrt8": predicted_ratio,
        "budget_monotone_decreasing": monotone_decreasing,
        "budget_scaling_confirmed": budget_confirmed,
        "sigma_scaling_ratio_highpower": sigma_ratio,
        "sigma_scaling_replicates_l4c": sigma_replicates_l4c,
        "sigma_scaling_is_samplecomplexity": sigma_is_samplecomplexity,
        "prohibited_extrapolations": ["real-workload behavior", "L7 compute-equivalent Pareto",
                                      "energy or latency advantage", "independent replication"],
    }


def main() -> None:
    r = analyze()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verdict.json").write_text(json.dumps(r, indent=2))
    print(f"L4d SCALING VERDICT: {r['verdict']}")
    print("  budget sweep (sigma=0.10):")
    for n in BUDGETS:
        print(f"    N={n:5d}  Δ*={r['budget_delta_star'][f'N_{n}']:.4f}")
    print(f"  Δ*(12000)/Δ*(1500) = {r['budget_ratio_N12000_over_N1500']:.3f}  "
          f"(predicted 1/√8 = {r['predicted_budget_ratio_1_over_sqrt8']:.3f}; "
          f"monotone={r['budget_monotone_decreasing']})")
    print(f"  σ re-test (24 seeds): Δ*(2σ)/Δ*(σ) = {r['sigma_scaling_ratio_highpower']:.3f}  "
          f"[replicates L4c={r['sigma_scaling_replicates_l4c']}, "
          f"sample-complexity={r['sigma_scaling_is_samplecomplexity']}]")


if __name__ == "__main__":
    main()
