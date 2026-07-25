"""WP17 metrology tests: the arithmetic and the frozen decision rules, not the host-dependent timings."""
from __future__ import annotations

import json
from pathlib import Path

from experiments.wp17_metrology.src.metrology import (
    ADVANTAGE_SURVIVE,
    analytic_flops,
    pareto_with_route_cost,
    router_analytic_flops,
    tabular_controller_flops,
)

ROOT = Path(__file__).resolve().parents[3]
VERDICT = ROOT / "artifacts/wp17-metrology/verdict.json"


def test_ledger_scales_linearly_in_k() -> None:
    """K iterations of a weight-tied block must cost exactly K times the per-iteration term."""
    a1, a2, a3 = (analytic_flops(k)["linear_only"] for k in (1, 2, 3))
    assert a2 - a1 == a3 - a2 > 0


def test_attention_core_is_the_profiler_gap() -> None:
    """The ledger's attention term is exactly what a with_flops profiler cannot see."""
    a = analytic_flops(2)
    assert a["matmul"] == a["linear_only"] + a["attention_core"]
    assert a["attention_core"] > 0


def test_router_costs_less_than_one_model_iteration() -> None:
    """A mean-pooled linear router must be cheap relative to a full block iteration."""
    assert 0 < router_analytic_flops(3) < analytic_flops(1)["total"]
    assert 0 < tabular_controller_flops(3) < router_analytic_flops(3)


def test_kill_test_rule_is_monotone_and_can_actually_kill() -> None:
    """The frozen Q3 rule must be able to reach every verdict -- a test that cannot fail is useless.

    Charging a large enough route cost MUST flip the WP15 positive; otherwise the kill-test is
    ceremonial.
    """
    cheap = pareto_with_route_cost(0.0)
    assert cheap["kill_test_verdict"] == "PARETO_SURVIVES_PHYSICAL_ROUTE_COST"
    # inside the measured frontier a bigger route cost must strictly reduce the advantage
    inside = pareto_with_route_cost(0.9)
    assert inside["advantage"] < cheap["advantage"]
    # beyond the measured frontier the comparison must refuse to conclude, not silently clamp
    beyond = pareto_with_route_cost(5.0)
    assert beyond["kill_test_verdict"] == "PARETO_NOT_IDENTIFIED_BEYOND_MEASURED_FRONTIER"


def test_threshold_matches_preregistration() -> None:
    assert ADVANTAGE_SURVIVE == 0.05


def test_recorded_verdict_is_internally_consistent() -> None:
    assert VERDICT.is_file(), "required frozen verdict is missing"
    v = json.loads(VERDICT.read_text())
    # ledger validated like-for-like at every operating point
    assert all(q["pass"] for q in v["q1_flop_ledger_vs_profiler"])
    # energy must never be reported available on a host without a validated meter
    assert v["q6_energy"]["pass"] is True
    assert v["q6_energy"]["energy_available"] is False
    # the recorded kill-test verdict must be one of the three preregistered tokens
    assert v["q3_wp15_kill_test"]["kill_test_verdict"] in {
        "PARETO_SURVIVES_PHYSICAL_ROUTE_COST", "PARETO_NARROWED_BY_ROUTE_COST",
        "PARETO_KILLED_BY_ROUTE_COST", "PARETO_NOT_IDENTIFIED_BEYOND_MEASURED_FRONTIER"}
