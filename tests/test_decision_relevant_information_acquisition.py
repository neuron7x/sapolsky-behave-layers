from __future__ import annotations

import math
from itertools import product

import pytest

from cwc.epistemics.information_acquisition import (
    InformationAction,
    PortfolioInformationAction,
    analyze_information_portfolio,
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


def test_complementary_actions_reach_threshold_when_neither_alone_can() -> None:
    historical = select_decision_relevant_information_action(
        actions=[act("x", 1.0, {"m1": 2.0, "m2": 0.0}),
                 act("y", 1.0, {"m1": 0.0, "m2": 2.0})],
        candidate_decision="A", alternative_decisions={"m1": "B", "m2": "C"},
        alpha=0.01, target_power=0.95, available_budget=2.0,
    )
    assert historical.state == "NO_DECISION_IDENTIFYING_INFORMATION_CHANNEL"
    actions = [
        PortfolioInformationAction("x", 1, 1, (2, 0), (2, 0)),
        PortfolioInformationAction("y", 1, 1, (0, 2), (0, 2)),
    ]
    kwargs = {"alternatives": ("m1", "m2"), "threshold": 2, "budget": 2}
    result = analyze_information_portfolio(actions=actions, **kwargs)
    assert result.state == "INFORMATION_THRESHOLD_CERTIFIED"
    assert result.single_action_lower_optimum == 0
    assert (result.lower_optimum, result.upper_optimum) == (2, 2)
    assert result.lower_witness == (("x", 1), ("y", 1))
    assert result.witness_cost == 2
    assert analyze_information_portfolio(actions=actions[::-1], **kwargs) == result


def test_missing_upper_bound_does_not_establish_impossibility() -> None:
    action = PortfolioInformationAction("q", 1, 1, (0,))
    with_budget = analyze_information_portfolio(actions=[action], alternatives=("m",), budget=1, threshold=1)
    assert with_budget.state == "INFORMATION_THRESHOLD_UNRESOLVED"
    assert with_budget.upper_optimum is None
    zero_budget = analyze_information_portfolio(actions=[action], alternatives=("m",), budget=0, threshold=1)
    assert zero_budget.state == "INFORMATION_THRESHOLD_RULED_OUT"
    assert zero_budget.upper_optimum == 0


def test_faster_action_with_zero_capacity_cannot_veto_a_feasible_action() -> None:
    result = analyze_information_portfolio(
        actions=[
            PortfolioInformationAction("fast", 1, 0, (5,), (5,)),
            PortfolioInformationAction("usable", 1, 2, (1,), (1,)),
        ],
        alternatives=("m",), budget=2, threshold=2,
    )
    assert result.lower_witness == (("usable", 2),)
    assert result.state == "INFORMATION_THRESHOLD_CERTIFIED"


@pytest.mark.parametrize("broken", [
    PortfolioInformationAction("x", True, 1, (0,), (1,)),
    PortfolioInformationAction("x", 1, 1, (False,), (1,)),
    PortfolioInformationAction("x", 1, 1, (2,), (1,)),
    PortfolioInformationAction("x", 1, 17, (0,), (1,)),
])
def test_portfolio_rejects_invalid_bounds(broken: PortfolioInformationAction) -> None:
    with pytest.raises(ValueError):
        analyze_information_portfolio(actions=[broken], alternatives=("m",), budget=1, threshold=1)


def test_portfolio_bounds_match_independent_cartesian_enumeration() -> None:
    states: dict[str, int] = {}
    mixed_only = 0
    for low in product(range(3), repeat=4):
        for increments in product((0, 1), repeat=4):
            high = tuple(l + d for l, d in zip(low, increments, strict=True))
            actions = [
                PortfolioInformationAction("a", 1, 2, low[:2], high[:2]),
                PortfolioInformationAction("b", 2, 2, low[2:], high[2:]),
            ]
            for budget in range(4):
                feasible = [(a, b) for a, b in product(range(3), repeat=2) if a + 2*b <= budget]
                lower = max(min(a*low[0] + b*low[2], a*low[1] + b*low[3]) for a, b in feasible)
                upper = max(min(a*high[0] + b*high[2], a*high[1] + b*high[3]) for a, b in feasible)
                single = max(min(a*low[0] + b*low[2], a*low[1] + b*low[3])
                             for a, b in feasible if not (a and b))
                result = analyze_information_portfolio(
                    actions=actions, alternatives=("x", "y"), budget=budget, threshold=2,
                )
                assert (result.lower_optimum, result.upper_optimum, result.single_action_lower_optimum) == (
                    lower, upper, single,
                )
                chosen = dict(result.lower_witness)
                a, b = chosen.get("a", 0), chosen.get("b", 0)
                assert (a, b) in feasible
                assert min(a*low[0] + b*low[2], a*low[1] + b*low[3]) == lower
                assert result.witness_cost == a + 2*b
                expected = ("INFORMATION_THRESHOLD_CERTIFIED" if lower >= 2
                            else "INFORMATION_THRESHOLD_RULED_OUT" if upper < 2
                            else "INFORMATION_THRESHOLD_UNRESOLVED")
                assert result.state == expected
                states[expected] = states.get(expected, 0) + 1
                mixed_only += int(single < 2 <= lower)
    assert mixed_only == 96
    assert states == {
        "INFORMATION_THRESHOLD_CERTIFIED": 1552,
        "INFORMATION_THRESHOLD_RULED_OUT": 2784,
        "INFORMATION_THRESHOLD_UNRESOLVED": 848,
    }
