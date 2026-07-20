"""Act-J identifiability pilot — the decision instrument.

Applies the calibrated pilot certificate
(`experiments/common/identifiability_inference.py`) to the lab's real local data to
decide, with a bounded false-positive rate, whether the cost-budget plasticity
mechanism is identifiable enough to warrant a confirmatory (L4) run.

Deterministic: real frozen data + a closed-form certificate. See PREREGISTRATION.md
for the frozen decision rule. This pilot decides L4 GO/NO-GO ONLY; it does NOT and
cannot green-light L7 (no trained checkpoint, no compute-Pareto, no learned
controller).
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from experiments.common.identifiability_inference import (
    falsify_inference,
    gap_lower_confidence_bound,
    plugin_gap,
    sample_complexity,
)

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "artifacts/wp3-plasticity-v1/oracle-gap/raw_runs"
OUT = ROOT / "artifacts/act-j-pilot-decision"

GROUPS = ["attn", "mlp", "head", "embed"]
TASKS = ["lexical", "relational"]
LAMBDAS = [0.0, 0.5, 1.0, 2.0]
DELTA = 0.05
DELTA_EFF = DELTA / len(LAMBDAS)  # Bonferroni over the post-hoc lambda grid
N_SEEDS = 5
OPERATING_LAMBDA = 1.0
C_ROUTE = 0.0  # given-task regime: task identity observed => route is a table lookup


def load_runs() -> list[dict[str, Any]]:
    return [json.loads((RAW / f"seed{s}.json").read_text()) for s in range(N_SEEDS)]


def _var(vals: list[float]) -> float:
    if len(vals) < 2:
        return 0.0
    mean = sum(vals) / len(vals)
    return sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)


def cell_stats(runs: list[dict[str, Any]], lam: float) -> tuple[list[list[float]], float, float]:
    """Return (Uhat[t][a], max_std_error, max_sigma) for the cost-budget utility."""
    cost = {a: runs[0]["tasks"][TASKS[0]][a]["cost_params"] for a in GROUPS}
    kmax = max(cost.values())
    uhat: list[list[float]] = []
    max_se = 0.0
    max_sigma = 0.0
    for t in TASKS:
        row: list[float] = []
        for a in GROUPS:
            vals = [r["tasks"][t][a]["new_acc"] - lam * cost[a] / kmax for r in runs]
            row.append(sum(vals) / len(vals))
            sigma = math.sqrt(_var(vals))
            max_sigma = max(max_sigma, sigma)
            max_se = max(max_se, sigma / math.sqrt(len(vals)))
        uhat.append(row)
    return uhat, max_se, max_sigma


def certify(uhat: list[list[float]], std_error: float, sigma: float, label: str) -> dict[str, Any]:
    n_c, n_a = len(uhat), len(uhat[0])
    ghat = plugin_gap(uhat)
    glo = gap_lower_confidence_bound(ghat, std_error, n_c, n_a, DELTA_EFF)
    nstar = sample_complexity(ghat, sigma, n_c, n_a, DELTA_EFF) if ghat > 0 and sigma > 0 else None
    return {
        "label": label,
        "gap_hat": ghat,
        "std_error": std_error,
        "sigma": sigma,
        "n_contexts": n_c,
        "n_actions": n_a,
        "delta_eff": DELTA_EFF,
        "gap_lower_bound": glo,
        "identifiable": glo > 0.0,
        "route_cost_headroom": glo,
        "sample_complexity_nstar": nstar,
    }


def run() -> dict[str, Any]:
    runs = load_runs()

    # Primary candidate: cost-budget plasticity at the operating lambda.
    u_primary, se_primary, sigma_primary = cell_stats(runs, OPERATING_LAMBDA)
    primary = certify(u_primary, se_primary, sigma_primary, f"plasticity_cost_budget_lambda_{OPERATING_LAMBDA}")

    # lambda sweep (transparency): G_lo at each grid point, same delta_eff.
    sweep = []
    for lam in LAMBDAS:
        u, se, sig = cell_stats(runs, lam)
        c = certify(u, se, sig, f"lambda_{lam}")
        sweep.append({"lambda": lam, "gap_hat": c["gap_hat"], "gap_lower_bound": c["gap_lower_bound"],
                      "identifiable": c["identifiable"]})

    # NEGATIVE control A: unconstrained plasticity (lambda=0) — weak interaction.
    u_neg_a, se_neg_a, sig_neg_a = cell_stats(runs, 0.0)
    neg_a = certify(u_neg_a, se_neg_a, sig_neg_a, "NEG_A_weak_interaction_lambda0")

    # NEGATIVE control B: routing-v2 quality matrix — unconstrained quality dominance.
    # Evaluated at the primary pilot's noise level (like-for-like).
    routing_q = [[1.00, 1.00], [0.004, 1.00]]
    neg_b = certify(routing_q, se_primary, sigma_primary, "NEG_B_quality_dominance_routing")

    # POSITIVE control: anti-diagonal specialization at the primary pilot's noise level.
    pos = certify([[1.0, 0.0], [0.0, 1.0]], se_primary, sigma_primary, "POS_specialization")

    # Certificate self-falsification (the instrument must be trustworthy).
    falsify = falsify_inference()

    controls_ok = (
        (not neg_a["identifiable"])
        and (not neg_b["identifiable"])
        and pos["identifiable"]
        and bool(falsify["all_ok"])
    )
    go = primary["gap_lower_bound"] > C_ROUTE

    if not controls_ok:
        verdict = "PILOT_VOID"
    elif go:
        verdict = "PILOT_GO_L4_CONFIRMATORY"
    else:
        verdict = "PILOT_NOGO"

    return {
        "experiment": "act_j_pilot_decision",
        "verdict": verdict,
        "decides": "L4 cost-aware plasticity confirmatory run GO/NO-GO",
        "does_not_decide": ["L7 compute-Pareto", "learned controller", "real-workload", "energy/latency"],
        "delta": DELTA,
        "delta_eff_bonferroni_over_lambda_grid": DELTA_EFF,
        "operating_lambda": OPERATING_LAMBDA,
        "c_route": C_ROUTE,
        "c_route_regime": "given-task (task identity observed => route is a lookup)",
        "primary": primary,
        "route_cost_headroom": primary["route_cost_headroom"],
        "lambda_sweep": sweep,
        "controls": {"negative_A": neg_a, "negative_B": neg_b, "positive": pos, "controls_ok": controls_ok},
        "certificate_self_falsification": falsify,
        "prohibited_extrapolations": [
            "L7 compute-equivalent Pareto", "energy or latency advantage",
            "learned allocator", "real-workload generalization", "independent replication",
        ],
    }


def main() -> None:
    result = run()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verdict.json").write_text(json.dumps(result, indent=2))
    print(f"ACT-J PILOT VERDICT: {result['verdict']}")
    p = result["primary"]
    print(f"  primary Ĝ={p['gap_hat']:.4f}  G_lo={p['gap_lower_bound']:.4f}  "
          f"(δ_eff={DELTA_EFF}, |C|={p['n_contexts']}, |A|={p['n_actions']}, se={p['std_error']:.4g})")
    print(f"  route-cost headroom = {result['route_cost_headroom']:.4f}  (c_route={C_ROUTE})")
    c = result["controls"]
    print(f"  controls: NEG_A id={c['negative_A']['identifiable']}  "
          f"NEG_B id={c['negative_B']['identifiable']}  POS id={c['positive']['identifiable']}  "
          f"falsify_ok={result['certificate_self_falsification']['all_ok']}  => controls_ok={c['controls_ok']}")


if __name__ == "__main__":
    main()
