from __future__ import annotations

import json
from dataclasses import replace
from fractions import Fraction
from itertools import permutations
from sys import float_info

import pytest

from cwc.governance.budget import BudgetLedger
from cwc.governance.compute_governor import ComputeGovernor
from cwc.governance.compute_value import estimate_voc
from cwc.governance.contracts import (
    CandidateOperation,
    ComputeDirective,
    DecisionGradientCertificate,
    Perturbation,
    RiskClass,
    bind_decision_digest,
)
from cwc.governance.decision_gradient import estimate_decision_gradient, verify_decision_gradient_certificate


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


@pytest.mark.parametrize("same_value", (False, True))
@pytest.mark.parametrize("extra_actions", ((), (("B", 2.0),)))
def test_normalization_collisions_fail_in_every_insertion_order(
    same_value: bool, extra_actions: tuple[tuple[str, float], ...]
) -> None:
    entries = (("A", 0.0), (" A ", 0.0 if same_value else 2.0), *extra_actions)
    for order in permutations(entries):
        with pytest.raises(ValueError, match="normalization collision"):
            estimate_decision_gradient(
                baseline_action="A",
                perturbations=(_p("p1"),),
                utility_evaluator=lambda _p, order=order: dict(order),
                source_state_digest="state",
                utility_digest="utility",
            )


@pytest.mark.parametrize(
    ("baseline", "utilities", "error"),
    (
        (1, {"1": 1, "B": 2}, "identifier"),
        ("A", {1: 2, "A": 1}, "identifier"),
        ("A", {" ": 2, "A": 1}, "identifier"),
        ("A", {"A": 1}, "distinct actions"),
        ("A", {"B": 1, "C": 2}, "baseline action"),
        ("A", {"A": 1, "B": float("inf")}, "finite numeric"),
        ("A", {"A": 1, "B": "invalid"}, "finite numeric"),
        ("A", {"A": 1, "B": True}, "finite numeric"),
    ),
)
def test_decision_gradient_admits_only_valid_action_tables(
    baseline: str, utilities: dict[str, float], error: str
) -> None:
    with pytest.raises(ValueError, match=error):
        estimate_decision_gradient(
            baseline_action=baseline,
            perturbations=(_p("p1"),),
            utility_evaluator=lambda _: utilities,
            source_state_digest="state",
            utility_digest="utility",
        )


@pytest.mark.parametrize(
    ("roster", "source", "error"),
    (
        ((), "state", "at least one perturbation"),
        ((_p("p1"), _p("p1")), "state", "ids must be unique"),
        ((_p("p1"),), " ", "context identifiers"),
    ),
)
def test_decision_gradient_rejects_incomplete_context(
    roster: tuple[Perturbation, ...], source: str, error: str,
) -> None:
    with pytest.raises(ValueError, match=error):
        estimate_decision_gradient(
            baseline_action="A",
            perturbations=roster,
            utility_evaluator=lambda _: pytest.fail("utility evaluated ahead of context validation"),
            source_state_digest=source,
            utility_digest="utility",
        )


def _decision_case() -> tuple[tuple[Perturbation, ...], dict[str, dict[str, float]]]:
    return (
        (_p("p1", 1.0), _p("p2", 2.0), _p("p3", 4.0)),
        {
            "p1": {"A": 1.0, "B": 1.0, "C": 0.0},
            "p2": {"A": 0.0, "B": 1.0, "C": 3.0},
            "p3": {"A": 2.0, "B": 1.0, "C": 6.0},
        },
    )


def _estimate_case(
    perturbations: tuple[Perturbation, ...],
    tables: dict[str, dict[str, float]],
    baseline: str = "A",
) -> DecisionGradientCertificate:
    return estimate_decision_gradient(
        baseline_action=baseline,
        perturbations=perturbations,
        utility_evaluator=lambda p: tables[p.perturbation_id],
        source_state_digest="state",
        utility_digest="utility",
    )


def test_numerical_contract_against_reference_and_permutation_properties() -> None:
    perturbations, tables = _decision_case()
    certificate = _estimate_case(perturbations, tables, baseline=" A ")
    # Independent rational reference against the declared baseline.
    regret_ref = {
        name: max(Fraction(value) - Fraction(row["A"]) for value in row.values())
        for name, row in tables.items()
    }
    weighted_ref = sum(
        Fraction(p.plausibility_weight) * regret_ref[p.perturbation_id] for p in perturbations
    ) / sum(Fraction(p.plausibility_weight) for p in perturbations)
    assert certificate.regret_by_perturbation == regret_ref == {"p1": 0, "p2": 3, "p3": 4}
    assert certificate.expected_regret == float(sum(regret_ref.values()) / 3)
    assert certificate.weighted_regret == float(weighted_ref) == float(Fraction(22, 7))
    assert certificate.worst_case_regret == 4
    assert certificate.decision_flip_count == 2

    for order in permutations(("A", "B", "C")):
        reordered = {key: {action: row[action] for action in order} for key, row in tables.items()}
        assert _estimate_case(perturbations, reordered) == certificate

    translated = {key: {action: value - 8 for action, value in row.items()} for key, row in tables.items()}
    assert _estimate_case(perturbations, translated).regret_by_perturbation == regret_ref
    scaled = {key: {action: value * 4 for action, value in row.items()} for key, row in tables.items()}
    assert _estimate_case(perturbations, scaled).weighted_regret == 4 * certificate.weighted_regret
    scaled_weights = tuple(replace(p, plausibility_weight=8 * p.plausibility_weight) for p in perturbations)
    assert _estimate_case(scaled_weights, tables).weighted_regret == certificate.weighted_regret
    reversed_roster = _estimate_case(tuple(reversed(perturbations)), tables)
    assert reversed_roster.weighted_regret == certificate.weighted_regret
    assert reversed_roster.decision_digest != certificate.decision_digest


