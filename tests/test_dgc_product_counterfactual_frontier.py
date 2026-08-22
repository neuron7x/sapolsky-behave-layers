from __future__ import annotations

import itertools
import random

import pytest

from cwc.governance.counterfactual_frontier import (
    CounterfactualOption,
    audit_policy_against_counterfactual_oracle,
    solve_exact_counterfactual_allocation,
)


def _opts():
    return (
        CounterfactualOption("t1", "cheap", 1, 2, 1, 0),
        CounterfactualOption("t1", "deep", 4, 7, 3, 1),
        CounterfactualOption("t2", "cheap", 1, 2, 1, 0),
        CounterfactualOption("t2", "deep", 4, 8, 3, 1),
    )


def test_exact_allocator_finds_nonuniform_global_optimum():
    sol = solve_exact_counterfactual_allocation(_opts(), max_cost_units=5)
    assert sol.total_value_units == 10
    assert sol.total_cost_units == 5
    assert sol.selections == (("t1", "cheap"), ("t2", "deep"))


def test_latency_and_risk_are_hard_constraints():
    sol = solve_exact_counterfactual_allocation(
        _opts(), max_cost_units=8, max_latency_units=4, max_risk_units=1
    )
    assert sol.total_value_units == 10
    assert sol.total_risk_units == 1
    assert sol.total_latency_units == 4


def test_policy_audit_reports_value_regret_and_avoidable_cost():
    options = (
        CounterfactualOption("t1", "wasteful", 5, 5, 2, 0),
        CounterfactualOption("t1", "efficient", 2, 5, 1, 0),
        CounterfactualOption("t2", "cheap", 1, 1, 1, 0),
        CounterfactualOption("t2", "better", 3, 4, 2, 0),
    )
    audit = audit_policy_against_counterfactual_oracle(
        options,
        policy_selections={"t1": "wasteful", "t2": "cheap"},
        max_cost_units=8,
    )
    assert audit.policy_value_units == 6
    assert audit.oracle_value_units == 9
    assert audit.value_regret_units == 3
    assert audit.minimum_cost_for_policy_value_units == 3
    assert audit.avoidable_cost_units == 3


def test_ties_are_deterministic_and_input_order_invariant():
    options = (
        CounterfactualOption("b", "z", 1, 1),
        CounterfactualOption("b", "a", 1, 1),
        CounterfactualOption("a", "z", 1, 1),
        CounterfactualOption("a", "a", 1, 1),
    )
    expected = (("a", "a"), ("b", "a"))
    assert solve_exact_counterfactual_allocation(options, max_cost_units=2).selections == expected
    assert solve_exact_counterfactual_allocation(reversed(options), max_cost_units=2).selections == expected


def test_infeasible_budget_fails_closed():
    options = (
        CounterfactualOption("t1", "only", 2, 1),
        CounterfactualOption("t2", "only", 2, 1),
    )
    with pytest.raises(ValueError, match="no feasible allocation"):
        solve_exact_counterfactual_allocation(options, max_cost_units=3)


def test_policy_must_cover_exact_task_set_and_be_feasible():
    with pytest.raises(ValueError, match="exactly one option"):
        audit_policy_against_counterfactual_oracle(
            _opts(), policy_selections={"t1": "cheap"}, max_cost_units=8
        )
    with pytest.raises(ValueError, match="violate"):
        audit_policy_against_counterfactual_oracle(
            _opts(),
            policy_selections={"t1": "deep", "t2": "deep"},
            max_cost_units=5,
        )


def _bruteforce(options, max_cost, max_latency, max_risk):
    by_task = {}
    for option in options:
        by_task.setdefault(option.task_id, []).append(option)
    best = None
    for combo in itertools.product(*(by_task[k] for k in sorted(by_task))):
        cost = sum(o.cost_units for o in combo)
        latency = sum(o.latency_units for o in combo)
        risk = sum(o.risk_units for o in combo)
        value = sum(o.value_units for o in combo)
        if cost > max_cost or latency > max_latency or risk > max_risk:
            continue
        selections = tuple((o.task_id, o.option_id) for o in combo)
        key = (-value, cost, latency, risk, selections)
        if best is None or key < best[0]:
            best = (key, value, cost, latency, risk, selections)
    return best


def test_exact_allocator_matches_bruteforce_random_small_instances():
    rng = random.Random(20260823)
    for _ in range(100):
        options = []
        for t in range(4):
            for j in range(3):
                options.append(
                    CounterfactualOption(
                        f"t{t}",
                        f"o{j}",
                        rng.randint(0, 5),
                        rng.randint(0, 9),
                        rng.randint(0, 4),
                        rng.randint(0, 3),
                    )
                )
        o0 = [o for o in options if o.option_id == "o0"]
        max_cost = sum(o.cost_units for o in o0) + rng.randint(0, 6)
        max_latency = sum(o.latency_units for o in o0) + rng.randint(0, 4)
        max_risk = sum(o.risk_units for o in o0) + rng.randint(0, 3)

        brute = _bruteforce(options, max_cost, max_latency, max_risk)
        assert brute is not None
        sol = solve_exact_counterfactual_allocation(
            options,
            max_cost_units=max_cost,
            max_latency_units=max_latency,
            max_risk_units=max_risk,
        )
        assert (
            sol.total_value_units,
            sol.total_cost_units,
            sol.total_latency_units,
            sol.total_risk_units,
            sol.selections,
        ) == (brute[1], brute[2], brute[3], brute[4], brute[5])
