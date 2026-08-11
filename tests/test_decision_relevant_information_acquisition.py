from __future__ import annotations

import math

from cwc.epistemics.information_acquisition import (
    InformationAction,
    select_decision_relevant_information_action,
    select_maximin_information_action,
)


def act(name, cost, rates, cert="CERTIFIED_LOWER_BOUND", max_units=None):
    return InformationAction(name, cost, rates, cert, max_units=max_units)


def test_same_decision_models_require_no_acquisition_even_if_not_identified():
    r = select_decision_relevant_information_action(
        actions=[act("q", 1.0, {"m1": 0.0, "m2": 0.3})],
        candidate_decision="A",
        alternative_decisions={"m1": "A", "m2": "A"},
        alpha=0.01,
        target_power=0.95,
        available_budget=100.0,
    )
    assert r.state == "DECISION_ALREADY_IDENTIFIED_NO_ACQUISITION"
    assert r.necessary_cost_lower_bound == 0.0
    assert set(r.ignored_same_decision_alternatives) == {"m1", "m2"}


def test_same_decision_zero_rate_no_longer_blocks_decisive_probe():
    q = act("decisive", 1.0, {"same": 0.0, "flip": 0.2})
    legacy = select_maximin_information_action(
        actions=[q], unresolved_alternatives=["same", "flip"],
        alpha=0.01, target_power=0.95, available_budget=100.0,
    )
    assert legacy.state == "NO_IDENTIFYING_INFORMATION_CHANNEL"
    r = select_decision_relevant_information_action(
        actions=[q], candidate_decision="A",
        alternative_decisions={"same": "A", "flip": "B"},
        alpha=0.01, target_power=0.95, available_budget=100.0,
    )
    assert r.state == "ACQUIRE_DECISION_RELEVANT_EVIDENCE_BUDGET_NOT_RULED_OUT_BY_CONVERSE"
    assert r.action_id == "decisive"
    assert r.bottleneck_alternatives == ("flip",)


def test_cross_decision_zero_rate_blocks_spend():
    r = select_decision_relevant_information_action(
        actions=[act("q", 1.0, {"same": 0.7, "flip": 0.0})],
        candidate_decision="A", alternative_decisions={"same": "A", "flip": "B"},
        alpha=0.01, target_power=0.95, available_budget=1000,
    )
    assert r.state == "NO_DECISION_IDENTIFYING_INFORMATION_CHANNEL"
    assert math.isinf(r.necessary_cost_lower_bound)


def test_selects_cross_decision_information_per_cost_not_raw_rate():
    r = select_decision_relevant_information_action(
        actions=[
            act("cheap", 1.0, {"flip": 0.10}),
            act("raw", 4.0, {"flip": 0.30}),
        ],
        candidate_decision="A", alternative_decisions={"flip": "B"},
        alpha=0.01, target_power=0.95, available_budget=100,
    )
    assert r.action_id == "cheap"


def test_nuisance_information_cannot_dominate_decision_information():
    r = select_decision_relevant_information_action(
        actions=[
            act("nuisance", 1.0, {"same": 10.0, "flip": 0.01}),
            act("decision", 1.0, {"same": 0.001, "flip": 0.10}),
        ],
        candidate_decision="A", alternative_decisions={"same": "A", "flip": "B"},
        alpha=0.01, target_power=0.95, available_budget=100,
    )
    assert r.action_id == "decision"


def test_capacity_and_budget_are_distinct_vetoes():
    cap = select_decision_relevant_information_action(
        actions=[act("q", 1.0, {"flip": 0.2}, max_units=5)],
        candidate_decision="A", alternative_decisions={"flip": "B"},
        alpha=0.01, target_power=0.95, available_budget=100,
    )
    assert cap.state == "DECISION_ACTION_CAPACITY_BELOW_NECESSARY_BOUND"
    bud = select_decision_relevant_information_action(
        actions=[act("q", 1.0, {"flip": 0.2}, max_units=1000)],
        candidate_decision="A", alternative_decisions={"flip": "B"},
        alpha=0.01, target_power=0.95, available_budget=10,
    )
    assert bud.state == "INSUFFICIENT_DECISION_INFORMATION_BUDGET"


def test_incomplete_and_uncertified_actions_cannot_authorize_spend():
    r = select_decision_relevant_information_action(
        actions=[
            act("uncert", 1.0, {"f1": 9.0, "f2": 9.0}, cert="POINT_ESTIMATE"),
            act("partial", 1.0, {"f1": 1.0}),
        ],
        candidate_decision="A", alternative_decisions={"f1": "B", "f2": "C"},
        alpha=0.01, target_power=0.95, available_budget=1000,
    )
    assert r.state == "NO_CERTIFIED_DECISION_INFORMATION_RATE"


def test_order_invariance():
    a = [act("z", 2.0, {"f1": 0.3, "f2": 0.2}), act("a", 1.0, {"f1": 0.11, "f2": 0.11})]
    kwargs = dict(candidate_decision="A", alternative_decisions={"f2": "C", "same": "A", "f1": "B"}, alpha=0.01, target_power=0.95, available_budget=100)
    r1 = select_decision_relevant_information_action(actions=a, **kwargs)
    r2 = select_decision_relevant_information_action(actions=list(reversed(a)), **kwargs)
    assert r1 == r2
