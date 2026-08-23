from __future__ import annotations

import math

import pytest

from cwc.governance.adaptive_eprocess import AdaptiveImportanceSample, adaptive_importance_mean_eprocess
from cwc.governance.budget import BudgetLedger
from cwc.governance.calibration import fit_split_conformal_lower
from cwc.governance.compute_governor import ComputeGovernor
from cwc.governance.compute_value import VOCAuthority, ValueOfComputationEstimate, estimate_voc
from cwc.governance.contracts import CandidateOperation, ComputeDirective
from cwc.governance.decision_stability import certify_action_stability, certify_decision_irrelevant_suffix
from cwc.governance.pareto import certify_paired_pareto_improvement
from cwc.governance.robust_voc import RobustnessBudget, robust_voc_lower_bound, robustify_voc_estimate


def test_tv_robust_voc_bound_is_exact_on_two_state_extremum() -> None:
    # Nominal P=(0.5,0.5), gross regret G=(0,1), TV radius=.1.
    # Worst admissible Q=(0.6,0.4), so E_Q[G]=.4 exactly.
    out = robust_voc_lower_bound(
        nominal_gross_lower=0.5,
        nominal_cost=0.2,
        gross_lower_support=0.0,
        gross_upper_support=1.0,
        budget=RobustnessBudget(total_variation_radius=0.1),
    )
    assert out.distribution_shift_penalty == pytest.approx(0.1)
    assert out.robust_voc_lower == pytest.approx(0.2)


def test_utility_and_cost_misspecification_can_kill_nominal_positive_voc() -> None:
    out = robust_voc_lower_bound(
        nominal_gross_lower=0.35,
        nominal_cost=0.20,
        gross_lower_support=0.0,
        gross_upper_support=0.5,
        budget=RobustnessBudget(
            total_variation_radius=0.05,
            utility_sup_error=0.05,
            cost_underestimate=0.04,
        ),
    )
    assert out.nominal_voc_lower == pytest.approx(0.15)
    assert out.robust_voc_lower == pytest.approx(-0.015)
    assert not out.admitted


def test_governor_can_require_ambiguity_robust_authority() -> None:
    op = CandidateOperation("critic", ComputeDirective.CRITIC, 0.1, token_cost=1)
    nominal = estimate_voc(
        operation_id="critic", gross_value=0.3, total_cost=0.1,
        gross_lower=0.25, gross_upper=0.35, method="nominal",
    )
    budget = BudgetLedger(hard_tokens=10, hard_money=10, hard_time=10)
    denied = ComputeGovernor.select(
        operations=(op,), estimates={"critic": nominal}, budget=budget,
        decision_digest="d", require_robust_estimate=True,
    )
    assert denied.directive is ComputeDirective.STOP

    robust = robustify_voc_estimate(
        nominal, gross_lower_support=0.0, gross_upper_support=0.5,
        budget=RobustnessBudget(total_variation_radius=0.01),
    )
    assert robust.authority is VOCAuthority.ROBUST_AMBIGUITY_BOUND
    admitted = ComputeGovernor.select(
        operations=(op,), estimates={"critic": robust}, budget=budget,
        decision_digest="d", require_robust_estimate=True,
    )
    assert admitted.directive is ComputeDirective.CRITIC


def test_robust_action_margin_certifies_decision_irrelevant_suffix() -> None:
    worlds = (
        {"A": 1.0, "B": 0.5, "C": 0.0},
        {"A": 0.9, "B": 0.6, "C": 0.2},
    )
    stability = certify_action_stability(worlds, action="A", utility_sup_error=0.1)
    assert stability.nominal_min_margin == pytest.approx(0.3)
    assert stability.robust_min_margin == pytest.approx(0.1)
    assert stability.stable
    removable = certify_decision_irrelevant_suffix(
        baseline_total_cost=10.0, suffix_cost=4.0, stability=stability,
    )
    assert removable.certified_fraction == pytest.approx(0.4)


def test_unstable_action_gives_zero_certified_removable_fraction() -> None:
    stability = certify_action_stability(
        ({"A": 1.0, "B": 0.9},), action="A", utility_sup_error=0.06,
    )
    assert not stability.stable
    removable = certify_decision_irrelevant_suffix(
        baseline_total_cost=5.0, suffix_cost=2.0, stability=stability,
    )
    assert removable.certified_fraction == 0.0


def test_adaptive_ipw_eprocess_matches_closed_form_and_rejects_low_null() -> None:
    # Equal target strata, but the adaptive sampler over-selects high-value A.
    # IPW corrects that selection. Propensities are assumed fixed before outcome.
    samples = [
        AdaptiveImportanceSample("A", 1.0, 0.8),
        AdaptiveImportanceSample("B", 0.4, 0.2),
    ] * 200
    lambdas = [0.15] * len(samples)
    result = adaptive_importance_mean_eprocess(
        samples, target_distribution={"A": 0.5, "B": 0.5}, lower=0.0, upper=1.0, alpha=0.05,
        lambdas=lambdas, max_importance_weight=2.5, null_mean=0.3,
    )
    assert result.n == 400
    assert result.lower_confidence_bound > 0.3
    assert result.rejects


