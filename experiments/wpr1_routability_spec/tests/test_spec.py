"""WP-R1 tests: the screen must be derived, must bind, and must be able to fail."""
from __future__ import annotations

import json
from pathlib import Path

from experiments.wpr1_routability_spec.src.spec import (
    C_ROUTE,
    boundary_sweep,
    derive_kappa,
)

ROOT = Path(__file__).resolve().parents[3]
VERDICT = ROOT / "artifacts/wpr1-routability-spec/verdict.json"


def test_kappa_is_derived_and_exactly_linear_in_se() -> None:
    """If the correction were not linear in se, a single-constant screen would be invalid."""
    k = derive_kappa()
    assert k["linear_in_se"] is True
    assert 4.0 < k["kappa"] < 6.0


def test_boundary_sweep_actually_populates_the_threshold_band() -> None:
    """A sweep that never lands near the threshold cannot test the threshold VALUE.

    The first implementation put ZERO points in the band; this asserts the fixed grid does.
    """
    sw = boundary_sweep(41)
    assert sw["n_points_near_threshold"] >= 3
    assert sw["certificate_sign_changes"] >= 1


def test_predicted_threshold_lies_inside_the_certificate_flip_bracket() -> None:
    """The full condition (kappa + c_route/se), not kappa alone, must bracket the real flip."""
    sw = boundary_sweep(61)
    lo, hi = sw["flip_bracket_gap_over_se"]
    assert lo <= sw["predicted_threshold_gap_over_se"] <= hi


def test_the_screen_is_binding_not_vacuous() -> None:
    """A screen that passes everything is useless: the sweep must contain both verdicts."""
    sw = boundary_sweep(41)
    verdicts = {p["predicted"] for p in sw["points"]}
    assert verdicts == {True, False}


def test_recorded_verdict_matches_the_frozen_decision_rule() -> None:
    assert VERDICT.is_file(), "required frozen verdict is missing"
    v = json.loads(VERDICT.read_text())
    total = v["mismatches"] + v["boundary_sweep"]["mismatches"]
    assert v["verdict"] == ("SPEC_PREDICTS_CERTIFICATE" if total == 0 else "SPEC_REFUTED")
    # every frozen bundle must be present -- no post-hoc exclusions
    assert v["n_cases"] == 7
    assert v["c_route_measured_wp17"] == C_ROUTE
    assert "L7" in v["prohibited_extrapolations"]
