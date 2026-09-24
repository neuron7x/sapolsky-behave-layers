from __future__ import annotations

import pytest

from cwc.governance.budget import BudgetLedger
from cwc.governance.compute_governor import ComputeGovernor
from cwc.governance.compute_value import estimate_voc
from cwc.governance.contracts import CandidateOperation, ComputeDirective, Perturbation, RiskClass
from cwc.governance.decision_gradient import estimate_decision_gradient


def _p(pid: str, weight: float = 1.0) -> Perturbation:
    return Perturbation(
        perturbation_id=pid,
        target_variable="x",
        baseline_value="0",
        perturbed_value="1",
        intervention_type="PARAMETER_SHIFT",
        provenance="synthetic:test",
        plausibility_weight=weight,
    )


def test_decision_gradient_zero_when_action_is_invariant() -> None:
    cert = estimate_decision_gradient(
        baseline_action="A",
        perturbations=[_p("p1"), _p("p2")],
        utility_evaluator=lambda _: {"A": 2.0, "B": 1.0},
        source_state_digest="state",
        utility_digest="utility",
    )
    assert cert.weighted_regret == 0
    assert cert.worst_case_regret == 0
    assert cert.decision_flip_count == 0


def test_decision_gradient_is_weighted_counterfactual_regret() -> None:
    values = {"p1": {"A": 0.0, "B": 4.0}, "p2": {"A": 3.0, "B": 1.0}}
    cert = estimate_decision_gradient(
        baseline_action="A",
        perturbations=[_p("p1", 1.0), _p("p2", 3.0)],
        utility_evaluator=lambda p: values[p.perturbation_id],
        source_state_digest="state",
        utility_digest="utility",
    )
    assert cert.weighted_regret == pytest.approx(1.0)
    assert cert.worst_case_regret == pytest.approx(4.0)
    assert cert.decision_flip_count == 1


def test_zero_total_weight_fails_closed() -> None:
    with pytest.raises(ValueError, match="positive total"):
        estimate_decision_gradient(
            baseline_action="A",
            perturbations=[_p("p1", 0.0)],
            utility_evaluator=lambda _: {"A": 1.0, "B": 0.0},
            source_state_digest="state",
            utility_digest="utility",
        )


def test_budget_cannot_self_raise_or_overspend() -> None:
    b = BudgetLedger(hard_tokens=10, hard_money=5, hard_time=3, reserved_emergency_money=1)
    assert b.can_spend(tokens=10, money=4, time=3)
    assert not b.can_spend(tokens=11)
    assert not b.can_spend(money=5)
    with pytest.raises(RuntimeError, match="HARD_BUDGET_EXCEEDED"):
        b.spend(tokens=11)


def test_governor_admits_only_positive_conservative_voc() -> None:
    budget = BudgetLedger(hard_tokens=100, hard_money=10, hard_time=10)
    op1 = CandidateOperation("cheap", ComputeDirective.LOCAL_PROBE, estimated_cost=1, token_cost=10)
    op2 = CandidateOperation("bad", ComputeDirective.EXTERNAL_MODEL, estimated_cost=5, token_cost=10)
    e1 = estimate_voc(operation_id="cheap", gross_value=3, total_cost=1, gross_lower=2, gross_upper=4, method="oracle-test")
    e2 = estimate_voc(operation_id="bad", gross_value=4, total_cost=5, gross_lower=3, gross_upper=6, method="oracle-test")
    decision = ComputeGovernor.select(
        operations=[op1, op2], estimates={"cheap": e1, "bad": e2}, budget=budget, decision_digest="d"
    )
    assert decision.operation_id == "cheap"
    assert decision.directive is ComputeDirective.LOCAL_PROBE


def test_governor_stops_when_lcb_is_not_positive() -> None:
    budget = BudgetLedger(hard_tokens=100, hard_money=10, hard_time=10)
    op = CandidateOperation("x", ComputeDirective.CRITIC, estimated_cost=2, token_cost=10)
    est = estimate_voc(operation_id="x", gross_value=2, total_cost=2, gross_lower=1.5, gross_upper=3, method="oracle-test")
    decision = ComputeGovernor.select(
        operations=[op], estimates={"x": est}, budget=budget, decision_digest="d", risk_class=RiskClass.NORMAL
    )
    assert decision.directive is ComputeDirective.STOP
    assert decision.operation_id is None
