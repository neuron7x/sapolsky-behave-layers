"""Conformance test for the Adaptive-Computation Admissibility Protocol spec v1.0.

A non-conforming build (any INV or guarantee failing) fails this test — the spec is
executable, not just prose. Also checks the §5 decision procedure returns the right
verdict on clear positive / null / malformed inputs.
"""
import math

import pytest

from experiments.common.admissibility_spec_conformance import (
    admissibility_decision,
    check_conformance,
)


def test_build_conforms_to_the_spec():
    report = check_conformance(quick=True)
    assert report["conforming"] is True
    for name, ok in report["invariants"].items():
        assert ok is True, name
    assert float(report["guarantees"]["G1 fpr_value"]) <= 0.1


def test_decision_admits_a_clear_positive():
    # a strongly identifiable benchmark with a tiny pilot noise, zero route cost
    u = [[1.0, 0.0], [0.0, 1.0]]
    d = admissibility_decision(u, [0.5, 0.5], [1.0, 1.0], std_error=0.02, route_cost=0.0, delta=0.05)
    assert d["decision"] == "ADMISSIBLE"
    assert float(d["gap_lower_bound"]) > 0.0


def test_decision_refuses_a_null_and_reports_sample_complexity():
    # additive (G=0) utility -> not certifiable; must return NOT_IDENTIFIABLE with n*
    u = [[a + b for b in (0.2, -0.1)] for a in (0.5, -0.3)]
    d = admissibility_decision(u, [0.5, 0.5], [1.0, 1.0], std_error=0.05, route_cost=0.0, delta=0.05)
    assert d["decision"] == "NOT_IDENTIFIABLE"
    assert int(d["n_star"]) > 0


def test_decision_is_inadmissible_when_route_cost_exceeds_value():
    u = [[1.0, 0.0], [0.0, 1.0]]
    d = admissibility_decision(u, [0.5, 0.5], [1.0, 1.0], std_error=0.02, route_cost=0.9, delta=0.05)
    assert d["decision"] == "INADMISSIBLE"


@pytest.mark.parametrize("kwargs", [
    {"route_cost": -0.1, "delta": 0.05, "std_error": 0.02},   # negative route cost
    {"route_cost": 0.0, "delta": 1.5, "std_error": 0.02},     # delta out of (0,1)
    {"route_cost": 0.0, "delta": 0.05, "std_error": -1.0},    # negative se
])
def test_decision_fails_closed_on_malformed_input(kwargs):
    d = admissibility_decision([[1.0, 0.0], [0.0, 1.0]], [0.5, 0.5], [1.0, 1.0], **kwargs)
    assert d["decision"] == "REJECT"


def test_landauer_floor_is_the_physical_route_cost_bound():
    # G3: the physical floor is positive and matches k_B T ln2
    from experiments.common.admissibility_spec_conformance import _K_B_T_LN2
    assert pytest.approx(1.380649e-23 * 310.15 * math.log(2), rel=1e-9) == _K_B_T_LN2
    assert _K_B_T_LN2 > 0.0
