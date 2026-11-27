from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction


def _require_nonnegative_int(name: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _canonical_digest(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class VerificationValue:
    guaranteed_net_gain: Fraction
    policy: tuple[int, ...] | None


def robust_verification_value(
    *,
    state_action_gains: Sequence[Sequence[int]],
    model_joint_weights: Sequence[Sequence[Sequence[int]]],
    admissible_actions: Sequence[Sequence[int]],
    candidate_policies: Iterable[Sequence[int]],
    verification_cost: int,
) -> VerificationValue:
    """Evaluate one fixed signal-to-action policy across all declared models.

    Matrices are state-major. Action zero is the no-verification fallback.
    A missing policy in the result means the score did not clear the cost.
    """
    _require_nonnegative_int("verification_cost", verification_cost)
    if not state_action_gains or not model_joint_weights or not admissible_actions:
        raise ValueError("state, model and signal populations must be nonempty")
    action_count = len(state_action_gains[0])
    signal_count = len(admissible_actions)
    for row in state_action_gains:
        if (
            not action_count
            or len(row) != action_count
            or any(type(gain) is not int for gain in row)
            or row[0] != 0
        ):
            raise ValueError("gains require equal-width integer rows with zero fallback gain")
    admitted: list[frozenset[int]] = []
    for actions in admissible_actions:
        for action in actions:
            if _require_nonnegative_int("admissible action", action) >= action_count:
                raise ValueError("admissible action outside gain matrix")
        if 0 not in actions:
            raise ValueError("fallback must be admissible for every signal")
        admitted.append(frozenset(actions))
    totals = []
    for weights in model_joint_weights:
        if len(weights) != len(state_action_gains) or any(len(row) != signal_count for row in weights):
            raise ValueError("each joint model must cover the exact state and signal populations")
        total = sum(_require_nonnegative_int("joint weight", weight) for row in weights for weight in row)
        if total == 0:
            raise ValueError("each joint model requires positive total weight")
        totals.append(total)

    best_gain = Fraction(-verification_cost)
    best_policy = (0,) * signal_count
    for candidate in candidate_policies:
        policy = tuple(candidate)
        if len(policy) != signal_count or any(
            _require_nonnegative_int("policy action", action) not in actions
            for action, actions in zip(policy, admitted, strict=True)
        ):
            raise ValueError("policy must select one admissible action per signal")
        gain = min(
            Fraction(
                sum(
                    weight * gains[policy[signal]]
                    for row, gains in zip(weights, state_action_gains, strict=True)
                    for signal, weight in enumerate(row)
                ),
                total,
            )
            for weights, total in zip(model_joint_weights, totals, strict=True)
        ) - verification_cost
        if (-gain, policy) < (-best_gain, best_policy):
            best_gain, best_policy = gain, policy
    return VerificationValue(best_gain, best_policy if best_gain > 0 else None)


@dataclass(frozen=True, slots=True)
class CounterfactualOption:
    task_id: str
    option_id: str
    cost_units: int
    value_units: int
    latency_units: int = 0
    risk_units: int = 0

    def __post_init__(self) -> None:
        if not str(self.task_id).strip():
            raise ValueError("task_id required")
        if not str(self.option_id).strip():
            raise ValueError("option_id required")
        for name in ("cost_units", "value_units", "latency_units", "risk_units"):
            _require_nonnegative_int(name, getattr(self, name))


@dataclass(frozen=True, slots=True)
class AllocationState:
    cost_units: int
    value_units: int
    latency_units: int
    risk_units: int
    selections: tuple[tuple[str, str], ...]

    @property
    def canonical_key(self) -> tuple[int, int, int, int, tuple[tuple[str, str], ...]]:
        return (
            self.cost_units,
            self.latency_units,
            self.risk_units,
            -self.value_units,
            self.selections,
        )


@dataclass(frozen=True, slots=True)
class CounterfactualFrontierSolution:
    budget_cost_units: int
    budget_latency_units: int | None
    budget_risk_units: int | None
    total_cost_units: int
    total_value_units: int
    total_latency_units: int
    total_risk_units: int
    selections: tuple[tuple[str, str], ...]
    frontier_size: int
    expanded_state_count: int
    certificate_digest: str


@dataclass(frozen=True, slots=True)
class PolicyOracleAudit:
    policy_cost_units: int
    policy_value_units: int
    policy_latency_units: int
    policy_risk_units: int
    oracle_value_units: int
    oracle_cost_units: int
    oracle_latency_units: int
    oracle_risk_units: int
    value_regret_units: int
    minimum_cost_for_policy_value_units: int
    avoidable_cost_units: int
    certificate_digest: str


def _group_options(options: Iterable[CounterfactualOption]) -> tuple[tuple[str, tuple[CounterfactualOption, ...]], ...]:
    by_task: dict[str, list[CounterfactualOption]] = {}
    seen_pairs: set[tuple[str, str]] = set()
    for option in options:
        pair = (option.task_id, option.option_id)
        if pair in seen_pairs:
            raise ValueError(f"duplicate task/option pair: {pair}")
        seen_pairs.add(pair)
        by_task.setdefault(option.task_id, []).append(option)
    if not by_task:
        raise ValueError("at least one option required")
    grouped: list[tuple[str, tuple[CounterfactualOption, ...]]] = []
    for task_id in sorted(by_task):
        task_options = tuple(sorted(by_task[task_id], key=lambda o: o.option_id))
        if not task_options:
            raise ValueError(f"task {task_id!r} has no options")
        grouped.append((task_id, task_options))
    return tuple(grouped)


def _within_limits(
    *,
    cost_units: int,
    latency_units: int,
    risk_units: int,
    max_cost_units: int,
    max_latency_units: int | None,
    max_risk_units: int | None,
) -> bool:
    if cost_units > max_cost_units:
        return False
    if max_latency_units is not None and latency_units > max_latency_units:
        return False
    return not (max_risk_units is not None and risk_units > max_risk_units)


def _dominates(left: AllocationState, right: AllocationState) -> bool:
    resources_no_worse = (
        left.cost_units <= right.cost_units
        and left.latency_units <= right.latency_units
        and left.risk_units <= right.risk_units
    )
    value_no_worse = left.value_units >= right.value_units
    strictly_better = (
        left.cost_units < right.cost_units
        or left.latency_units < right.latency_units
        or left.risk_units < right.risk_units
        or left.value_units > right.value_units
    )
    return resources_no_worse and value_no_worse and strictly_better


def _pareto_prune(states: Sequence[AllocationState]) -> tuple[AllocationState, ...]:
    best_by_metrics: dict[tuple[int, int, int, int], AllocationState] = {}
    for state in states:
        metrics = (state.cost_units, state.latency_units, state.risk_units, state.value_units)
        incumbent = best_by_metrics.get(metrics)
        if incumbent is None or state.selections < incumbent.selections:
            best_by_metrics[metrics] = state
    unique = tuple(best_by_metrics.values())
    kept: list[AllocationState] = []
    for i, candidate in enumerate(unique):
        if any(j != i and _dominates(other, candidate) for j, other in enumerate(unique)):
            continue
        kept.append(candidate)
    return tuple(sorted(kept, key=lambda s: s.canonical_key))


def exact_counterfactual_frontier(
    options: Iterable[CounterfactualOption],
    *,
    max_cost_units: int,
    max_latency_units: int | None = None,
    max_risk_units: int | None = None,
) -> tuple[tuple[AllocationState, ...], int]:
    max_cost_units = _require_nonnegative_int("max_cost_units", max_cost_units)
    if max_latency_units is not None:
        max_latency_units = _require_nonnegative_int("max_latency_units", max_latency_units)
    if max_risk_units is not None:
        max_risk_units = _require_nonnegative_int("max_risk_units", max_risk_units)

    grouped = _group_options(options)
    frontier: tuple[AllocationState, ...] = (
        AllocationState(cost_units=0, value_units=0, latency_units=0, risk_units=0, selections=()),
    )
    expanded = 0

    for task_id, task_options in grouped:
        candidates: list[AllocationState] = []
        for state in frontier:
            for option in task_options:
                expanded += 1
                cost = state.cost_units + option.cost_units
                latency = state.latency_units + option.latency_units
                risk = state.risk_units + option.risk_units
                if not _within_limits(
                    cost_units=cost,
                    latency_units=latency,
                    risk_units=risk,
                    max_cost_units=max_cost_units,
                    max_latency_units=max_latency_units,
                    max_risk_units=max_risk_units,
                ):
                    continue
                candidates.append(
                    AllocationState(
                        cost_units=cost,
                        value_units=state.value_units + option.value_units,
                        latency_units=latency,
                        risk_units=risk,
                        selections=(*state.selections, (task_id, option.option_id)),
                    )
                )
        if not candidates:
            raise ValueError(
                f"no feasible allocation remains after task {task_id!r}; resource budgets are too small"
            )
        frontier = _pareto_prune(candidates)

    return frontier, expanded


def _best_value_state(frontier: Sequence[AllocationState]) -> AllocationState:
    if not frontier:
        raise ValueError("frontier must be non-empty")
    return min(
        frontier,
        key=lambda s: (-s.value_units, s.cost_units, s.latency_units, s.risk_units, s.selections),
    )


def solve_exact_counterfactual_allocation(
    options: Iterable[CounterfactualOption],
    *,
    max_cost_units: int,
    max_latency_units: int | None = None,
    max_risk_units: int | None = None,
) -> CounterfactualFrontierSolution:
    options_tuple = tuple(options)
    frontier, expanded = exact_counterfactual_frontier(
        options_tuple,
        max_cost_units=max_cost_units,
        max_latency_units=max_latency_units,
        max_risk_units=max_risk_units,
    )
    best = _best_value_state(frontier)
    payload = {
        "version": "DGC_COUNTERFACTUAL_FRONTIER_V1",
        "limits": {"cost_units": max_cost_units, "latency_units": max_latency_units, "risk_units": max_risk_units},
        "options": [
            {
                "task_id": o.task_id,
                "option_id": o.option_id,
                "cost_units": o.cost_units,
                "value_units": o.value_units,
                "latency_units": o.latency_units,
                "risk_units": o.risk_units,
            }
            for o in sorted(options_tuple, key=lambda x: (x.task_id, x.option_id))
        ],
        "solution": {
            "cost_units": best.cost_units,
            "value_units": best.value_units,
            "latency_units": best.latency_units,
            "risk_units": best.risk_units,
            "selections": best.selections,
        },
    }
    return CounterfactualFrontierSolution(
        budget_cost_units=max_cost_units,
        budget_latency_units=max_latency_units,
        budget_risk_units=max_risk_units,
        total_cost_units=best.cost_units,
        total_value_units=best.value_units,
        total_latency_units=best.latency_units,
        total_risk_units=best.risk_units,
        selections=best.selections,
        frontier_size=len(frontier),
        expanded_state_count=expanded,
        certificate_digest=_canonical_digest(payload),
    )


def audit_policy_against_counterfactual_oracle(
    options: Iterable[CounterfactualOption],
    *,
    policy_selections: Mapping[str, str],
    max_cost_units: int,
    max_latency_units: int | None = None,
    max_risk_units: int | None = None,
) -> PolicyOracleAudit:
    options_tuple = tuple(options)
    grouped = _group_options(options_tuple)
    expected_tasks = tuple(task_id for task_id, _ in grouped)
    if set(policy_selections) != set(expected_tasks):
        missing = sorted(set(expected_tasks) - set(policy_selections))
        extra = sorted(set(policy_selections) - set(expected_tasks))
        raise ValueError(f"policy must select exactly one option per task; missing={missing}; extra={extra}")

    lookup = {(option.task_id, option.option_id): option for option in options_tuple}
    selected: list[CounterfactualOption] = []
    for task_id in expected_tasks:
        option_id = policy_selections[task_id]
        try:
            selected.append(lookup[(task_id, option_id)])
        except KeyError as exc:
            raise ValueError(f"unknown policy option {(task_id, option_id)!r}") from exc

    policy_cost = sum(o.cost_units for o in selected)
    policy_value = sum(o.value_units for o in selected)
    policy_latency = sum(o.latency_units for o in selected)
    policy_risk = sum(o.risk_units for o in selected)
    if not _within_limits(
        cost_units=policy_cost,
        latency_units=policy_latency,
        risk_units=policy_risk,
        max_cost_units=max_cost_units,
        max_latency_units=max_latency_units,
        max_risk_units=max_risk_units,
    ):
        raise ValueError("policy selections violate declared resource budgets")

    frontier, _ = exact_counterfactual_frontier(
        options_tuple,
        max_cost_units=max_cost_units,
        max_latency_units=max_latency_units,
        max_risk_units=max_risk_units,
    )
    oracle = _best_value_state(frontier)
    same_or_better = [
        state
        for state in frontier
        if state.value_units >= policy_value
        and state.latency_units <= policy_latency
        and state.risk_units <= policy_risk
    ]
    if not same_or_better:
        raise RuntimeError("frontier lost all states matching the feasible policy envelope")
    min_cost = min(state.cost_units for state in same_or_better)
    avoidable = max(0, policy_cost - min_cost)
    regret = oracle.value_units - policy_value
    if regret < 0:
        raise RuntimeError("oracle value cannot be lower than feasible policy value")

    payload = {
        "version": "DGC_COUNTERFACTUAL_ORACLE_AUDIT_V1",
        "policy": {
            "cost_units": policy_cost,
            "value_units": policy_value,
            "latency_units": policy_latency,
            "risk_units": policy_risk,
            "selections": sorted(policy_selections.items()),
        },
        "oracle": {
            "cost_units": oracle.cost_units,
            "value_units": oracle.value_units,
            "latency_units": oracle.latency_units,
            "risk_units": oracle.risk_units,
            "selections": oracle.selections,
        },
        "minimum_cost_for_policy_value_units": min_cost,
        "avoidable_cost_units": avoidable,
    }
    return PolicyOracleAudit(
        policy_cost_units=policy_cost,
        policy_value_units=policy_value,
        policy_latency_units=policy_latency,
        policy_risk_units=policy_risk,
        oracle_value_units=oracle.value_units,
        oracle_cost_units=oracle.cost_units,
        oracle_latency_units=oracle.latency_units,
        oracle_risk_units=oracle.risk_units,
        value_regret_units=regret,
        minimum_cost_for_policy_value_units=min_cost,
        avoidable_cost_units=avoidable,
        certificate_digest=_canonical_digest(payload),
    )