def test_adaptive_ipw_refuses_propensity_positivity_violation() -> None:
    sample = AdaptiveImportanceSample("A", 0.5, 0.1)  # target .5 -> weight=5
    with pytest.raises(ValueError, match="importance weight"):
        adaptive_importance_mean_eprocess(
            [sample], target_distribution={"A": 0.5, "B": 0.5}, lower=0.0, upper=1.0, alpha=0.05,
            lambdas=[0.1], max_importance_weight=4.0, null_mean=0.2,
        )


def test_split_conformal_lower_has_finite_sample_rank_contract() -> None:
    predictions = [0.0] * 99
    outcomes = [float(i) / 100.0 for i in range(1, 100)]
    cal = fit_split_conformal_lower(predictions=predictions, outcomes=outcomes, alpha=0.10)
    assert cal.calibration_size == 99
    assert cal.guaranteed_miscoverage_upper <= 0.10
    assert cal.residual_quantile == pytest.approx(0.10)
    assert cal.lower_bound(0.5) == pytest.approx(0.60)


def test_split_conformal_is_uninformative_when_sample_too_small() -> None:
    cal = fit_split_conformal_lower(predictions=[0.0], outcomes=[1.0], alpha=0.1)
    assert math.isinf(cal.residual_quantile) and cal.residual_quantile < 0


def test_paired_pareto_certificate_requires_simultaneous_cost_and_quality() -> None:
    cert = certify_paired_pareto_improvement(
        baseline_minus_dgc_cost=[0.4] * 1000,
        dgc_minus_baseline_quality=[0.0] * 1000,
        cost_gain_support=(0.0, 1.0),
        quality_gain_support=(0.0, 0.0),
        alpha=0.05,
    )
    assert cert.certified_cost_reduction
    assert cert.certified_quality_noninferiority
    assert cert.certified_pareto_improvement

    bad = certify_paired_pareto_improvement(
        baseline_minus_dgc_cost=[0.4] * 1000,
        dgc_minus_baseline_quality=[-0.1] * 1000,
        cost_gain_support=(0.0, 1.0),
        quality_gain_support=(-0.2, 0.2),
        alpha=0.05,
    )
    assert bad.certified_cost_reduction
    assert not bad.certified_quality_noninferiority
    assert not bad.certified_pareto_improvement

from cwc.governance.ambiguity import (
    certify_no_information_worth_cost,
    credal_expectation_interval,
    minimax_regret_action,
)


def test_credal_interval_solves_finite_probability_box_exactly() -> None:
    # p0 in [.2,.6], p1 in [.4,.8], p0+p1=1; values=(0,1).
    interval = credal_expectation_interval(
        [0.0, 1.0], probability_lower=[0.2, 0.4], probability_upper=[0.6, 0.8]
    )
    assert interval.lower == pytest.approx(0.4)
    assert interval.upper == pytest.approx(0.8)
    assert sum(interval.minimizing_distribution) == pytest.approx(1.0)
    assert sum(interval.maximizing_distribution) == pytest.approx(1.0)


def test_minimax_regret_does_not_require_probabilities() -> None:
    decision = minimax_regret_action(
        (
            {"A": 10.0, "B": 7.0, "C": 0.0},
            {"A": 0.0, "B": 7.0, "C": 10.0},
        )
    )
    assert decision.action == "B"
    assert decision.worst_case_regret == pytest.approx(3.0)


def test_perfect_information_upper_bound_can_certify_robust_stop() -> None:
    cert = certify_no_information_worth_cost(
        current_action_regrets=[0.0, 0.02, 0.04],
        probability_lower=[0.2, 0.2, 0.2],
        probability_upper=[0.6, 0.6, 0.6],
        minimum_compute_cost=0.04,
    )
    assert cert.max_plausible_evpi <= 0.04
    assert cert.stop_certified


def test_perfect_information_stop_refuses_when_some_plausible_prior_makes_info_valuable() -> None:
    cert = certify_no_information_worth_cost(
        current_action_regrets=[0.0, 0.02, 0.20],
        probability_lower=[0.2, 0.2, 0.2],
        probability_upper=[0.6, 0.6, 0.6],
        minimum_compute_cost=0.04,
    )
    assert cert.max_plausible_evpi > 0.04
    assert not cert.stop_certified

from cwc.governance.robust_voc import WassersteinRobustnessBudget, wasserstein_robust_voc_lower_bound


