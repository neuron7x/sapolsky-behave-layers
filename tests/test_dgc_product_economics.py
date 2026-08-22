import math
import pytest

from cwc.governance.product_economics import (
    ProductTrialCost,
    ProductTrialOutcome,
    certify_product_economics,
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


def _trial(task: str, policy: str, total: float, *, accepted=True, quality=True, regret=True, coverage=True):
    return ProductTrialOutcome(
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
        _trial("a", "DGC", 3.0),
        _trial("b", "DGC", 2.0, quality=False),
    ]
    cert = certify_product_economics(trials)
    assert cert.tasks == 2
    assert cert.accepted_successes == 1
    assert cert.total_operational_usd == 5.0
    assert cert.cost_per_accepted_success_usd == 5.0


def test_zero_accepted_successes_has_infinite_cps_not_fake_saving():
    cert = certify_product_economics([_trial("a", "DGC", 1.0, accepted=False)])
    assert cert.accepted_successes == 0
    assert math.isinf(cert.cost_per_accepted_success_usd)


def test_hidden_human_and_infra_costs_are_counted():
    cost = ProductTrialCost(1, 2, 3, 4, 5, 6, 7, 8, 9, 10)
    assert cost.total_operational_usd == 55.0


def test_net_saving_requires_equal_accepted_success_count():
    baseline = certify_product_economics([_trial("a", "B", 10.0)])
    candidate = certify_product_economics([_trial("a", "DGC", 1.0, quality=False)])
    with pytest.raises(ValueError):
        net_saving(baseline, candidate)


def test_net_saving_is_authorized_for_equal_success_population():
    baseline = certify_product_economics([_trial("a", "B", 10.0), _trial("b", "B", 10.0)])
    candidate = certify_product_economics([_trial("a", "DGC", 7.0), _trial("b", "DGC", 7.0)])
    assert net_saving(baseline, candidate) == pytest.approx(0.3)


def test_invalid_cost_fails_closed():
    with pytest.raises(ValueError):
        ProductTrialCost(-1, 0, 0, 0, 0, 0, 0, 0, 0, 0)
