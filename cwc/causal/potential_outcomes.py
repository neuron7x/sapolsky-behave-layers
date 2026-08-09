"""Fail-closed contracts for causal adaptive-compute experiments.

The causal layer deliberately knows nothing about models, routers, or PyTorch.  It
represents the *decision problem* after a runner has produced outcomes.  Keeping
this layer pure makes it possible to attack identification and statistics without
silently changing the execution mechanism.

All costs in this module must already be expressed in the same scalar utility
units as ``utility``.  Observation/controller/dispatch costs are decision-level
costs and are therefore charged by the experiment gate, not duplicated on every
potential-outcome row.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from collections import defaultdict
from collections.abc import Iterable, Sequence


@dataclass(frozen=True, slots=True)
class PotentialOutcome:
    """One observed potential outcome from an exhaustive frozen-action replay.

    ``unit_id`` is the independent experimental unit (request/document/episode,
    never an individual token when tokens are nested in a request).  A valid
    exhaustive replay contains exactly one row for every ``(unit_id, action)``
    pair and one immutable pre-decision context label per unit.
    """

    unit_id: str
    context: str
    action: str
    utility: float
    action_cost: float = 0.0

    @property
    def net_utility(self) -> float:
        return self.utility - self.action_cost


@dataclass(frozen=True, slots=True)
class TrialObservation:
    """One row from a randomized/known-propensity intervention trial.

    ``outcome_model`` contains *cross-fitted* predictions for every admissible
    action.  It is consumed by the doubly-robust estimator; predictions fitted on
    the same unit are not admissible evidence.
    """

    unit_id: str
    context: str
    action: str
    utility: float
    propensity: float
    outcome_model: dict[str, float]


def _finite(value: float, name: str) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


def validate_exhaustive_replay(
    rows: Sequence[PotentialOutcome],
    *,
    actions: Sequence[str] | None = None,
) -> tuple[str, ...]:
    """Validate complete potential outcomes and return canonical action order.

    Fail-closed conditions:
    - no empty ids/contexts/actions;
    - finite utility/cost and non-negative action cost;
    - a unit has exactly one immutable context;
    - no duplicate ``(unit, action)`` row;
    - every independent unit has every admissible action exactly once.
    """
    if not rows:
        raise ValueError("exhaustive replay must contain at least one row")

    declared = tuple(actions) if actions is not None else tuple(sorted({r.action for r in rows}))
    if not declared or len(set(declared)) != len(declared) or any(not a for a in declared):
        raise ValueError("actions must be unique non-empty strings")
    expected = set(declared)

    by_unit: dict[str, dict[str, PotentialOutcome]] = defaultdict(dict)
    unit_context: dict[str, str] = {}
    for row in rows:
        if not row.unit_id or not row.context or not row.action:
            raise ValueError("unit_id, context and action must be non-empty")
        _finite(row.utility, "utility")
        _finite(row.action_cost, "action_cost")
        if row.action_cost < 0.0:
            raise ValueError("action_cost must be non-negative")
        if row.action not in expected:
            raise ValueError(f"undeclared action {row.action!r}")
        prior_context = unit_context.setdefault(row.unit_id, row.context)
        if prior_context != row.context:
            raise ValueError(f"unit {row.unit_id!r} changes context across actions")
        if row.action in by_unit[row.unit_id]:
            raise ValueError(f"duplicate outcome for {(row.unit_id, row.action)!r}")
        by_unit[row.unit_id][row.action] = row

    for unit_id, found in by_unit.items():
        if set(found) != expected:
            missing = sorted(expected - set(found))
            extra = sorted(set(found) - expected)
            raise ValueError(f"unit {unit_id!r} is not exhaustive; missing={missing}, extra={extra}")
    return declared


def independent_units(rows: Sequence[PotentialOutcome]) -> tuple[str, ...]:
    """Return deterministic independent-unit ids after contract validation."""
    validate_exhaustive_replay(rows)
    return tuple(sorted({r.unit_id for r in rows}))


def context_action_matrix(
    rows: Sequence[PotentialOutcome],
    *,
    actions: Sequence[str] | None = None,
) -> tuple[tuple[str, ...], tuple[str, ...], list[list[float]], dict[str, int]]:
    """Aggregate exhaustive replays into ``E[net utility | context, action]``.

    Returns ``(contexts, actions, matrix, units_per_context)``.  Aggregation is
    unit-weighted, so a request with more tokens cannot silently receive more
    inferential weight merely because it generated more nested observations.
    """
    action_order = validate_exhaustive_replay(rows, actions=actions)
    contexts = tuple(sorted({r.context for r in rows}))
    by_key: dict[tuple[str, str], list[float]] = defaultdict(list)
    units_per_context: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        by_key[(row.context, row.action)].append(row.net_utility)
        units_per_context[row.context].add(row.unit_id)

    matrix: list[list[float]] = []
    for context in contexts:
        row_values: list[float] = []
        expected_n = len(units_per_context[context])
        for action in action_order:
            values = by_key[(context, action)]
            if len(values) != expected_n:
                raise ValueError(
                    f"context {context!r}, action {action!r} has {len(values)} values; "
                    f"expected {expected_n}"
                )
            row_values.append(sum(values) / len(values))
        matrix.append(row_values)
    return contexts, action_order, matrix, {k: len(v) for k, v in units_per_context.items()}


def rows_from_replicate_matrices(
    matrices: Sequence[Sequence[Sequence[float]]],
    *,
    contexts: Sequence[str],
    actions: Sequence[str],
    unit_prefix: str,
) -> list[PotentialOutcome]:
    """Convert frozen replicate utility matrices into the canonical row contract.

    This adapter is intentionally explicit: it is used for retrospective audits
    of already sealed CWC evidence and does not manufacture independence.
    """
    if not matrices:
        raise ValueError("matrices must be non-empty")
    if not contexts or not actions:
        raise ValueError("contexts/actions must be non-empty")
    out: list[PotentialOutcome] = []
    for i, matrix in enumerate(matrices):
        if len(matrix) != len(contexts):
            raise ValueError("matrix/context shape mismatch")
        for ci, context in enumerate(contexts):
            if len(matrix[ci]) != len(actions):
                raise ValueError("matrix/action shape mismatch")
            # Context cells of one seed×shard replicate are correlated.  Give
            # each context its own unit id only for representation; inferential
            # code must continue to use the original replicate matrix as cluster.
            unit_id = f"{unit_prefix}:{i}:{context}"
            for ai, action in enumerate(actions):
                value = float(matrix[ci][ai])
                _finite(value, "matrix utility")
                out.append(PotentialOutcome(unit_id, str(context), str(action), value))
    validate_exhaustive_replay(out, actions=tuple(map(str, actions)))
    return out
