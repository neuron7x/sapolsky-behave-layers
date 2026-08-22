from __future__ import annotations

from cwc.governance.counterfactual_frontier import (
    CounterfactualOption,
    audit_policy_against_counterfactual_oracle,
    solve_exact_counterfactual_allocation,
)


def _greedy_ratio_value(options, budget):
    by_task = {}
    for option in options:
        by_task.setdefault(option.task_id, []).append(option)
    chosen = {}
    cost = 0
    value = 0
    for task_id in sorted(by_task):
        base = min(by_task[task_id], key=lambda o: (o.cost_units, -o.value_units, o.option_id))
        chosen[task_id] = base
        cost += base.cost_units
        value += base.value_units
    upgrades = []
    for task_id, task_options in by_task.items():
        base = chosen[task_id]
        for option in task_options:
            delta_cost = option.cost_units - base.cost_units
            delta_value = option.value_units - base.value_units
            if delta_cost > 0 and delta_value > 0:
                upgrades.append(
                    (-(delta_value / delta_cost), -delta_value, task_id, option.option_id, option)
                )
    for _, _, task_id, _, option in sorted(upgrades):
        current = chosen[task_id]
        delta_cost = option.cost_units - current.cost_units
        if cost + delta_cost <= budget:
            cost += delta_cost
            value += option.value_units - current.value_units
            chosen[task_id] = option
    return value


def main() -> int:
    options = (
        CounterfactualOption("a", "stop", 0, 0),
        CounterfactualOption("a", "deep", 6, 12),
        CounterfactualOption("b", "stop", 0, 0),
        CounterfactualOption("b", "deep", 5, 9),
        CounterfactualOption("c", "stop", 0, 0),
        CounterfactualOption("c", "deep", 5, 9),
    )
    exact = solve_exact_counterfactual_allocation(options, max_cost_units=10)
    greedy_value = _greedy_ratio_value(options, 10)
    if exact.total_value_units != 18 or greedy_value != 12:
        raise SystemExit(
            f"CCF_ATTACK_FAIL exact={exact.total_value_units} greedy={greedy_value}"
        )

    waste = (
        CounterfactualOption("x", "wasteful", 5, 5),
        CounterfactualOption("x", "efficient", 2, 5),
        CounterfactualOption("y", "cheap", 1, 1),
        CounterfactualOption("y", "better", 3, 4),
    )
    audit = audit_policy_against_counterfactual_oracle(
        waste,
        policy_selections={"x": "wasteful", "y": "cheap"},
        max_cost_units=8,
    )
    if audit.value_regret_units != 3 or audit.avoidable_cost_units != 3:
        raise SystemExit(f"CCF_AUDIT_ATTACK_FAIL {audit}")

    print(
        "DGC-CCF-GATE: PASS — greedy allocation falsified; "
        "oracle regret/cost headroom recovered"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
