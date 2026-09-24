from __future__ import annotations

import math
import pytest

from cwc.governance.causal_obligations import IdentifiabilityStatus, certify_declared_interventional_query
from cwc.governance.metareasoning_gap_v2 import perfect_information_myopic_gap_bound
from cwc.governance.drift_contract_v2 import bounded_drift_current_mean_lcb
from cwc.governance.restricted_sampling import certify_restricted_adaptive_policy


def test_bounded_drift_reduces_stationary_lcb_exactly_by_average_envelope() -> None:
    result = bounded_drift_current_mean_lcb([0.7, 0.8, 0.9, 0.8], lower=0.0, upper=1.0, delta=0.05, drift_to_current=[0.02, 0.03, 0.01, 0.02])
    assert math.isclose(result.average_drift_budget, 0.02)
    assert math.isclose(result.current_mean_lower, max(0.0, result.stationary_lower - 0.02))


def test_zero_drift_recovers_stationary_bound() -> None:
    result = bounded_drift_current_mean_lcb([0.5] * 20, lower=0, upper=1, delta=0.1, drift_to_current=[0.0] * 20)
    assert result.current_mean_lower == result.stationary_lower


def test_drift_contract_rejects_posthoc_shape_mismatch_and_negative_budget() -> None:
    with pytest.raises(ValueError):
        bounded_drift_current_mean_lcb([0.5], lower=0, upper=1, delta=0.1, drift_to_current=[])
    with pytest.raises(ValueError):
        bounded_drift_current_mean_lcb([0.5], lower=0, upper=1, delta=0.1, drift_to_current=[-0.1])


def test_perfect_information_gap_can_certify_global_stop() -> None:
    cert = perfect_information_myopic_gap_bound(current_action_regrets=[0.0, 0.2, 0.5], probability_upper_expectation=0.08, minimum_future_compute_cost=0.1, myopic_value=0.0)
    assert cert.global_net_upper == pytest.approx(-0.02)
    assert cert.globally_stop_certified is True
    assert cert.worst_case_suboptimality_upper == 0.0


def test_perfect_information_gap_exposes_possible_myopic_error() -> None:
    cert = perfect_information_myopic_gap_bound(current_action_regrets=[0.0, 0.5, 1.0], probability_upper_expectation=0.9, minimum_future_compute_cost=0.1, myopic_value=-0.2)
    assert cert.global_net_upper == pytest.approx(0.8)
    assert cert.worst_case_suboptimality_upper == pytest.approx(1.0)
    assert cert.globally_stop_certified is False


def test_gap_rejects_impossible_evpi_upper() -> None:
    with pytest.raises(ValueError):
        perfect_information_myopic_gap_bound(current_action_regrets=[0.0, 0.2], probability_upper_expectation=0.3, minimum_future_compute_cost=0.0, myopic_value=0.0)


def test_restricted_sampling_policy_derives_importance_weight_cap() -> None:
    p = certify_restricted_adaptive_policy(target_distribution={"a": 0.6, "b": 0.4}, minimum_propensity=0.2)
    assert p.max_importance_weight == pytest.approx(3.0)
    assert len(p.policy_digest) == 64


def test_restricted_sampling_rejects_infeasible_propensity_floor() -> None:
    with pytest.raises(ValueError):
        certify_restricted_adaptive_policy(target_distribution={"a": 0.5, "b": 0.5}, minimum_propensity=0.6)


def test_restricted_sampling_rejects_non_normalized_target() -> None:
    with pytest.raises(ValueError):
        certify_restricted_adaptive_policy(target_distribution={"a": 0.7, "b": 0.7}, minimum_propensity=0.1)


def test_causal_obligations_fail_closed_without_structural_authority() -> None:
    cert = certify_declared_interventional_query(structural_model_digest=None, intervention_declared=True, outcome_mapping_declared=True, no_hidden_confounding_asserted=True, transport_required=False, transport_assumptions_declared=False)
    assert cert.status is IdentifiabilityStatus.NOT_IDENTIFIED


def test_causal_obligations_require_transport_assumptions_when_transporting() -> None:
    cert = certify_declared_interventional_query(structural_model_digest="abc", intervention_declared=True, outcome_mapping_declared=True, no_hidden_confounding_asserted=True, transport_required=True, transport_assumptions_declared=False)
    assert cert.status is IdentifiabilityStatus.NOT_IDENTIFIED


def test_causal_obligations_certify_only_declared_query() -> None:
    cert = certify_declared_interventional_query(structural_model_digest="abc", intervention_declared=True, outcome_mapping_declared=True, no_hidden_confounding_asserted=True, transport_required=True, transport_assumptions_declared=True)
    assert cert.status is IdentifiabilityStatus.CERTIFIED_FOR_DECLARED_QUERY