def test_representable_aggregate_survives_intermediate_overflow() -> None:
    large = float_info.max
    certificate = _estimate_case(
        (_p("p1", 2.0), _p("p2", 2.0)),
        {"p1": {"A": 0.0, "B": large}, "p2": {"A": 0.0, "B": large}},
    )
    assert certificate.expected_regret == certificate.weighted_regret == large
    with pytest.raises(ValueError, match="action regret is outside the finite float range"):
        _estimate_case((_p("p1"),), {"p1": {"A": -large, "B": large}})
    with pytest.raises(ValueError, match="total plausibility weight is outside the finite float range"):
        _estimate_case((_p("p1", large), _p("p2", large)), {})


@pytest.mark.parametrize(
    "overrides",
    (
        {"baseline_action": " A "},
        {"perturbations_examined": ()},
        {"perturbations_examined": "p1"},
        {"perturbations_examined": ("p1", "p1")},
        {"regret_by_perturbation": ["p1", "p2", "p3"]},
        {"regret_by_perturbation": {"other": 0.0}},
        {"regret_by_perturbation": {"p1": float("nan"), "p2": 3, "p3": 4}},
        {"expected_regret": 2},
        {"worst_case_regret": 5},
        {"weighted_regret": 5},
        {"effective_weight": 0},
        {"effective_weight": "1"},
        {"effective_weight": 10 ** 400},
        {"decision_flip_count": 99},
        {"decision_flip_count": 2.0},
        {"decision_flip_count": True},
        {"decision_digest": "arbitrary"},
        {"digest_version": 3},
    ),
)
def test_certificate_construction_rejects_inconsistent_values(overrides: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        replace(_estimate_case(*_decision_case()), **overrides)


def test_certificate_requires_weighted_regret_above_observed_minimum() -> None:
    certificate = _estimate_case((_p("p1"),), {"p1": {"A": 1.0, "B": 4.0}})
    with pytest.raises(ValueError, match="within the observed range"):
        replace(certificate, weighted_regret=0.0)


def test_certificate_wire_format_round_trip_and_strict_decoding() -> None:
    certificate = _estimate_case(*_decision_case())
    serialized = certificate.to_json()
    restored = DecisionGradientCertificate.from_json(serialized)
    assert restored == certificate
    assert restored.to_json() == serialized

    with pytest.raises(ValueError, match="schema"):
        DecisionGradientCertificate.from_json("[]")
    duplicate = serialized.replace('"p1":0.0', '"p1":1,"p1":0.0', 1)
    assert duplicate != serialized
    with pytest.raises(ValueError, match="duplicate"):
        DecisionGradientCertificate.from_json(duplicate)
    nonfinite = serialized.replace('"p1":0.0', '"p1":NaN', 1)
    assert nonfinite != serialized
    with pytest.raises(ValueError, match="non-finite"):
        DecisionGradientCertificate.from_json(nonfinite)
    missing = json.loads(serialized)
    del missing["digest_version"]
    with pytest.raises(ValueError, match="field roster"):
        DecisionGradientCertificate.from_json(json.dumps(missing))


def test_contextual_replay_rejects_self_consistent_but_unbound_certificate() -> None:
    perturbations, tables = _decision_case()
    certificate = _estimate_case(perturbations, tables)
    kwargs = {
        "baseline_action": "A",
        "perturbations": perturbations,
        "utility_evaluator": lambda p: tables[p.perturbation_id],
        "source_state_digest": "state",
        "utility_digest": "utility",
    }
    assert verify_decision_gradient_certificate(certificate, **kwargs) == certificate
    for modified in (
        replace(certificate, weighted_regret=2.0),
        replace(certificate, effective_weight=8.0),
        replace(certificate, decision_digest="a" * 64),
    ):
        with pytest.raises(ValueError, match="contextual replay"):
            verify_decision_gradient_certificate(modified, **kwargs)
    for key, value in (
        ("baseline_action", "B"),
        ("source_state_digest", "different-state"),
        ("utility_digest", "different-utility"),
        ("perturbations", (replace(perturbations[0], provenance="synthetic:other"), *perturbations[1:])),
    ):
        with pytest.raises(ValueError, match="contextual replay"):
            verify_decision_gradient_certificate(certificate, **{**kwargs, key: value})

    # The earlier V1 digest is preserved for historical compatibility.
    legacy_digest = bind_decision_digest(
        baseline_action="A",
        source_state_digest="state",
        utility_digest="utility",
        perturbations=perturbations,
        regrets=certificate.regret_by_perturbation,
    )
    assert legacy_digest == "546be295a1024115b482da42c66e09cb90c0f8344f0e7f992b291e5151b39eab"
    legacy = replace(certificate, decision_digest=legacy_digest, digest_version=1)
    with pytest.raises(ValueError, match="requires a V2"):
        verify_decision_gradient_certificate(legacy, **kwargs)

    # Changing a non-best action changes the bound utility even with identical regrets.
    tables["p1"]["C"] = -1.0
    assert _estimate_case(perturbations, tables).regret_by_perturbation == certificate.regret_by_perturbation
    with pytest.raises(ValueError, match="contextual replay"):
        verify_decision_gradient_certificate(certificate, **kwargs)


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
