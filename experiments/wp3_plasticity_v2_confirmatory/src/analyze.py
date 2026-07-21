"""L4 plasticity cost-budget CONFIRMATORY analysis.

Reads the fresh held-out raw runs (seeds 5..20, disjoint from the exploratory 0..4),
applies the frozen cost-budget utility at lambda=1, and certifies the oracle gap
out-of-sample with the calibrated pilot certificate at delta=0.05 (no selection
correction — lambda is frozen a priori). See PREREGISTRATION.md.

Deterministic given the raw runs. Verdict per the preregistered decision rule.
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
RAW = ROOT / "artifacts/wp3-plasticity-v2-confirmatory/raw_runs"
OUT = ROOT / "artifacts/wp3-plasticity-v2-confirmatory"

GROUPS = ["attn", "mlp", "head", "embed"]
TASKS = ["lexical", "relational"]
LAMBDA = 1.0          # FROZEN a priori
DELTA = 0.05          # no selection correction — lambda not swept here
C_ROUTE = 0.0


def _load(seeds: list[int]) -> list[dict[str, Any]]:
    return [json.loads((RAW / f"seed{s}.json").read_text()) for s in seeds]


def _u_lambda(run: dict[str, Any], lam: float) -> list[list[float]]:
    cost = {a: run["tasks"][TASKS[0]][a]["cost_params"] for a in GROUPS}
    kmax = max(cost.values())
    return [[run["tasks"][t][a]["new_acc"] - lam * cost[a] / kmax for a in GROUPS] for t in TASKS]


def _per_seed_gap(u: list[list[float]]) -> float:
    n_t, n_a = len(u), len(u[0])
    v_oracle = sum(max(u[t]) for t in range(n_t)) / n_t
    v_fixed = max(sum(u[t][a] for t in range(n_t)) / n_t for a in range(n_a))
    return v_oracle - v_fixed


def _var(vals: list[float]) -> float:
    if len(vals) < 2:
        return 0.0
    m = sum(vals) / len(vals)
    return sum((v - m) ** 2 for v in vals) / (len(vals) - 1)


def _aggregate(runs: list[dict[str, Any]], lam: float) -> tuple[list[list[float]], float, float]:
    n = len(runs)
    per = [_u_lambda(r, lam) for r in runs]
    uhat: list[list[float]] = []
    max_se = max_sigma = 0.0
    for ti in range(len(TASKS)):
        row = []
        for ai in range(len(GROUPS)):
            vals = [per[s][ti][ai] for s in range(n)]
            row.append(sum(vals) / n)
            sigma = math.sqrt(_var(vals))
            max_sigma = max(max_sigma, sigma)
            max_se = max(max_se, sigma / math.sqrt(n))
        uhat.append(row)
    return uhat, max_se, max_sigma


def _certify(uhat: list[list[float]], std_error: float, sigma: float, label: str) -> dict[str, Any]:
    n_c, n_a = len(uhat), len(uhat[0])
    ghat = plugin_gap(uhat)
    glo = gap_lower_confidence_bound(ghat, std_error, n_c, n_a, DELTA)
    nstar = sample_complexity(ghat, sigma, n_c, n_a, DELTA) if ghat > 0 and sigma > 0 else None
    return {"label": label, "gap_hat": ghat, "std_error": std_error, "sigma": sigma,
            "gap_lower_bound": glo, "identifiable": glo > 0.0, "sample_complexity_nstar": nstar}


def analyze(seeds: list[int]) -> dict[str, Any]:
    runs = _load(seeds)
    per_seed = [_per_seed_gap(_u_lambda(r, LAMBDA)) for r in runs]
    worst = min(per_seed)
    frac_pos = sum(1 for g in per_seed if g > 0) / len(per_seed)

    uhat, se, sigma = _aggregate(runs, LAMBDA)
    primary = _certify(uhat, se, sigma, f"plasticity_cost_budget_lambda_{LAMBDA}_heldout")

    u0, se0, sigma0 = _aggregate(runs, 0.0)
    neg_a = _certify(u0, se0, sigma0, "NEG_A_weak_interaction_lambda0")
    neg_b = _certify([[1.00, 1.00], [0.004, 1.00]], se, sigma, "NEG_B_quality_dominance_routing")
    pos = _certify([[1.0, 0.0], [0.0, 1.0]], se, sigma, "POS_specialization")
    falsify = falsify_inference()

    controls_ok = (not neg_a["identifiable"]) and (not neg_b["identifiable"]) \
        and pos["identifiable"] and bool(falsify["all_ok"])
    primary_ok = primary["gap_lower_bound"] > C_ROUTE

    if not controls_ok:
        verdict = "L4_VOID"
    elif not primary_ok:
        verdict = "L4_NOT_CONFIRMED"
    elif worst > 0.0:
        verdict = "L4_IDENTIFIABLE_CONFIRMED_SYNTHETIC"
    else:
        verdict = "L4_IDENTIFIABLE_CONFIRMED_WEAK"

    return {
        "experiment": "wp3_plasticity_v2_confirmatory",
        "verdict": verdict,
        "tier": "SYNTHETIC (toy GroupedModel, oracle, no learned controller)",
        "held_out_seeds": seeds,
        "n_seeds": len(seeds),
        "lambda_frozen": LAMBDA,
        "delta": DELTA,
        "c_route": C_ROUTE,
        "primary": primary,
        "route_cost_headroom": primary["gap_lower_bound"],
        "per_seed_gaps": per_seed,
        "worst_seed_gap": worst,
        "fraction_seeds_positive": frac_pos,
        "controls": {"negative_A": neg_a, "negative_B": neg_b, "positive": pos, "controls_ok": controls_ok},
        "certificate_self_falsification": falsify,
        "prohibited_extrapolations": [
            "learned governor achieves it", "L7 compute-equivalent Pareto",
            "energy or latency advantage", "real-workload generalization", "independent replication",
        ],
    }


def main() -> None:
    seeds = list(range(5, 21))
    result = analyze(seeds)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verdict.json").write_text(json.dumps(result, indent=2))
    p = result["primary"]
    print(f"L4 CONFIRMATORY VERDICT: {result['verdict']}")
    print(f"  held-out seeds {seeds[0]}..{seeds[-1]} (n={result['n_seeds']})  lambda={LAMBDA} frozen")
    print(f"  aggregate Ĝ={p['gap_hat']:.4f}  G_lo={p['gap_lower_bound']:.4f}  (δ={DELTA}, se={p['std_error']:.4g})")
    print(f"  worst-seed gap={result['worst_seed_gap']:.4f}  frac_positive={result['fraction_seeds_positive']:.2f}")
    c = result["controls"]
    print(f"  controls: NEG_A={c['negative_A']['identifiable']} NEG_B={c['negative_B']['identifiable']} "
          f"POS={c['positive']['identifiable']} falsify={result['certificate_self_falsification']['all_ok']} "
          f"=> ok={c['controls_ok']}")


if __name__ == "__main__":
    main()
