import math
import pytest

from cwc.governance.product_economics import (
    ProductTrialCost,
    ProductTrialOutcome,
    certify_product_economics,
    cps_improvement,
    net_saving,
)


def _cost(total: float) -> ProductTrialCost:
    return ProductTrialCost(
        model_usd=total,
        router_usd=0,
        countermodel_usd=0,
        retrieval_usd=0,
        tools_usd=0,
        verification_usd=0,
        human_review_usd=0,
        infra_usd=0,
        retry_usd=0,
        failure_loss_usd=0,
    )


def _trial(trial: str, task: str, policy: str, total: float, *, accepted=True, quality=True, regret=True, coverage=True):
    return ProductTrialOutcome(
        trial_id=trial,
        task_id=task,
        policy_id=policy,
        cost=_cost(total),
        accepted_success=accepted,
        quality_gate_passed=quality,
        catastrophic_regret_gate_passed=regret,
        coverage_gate_passed=coverage,
    )


def test_cps_uses_full_operational_cost_and_only_accepted_successes():
    trials = [
        _trial("a-0", "a", "DGC", 3.0),
        _trial("b-0", "b", "DGC", 2.0, quality=False),
    ]
    cert = certify_product_economics(trials, expected_task_ids=("a", "b"))
    assert cert.trials == 2
    assert cert.tasks_observed == 2
    assert cert.accepted_successes == 1
    assert cert.total_operational_usd == 5.0
    assert cert.cost_per_accepted_success_usd == 5.0
    assert cert.full_task_coverage


def test_multiple_stochastic_trials_per_task_are_supported():
    trials = [
        _trial("a-0", "a", "DGC", 1.0),
        _trial("a-1", "a", "DGC", 1.0),
        _trial("b-0", "b", "DGC", 1.0),
        _trial("b-1", "b", "DGC", 1.0),
    ]
    cert = certify_product_economics(trials, expected_task_ids=("a", "b"))
    assert cert.trials == 4
    assert cert.trial_counts_by_task == (("a", 2), ("b", 2))


def test_missing_expected_task_is_not_falsely_full_coverage():
    cert = certify_product_economics(
        [_trial("a-0", "a", "DGC", 1.0)], expected_task_ids=("a", "b")
    )
    assert cert.task_coverage_fraction == 0.5
    assert not cert.full_task_coverage


def test_zero_accepted_successes_has_infinite_cps():
    cert = certify_product_economics(
        [_trial("a-0", "a", "DGC", 1.0, accepted=False)], expected_task_ids=("a",)
    )
    assert cert.accepted_successes == 0
    assert math.isinf(cert.cost_per_accepted_success_usd)


def test_hidden_human_and_infra_costs_are_counted():
    cost = ProductTrialCost(1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
    assert cost.total_operational_usd == 55.0


def test_net_saving_requires_identical_paired_trial_population():
    baseline = certify_product_economics(
        [_trial("a-0", "a", "B", 10.0)], expected_task_ids=("a",)
    )
    candidate = certify_product_economics(
        [_trial("a-1", "a", "DGC", 7.0)], expected_task_ids=("a",)
    )
    with pytest.raises(ValueError):
        net_saving(
            baseline,
            candidate,
            quality_noninferiority_certified=True,
            catastrophic_regret_noninferiority_certified=True,
            coverage_equivalence_certified=True,
        )


def test_net_saving_requires_independent_quality_regret_coverage_authority():
    baseline = certify_product_economics(
        [_trial("a-0", "a", "B", 10.0)], expected_task_ids=("a",)
    )
    candidate = certify_product_economics(
        [_trial("a-0", "a", "DGC", 7.0)], expected_task_ids=("a",)
    )
    with pytest.raises(ValueError):
        net_saving(
            baseline,
            candidate,
            quality_noninferiority_certified=False,
            catastrophic_regret_noninferiority_certified=True,
            coverage_equivalence_certified=True,
        )


def test_net_saving_and_cps_improvement_for_valid_paired_population():
    baseline = certify_product_economics(
        [_trial("a-0", "a", "B", 10.0), _trial("b-0", "b", "B", 10.0)],
        expected_task_ids=("a", "b"),
    )
    candidate = certify_product_economics(
        [_trial("a-0", "a", "DGC", 7.0), _trial("b-0", "b", "DGC", 7.0)],
        expected_task_ids=("a", "b"),
    )
    assert net_saving(
        baseline,
        candidate,
        quality_noninferiority_certified=True,
        catastrophic_regret_noninferiority_certified=True,
        coverage_equivalence_certified=True,
    ) == pytest.approx(0.3)
    assert cps_improvement(baseline, candidate) == pytest.approx(0.3)


def test_duplicate_trial_id_fails_closed():
    with pytest.raises(ValueError):
        certify_product_economics(
            [_trial("x", "a", "DGC", 1), _trial("x", "a", "DGC", 1)],
            expected_task_ids=("a",),
        )


def test_invalid_cost_fails_closed():
    with pytest.raises(ValueError):
        ProductTrialCost(-1, 0, 0, 0, 0, 0, 0, 0, 0, 0)
