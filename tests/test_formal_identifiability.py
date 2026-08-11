from __future__ import annotations

import math

import numpy as np
import pytest

from cwc.causal.observability import (
    finite_identifiability_certificate,
    local_first_order_identifiability,
    minimum_cost_separating_design,
    total_variation_distance,
)


def _family():
    return {
        "m0": {
            "observe": {0: 0.5, 1: 0.5},
            "do_x": {0: 0.9, 1: 0.1},
            "do_z": {0: 0.5, 1: 0.5},
        },
        "m1": {
            "observe": {0: 0.5, 1: 0.5},
            "do_x": {0: 0.1, 1: 0.9},
            "do_z": {0: 0.5, 1: 0.5},
        },
        "m2": {
            "observe": {0: 0.5, 1: 0.5},
            "do_x": {0: 0.9, 1: 0.1},
            "do_z": {0: 0.2, 1: 0.8},
        },
    }


def test_total_variation_exact():
    assert total_variation_distance({0: 1.0}, {1: 1.0}) == pytest.approx(1.0)
    assert total_variation_distance({0: 0.5, 1: 0.5}, {0: 0.5, 1: 0.5}) == 0.0


def test_observation_only_exposes_equivalence():
    cert = finite_identifiability_certificate(_family(), selected_actions=["observe"])
    assert cert.state == "NOT_IDENTIFIABLE_UNDER_DECLARED_CHANNEL"
    assert len(cert.unresolved_pairs) == 3
    assert cert.minimum_pair_separation == 0.0
    assert cert.causal_authority_granted is False


def test_interventions_separate_all_candidates():
    cert = finite_identifiability_certificate(_family(), selected_actions=["do_x", "do_z"])
    assert cert.state == "FINITE_IDENTIFIABLE_UNDER_DECLARED_CHANNEL"
    assert cert.unresolved_pairs == ()
    assert cert.minimum_pair_separation == pytest.approx(0.3)


def test_omitting_required_intervention_preserves_unresolved_pair():
    cert = finite_identifiability_certificate(_family(), selected_actions=["do_x"])
    assert cert.state == "NOT_IDENTIFIABLE_UNDER_DECLARED_CHANNEL"
    assert cert.unresolved_pairs == (("m0", "m2"),)


def test_minimum_cost_design_is_exact_not_greedy():
    design = minimum_cost_separating_design(
        _family(), costs={"observe": 0.1, "do_x": 2.0, "do_z": 1.0}
    )
    assert design.actions == ("do_x", "do_z")
    assert design.total_cost == pytest.approx(3.0)
    assert design.certificate.unresolved_pairs == ()


def test_duplicate_mechanism_is_not_identifiable_even_with_all_actions():
    family = _family()
    family["m3"] = {k: dict(v) for k, v in family["m0"].items()}
    design = minimum_cost_separating_design(
        family, costs={"observe": 1.0, "do_x": 1.0, "do_z": 1.0}
    )
    assert design.state == "NOT_IDENTIFIABLE_UNDER_DECLARED_CHANNEL"
    assert design.actions == ()
    assert ("m0", "m3") in design.certificate.unresolved_pairs


def test_probability_validation_fail_closed():
    bad = _family()
    bad["m0"]["do_x"] = {0: 0.8, 1: 0.8}
    with pytest.raises(ValueError, match="sum to 1"):
        finite_identifiability_certificate(bad)


def test_cost_validation_fail_closed():
    with pytest.raises(ValueError, match="costs"):
        minimum_cost_separating_design(
            _family(), costs={"observe": 1.0, "do_x": 0.0, "do_z": 1.0}
        )


def test_model_relabelling_does_not_change_separation_margin():
    family = _family()
    relabelled = {"z": family["m2"], "x": family["m0"], "y": family["m1"]}
    a = finite_identifiability_certificate(family, selected_actions=["do_x", "do_z"])
    b = finite_identifiability_certificate(relabelled, selected_actions=["do_x", "do_z"])
    assert a.state == b.state
    assert a.minimum_pair_separation == pytest.approx(b.minimum_pair_separation)


def test_full_column_rank_certifies_local_first_order_identifiability():
    cert = local_first_order_identifiability([[1.0, 0.0], [0.0, 2.0], [1.0, 1.0]])
    assert cert.state == "LOCAL_FIRST_ORDER_IDENTIFIABLE"
    assert cert.numerical_rank == 2
    assert cert.nullspace_basis == ()
    assert cert.smallest_singular_value > 0
    assert cert.causal_authority_granted is False


def test_rank_deficiency_returns_null_direction():
    cert = local_first_order_identifiability([[1.0, 2.0], [2.0, 4.0]])
    assert cert.state == "LOCAL_FIRST_ORDER_NOT_IDENTIFIABLE"
    assert cert.numerical_rank == 1
    assert len(cert.nullspace_basis) == 1
    v = np.asarray(cert.nullspace_basis[0])
    assert np.linalg.norm(np.asarray([[1.0, 2.0], [2.0, 4.0]]) @ v) < 1e-10


def test_nearly_singular_is_reported_as_ill_conditioned_not_silently_collapsed():
    cert = local_first_order_identifiability(
        [[1.0, 0.0], [0.0, 1e-10]], rank_tolerance=1e-14
    )
    assert cert.state == "LOCAL_FIRST_ORDER_IDENTIFIABLE"
    assert cert.condition_number == pytest.approx(1e10)
    assert cert.smallest_singular_value == pytest.approx(1e-10)


def test_covariance_information_diagnostics():
    cert = local_first_order_identifiability(
        [[1.0, 0.0], [0.0, 2.0]], covariance=[[4.0, 0.0], [0.0, 1.0]]
    )
    assert cert.information_min_eigenvalue == pytest.approx(0.25)
    assert cert.information_condition_number == pytest.approx(16.0)


def test_non_positive_definite_covariance_rejected():
    with pytest.raises(ValueError, match="positive definite"):
        local_first_order_identifiability(
            [[1.0, 0.0], [0.0, 1.0]], covariance=[[1.0, 0.0], [0.0, 0.0]]
        )


def test_rank_tolerance_can_fail_closed_on_weak_direction():
    cert = local_first_order_identifiability(
        [[1.0, 0.0], [0.0, 1e-10]], rank_tolerance=1e-9
    )
    assert cert.state == "LOCAL_FIRST_ORDER_NOT_IDENTIFIABLE"
    assert cert.numerical_rank == 1
    assert math.isfinite(cert.condition_number)