def test_wasserstein_lipschitz_voc_penalty_is_exact_on_two_point_shift() -> None:
    # Two worlds distance 1, g=(0,1), move .1 mass from high to low: W1=.1.
    # L=1, so the KR penalty .1 is attained exactly.
    value = wasserstein_robust_voc_lower_bound(
        nominal_gross_lower=0.5,
        nominal_cost=0.2,
        budget=WassersteinRobustnessBudget(radius=0.1, gross_lipschitz_constant=1.0),
    )
    assert value == pytest.approx(0.2)

from cwc.governance.risk_control import conformal_risk_control


def test_conformal_risk_control_uses_n_plus_one_correction() -> None:
    thresholds = [0.2, 0.5, 0.8]
    # 19 rows. At threshold .5 each row loss=.05: corrected=(.95+1)/20=.0975 <= .10.
    losses = [[0.2, 0.05, 0.0] for _ in range(19)]
    result = conformal_risk_control(
        thresholds=thresholds,
        losses_by_example=losses,
        risk_limit=0.10,
        loss_upper_bound=1.0,
        monotonicity_certified=True, terminal_safety_certified=True,
    )
    assert result.selected_threshold == pytest.approx(0.5)
    assert result.corrected_empirical_risk == pytest.approx(0.0975)


def test_conformal_risk_control_refuses_nonmonotone_posthoc_grid() -> None:
    with pytest.raises(ValueError, match="non-increasing"):
        conformal_risk_control(
            thresholds=[0.1, 0.2, 0.3],
            losses_by_example=[[0.2, 0.3, 0.0]],
            risk_limit=0.2,
            loss_upper_bound=1.0,
            monotonicity_certified=True, terminal_safety_certified=True,
        )


def test_adaptive_eprocess_refuses_non_normalized_target_distribution() -> None:
    with pytest.raises(ValueError, match="sum to 1"):
        adaptive_importance_mean_eprocess(
            [AdaptiveImportanceSample("A", 1.0, 0.5)],
            target_distribution={"A": 0.9}, lower=0.0, upper=1.0, alpha=0.05,
            lambdas=[0.1], max_importance_weight=2.0, null_mean=0.5,
        )


def test_conformal_risk_control_requires_external_contract_authority() -> None:
    with pytest.raises(ValueError, match="monotonicity"):
        conformal_risk_control(
            thresholds=[0.1, 0.2], losses_by_example=[[0.1, 0.0]],
            risk_limit=0.1, loss_upper_bound=1.0,
            monotonicity_certified=False, terminal_safety_certified=True,
        )

from cwc.governance.metareasoning import MetaOperation, MetaTransition, finite_horizon_meta_values, myopic_meta_values


def test_myopic_voc_can_miss_complementary_multistep_compute() -> None:
    decision_values = {"s0": 0.0, "s1": 0.0, "s2": 1.0}
    operations = {
        "s0": [MetaOperation("c1", 0.1, (MetaTransition("s1", 1.0),))],
        "s1": [MetaOperation("c2", 0.1, (MetaTransition("s2", 1.0),))],
    }
    myopic = myopic_meta_values(decision_values=decision_values, operations=operations)
    horizon2 = finite_horizon_meta_values(
        decision_values=decision_values, operations=operations, horizon=2
    )
    assert myopic["s0"].selected_operation is None  # c1 alone: -0.1
    assert horizon2["s0"].selected_operation == "c1"
    assert horizon2["s0"].value == pytest.approx(0.8)


def test_meta_bellman_never_values_compute_below_stop_value() -> None:
    values = finite_horizon_meta_values(
        decision_values={"s": 1.0},
        operations={"s": [MetaOperation("waste", 0.5, (MetaTransition("s", 1.0),))]},
        horizon=5,
    )
    assert values["s"].value == pytest.approx(1.0)
    assert values["s"].selected_operation is None


def test_voc_authority_coerces_valid_string_and_rejects_invalid_string() -> None:
    ok = ValueOfComputationEstimate(
        operation_id="x", gross_value=2.0, total_cost=1.0, voc=1.0,
        lower_bound=0.5, upper_bound=1.5, method="test", authority="MODEL_CONDITIONAL",
    )
    assert ok.authority is VOCAuthority.MODEL_CONDITIONAL
    with pytest.raises(ValueError):
        ValueOfComputationEstimate(
            operation_id="x", gross_value=2.0, total_cost=1.0, voc=1.0,
            lower_bound=0.5, upper_bound=1.5, method="test", authority="FAKE_AUTHORITY",
        )


def test_robustification_cannot_be_applied_twice() -> None:
    nominal = estimate_voc(
        operation_id="x", gross_value=1.0, total_cost=0.2, gross_lower=0.8, gross_upper=1.2, method="test"
    )
    once = robustify_voc_estimate(
        nominal, gross_lower_support=0.0, gross_upper_support=2.0, budget=RobustnessBudget(total_variation_radius=0.1)
    )
    with pytest.raises(ValueError, match="already ambiguity-robust"):
        robustify_voc_estimate(
            once, gross_lower_support=0.0, gross_upper_support=2.0, budget=RobustnessBudget(total_variation_radius=0.1)
        )
