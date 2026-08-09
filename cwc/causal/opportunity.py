"""First-principles opportunity/observability separation for adaptive compute.

The key distinction is between two questions that must not be conflated:

1. Does *any* unit-specific adaptive action have value before choosing a controller
   representation?  This is the instance-oracle opportunity.
2. How much of that value survives when decisions are restricted to a coarse,
   cheap observable context?  This is the contextual opportunity.

For an exhaustive potential-outcome table and scalarized utility U, the ordering

    best_fixed <= contextual_oracle <= instance_oracle

must hold.  Violating it is a software/statistical error.  A negative contextual
result therefore does not, by itself, prove the absence of latent per-instance
heterogeneity; it proves only that the tested context partition did not expose
sufficient value under the tested mechanism.

This module also supports a Lagrangian quality/compute analysis that keeps raw
quality and compute separate until a penalty lambda is explicitly supplied:

    U_lambda = quality - lambda * compute

The resulting opportunity curve is useful for candidate-mechanism qualification.
It is not a substitute for measured production latency/energy and carries no
scientific ascension authority on its own.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
import math


@dataclass(frozen=True, slots=True)
class QualityComputeOutcome:
    """One exhaustive action outcome with quality and compute kept separate.

    ``unit_id`` is the independent unit. ``regime`` is a scientific/latent regime
    label used only for opportunity analysis; it is not assumed to be cheaply
    observable at inference time.  ``compute`` is a non-negative abstract or
    measured resource quantity.  The resource unit must be declared by the
    experiment (e.g. executed FLOPs, milliseconds, joules, or a controlled proxy).
    """

    unit_id: str
    regime: str
    action: str
    quality: float
    compute: float


@dataclass(frozen=True, slots=True)
class OpportunityPoint:
    """Values at one Lagrange multiplier ``lambda_compute``."""

    lambda_compute: float
    fixed_value: float
    regime_oracle_value: float
    instance_oracle_value: float
    regime_gap: float
    instance_gap: float
    controller_compute: float
    regime_net_gap: float
    instance_net_gap: float
    best_fixed_action: str


@dataclass(frozen=True, slots=True)
class OpportunitySummary:
    """Finite candidate-mechanism opportunity summary over exact critical regions."""

    actions: tuple[str, ...]
    regimes: tuple[str, ...]
    critical_lambdas: tuple[float, ...]
    sampled_lambdas: tuple[float, ...]
    points: tuple[OpportunityPoint, ...]
    max_regime_gap: float
    max_instance_gap: float
    max_controller_compute_allowance: float
    positive_regime_interval_found: bool


def _finite(value: float, name: str) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


def validate_quality_compute_replay(
    rows: Sequence[QualityComputeOutcome],
    *,
    actions: Sequence[str] | None = None,
) -> tuple[str, ...]:
    """Validate an exhaustive quality/compute table and return canonical actions."""
    if not rows:
        raise ValueError("quality/compute replay must be non-empty")
    action_order = tuple(actions) if actions is not None else tuple(sorted({r.action for r in rows}))
    if not action_order or len(set(action_order)) != len(action_order) or any(not a for a in action_order):
        raise ValueError("actions must be unique non-empty strings")
    expected = set(action_order)

    by_unit: dict[str, dict[str, QualityComputeOutcome]] = defaultdict(dict)
    regime_by_unit: dict[str, str] = {}
    for row in rows:
        if not row.unit_id or not row.regime or not row.action:
            raise ValueError("unit_id, regime, and action must be non-empty")
        _finite(row.quality, "quality")
        _finite(row.compute, "compute")
        if row.compute < 0.0:
            raise ValueError("compute must be non-negative")
        if row.action not in expected:
            raise ValueError(f"undeclared action {row.action!r}")
        prior_regime = regime_by_unit.setdefault(row.unit_id, row.regime)
        if prior_regime != row.regime:
            raise ValueError(f"unit {row.unit_id!r} changes regime across actions")
        if row.action in by_unit[row.unit_id]:
            raise ValueError(f"duplicate outcome for {(row.unit_id, row.action)!r}")
        by_unit[row.unit_id][row.action] = row

    for unit_id, found in by_unit.items():
        if set(found) != expected:
            raise ValueError(
                f"unit {unit_id!r} is not exhaustive; "
                f"missing={sorted(expected-set(found))}, extra={sorted(set(found)-expected)}"
            )
    return action_order


def _unit_table(
    rows: Sequence[QualityComputeOutcome],
    *,
    actions: Sequence[str] | None = None,
) -> tuple[tuple[str, ...], dict[str, dict[str, QualityComputeOutcome]]]:
    action_order = validate_quality_compute_replay(rows, actions=actions)
    by_unit: dict[str, dict[str, QualityComputeOutcome]] = defaultdict(dict)
    for row in rows:
        by_unit[row.unit_id][row.action] = row
    return action_order, dict(by_unit)


def _mean(values: Iterable[float]) -> float:
    values = tuple(values)
    if not values:
        raise ValueError("cannot average an empty collection")
    return sum(values) / len(values)


def _utility(row: QualityComputeOutcome, lambda_compute: float) -> float:
    return row.quality - lambda_compute * row.compute


def opportunity_at_lambda(
    rows: Sequence[QualityComputeOutcome],
    *,
    lambda_compute: float,
    controller_compute: float = 0.0,
    actions: Sequence[str] | None = None,
) -> OpportunityPoint:
    """Compute fixed, regime-oracle, and instance-oracle opportunity exactly.

    ``controller_compute`` is charged once per adaptive decision and converted to
    utility using the same ``lambda_compute``.  The fixed policy pays no adaptive
    controller charge.
    """
    _finite(lambda_compute, "lambda_compute")
    _finite(controller_compute, "controller_compute")
    if lambda_compute < 0.0:
        raise ValueError("lambda_compute must be non-negative")
    if controller_compute < 0.0:
        raise ValueError("controller_compute must be non-negative")

    action_order, by_unit = _unit_table(rows, actions=actions)
    unit_ids = tuple(sorted(by_unit))

    action_means = {
        action: _mean(_utility(by_unit[u][action], lambda_compute) for u in unit_ids)
        for action in action_order
    }
    best_fixed_action = max(action_order, key=lambda a: (action_means[a], a))
    fixed_value = action_means[best_fixed_action]

    instance_oracle_value = _mean(
        max(_utility(by_unit[u][a], lambda_compute) for a in action_order)
        for u in unit_ids
    )

    units_by_regime: dict[str, list[str]] = defaultdict(list)
    for unit_id in unit_ids:
        any_row = by_unit[unit_id][action_order[0]]
        units_by_regime[any_row.regime].append(unit_id)
    regime_oracle_value = 0.0
    n_units = len(unit_ids)
    for regime, regime_units in sorted(units_by_regime.items()):
        regime_best = max(
            _mean(_utility(by_unit[u][a], lambda_compute) for u in regime_units)
            for a in action_order
        )
        regime_oracle_value += (len(regime_units) / n_units) * regime_best

    tol = 1e-12
    if regime_oracle_value + tol < fixed_value:
        raise AssertionError("regime oracle fell below best fixed value")
    if instance_oracle_value + tol < regime_oracle_value:
        raise AssertionError("instance oracle fell below regime oracle value")

    regime_gap = regime_oracle_value - fixed_value
    instance_gap = instance_oracle_value - fixed_value
    controller_penalty = lambda_compute * controller_compute
    return OpportunityPoint(
        lambda_compute=lambda_compute,
        fixed_value=fixed_value,
        regime_oracle_value=regime_oracle_value,
        instance_oracle_value=instance_oracle_value,
        regime_gap=regime_gap,
        instance_gap=instance_gap,
        controller_compute=controller_compute,
        regime_net_gap=regime_gap - controller_penalty,
        instance_net_gap=instance_gap - controller_penalty,
        best_fixed_action=best_fixed_action,
    )


def _crossing(q1: float, c1: float, q2: float, c2: float) -> float | None:
    denom = c1 - c2
    if math.isclose(denom, 0.0, abs_tol=1e-15, rel_tol=0.0):
        return None
    value = (q1 - q2) / denom
    if value > 0.0 and math.isfinite(value):
        return value
    return None


def critical_lambdas(
    rows: Sequence[QualityComputeOutcome],
    *,
    actions: Sequence[str] | None = None,
) -> tuple[float, ...]:
    """Return positive lambda values where any relevant action ranking can change.

    Crossings are collected at three resolutions: individual unit, regime mean,
    and global mean.  Between crossings, all argmax identities are constant and
    the opportunity functions are affine.
    """
    action_order, by_unit = _unit_table(rows, actions=actions)
    points: set[float] = set()

    def add_crossings(stats: Mapping[str, tuple[float, float]]) -> None:
        for i, a1 in enumerate(action_order):
            for a2 in action_order[i + 1 :]:
                q1, c1 = stats[a1]
                q2, c2 = stats[a2]
                value = _crossing(q1, c1, q2, c2)
                if value is not None:
                    points.add(value)

    for unit_id in sorted(by_unit):
        add_crossings({a: (by_unit[unit_id][a].quality, by_unit[unit_id][a].compute) for a in action_order})

    units_by_regime: dict[str, list[str]] = defaultdict(list)
    for unit_id in sorted(by_unit):
        units_by_regime[by_unit[unit_id][action_order[0]].regime].append(unit_id)
    for regime_units in units_by_regime.values():
        add_crossings({
            a: (
                _mean(by_unit[u][a].quality for u in regime_units),
                _mean(by_unit[u][a].compute for u in regime_units),
            )
            for a in action_order
        })

    all_units = tuple(sorted(by_unit))
    add_crossings({
        a: (
            _mean(by_unit[u][a].quality for u in all_units),
            _mean(by_unit[u][a].compute for u in all_units),
        )
        for a in action_order
    })
    return tuple(sorted(points))


def representative_lambdas(critical: Sequence[float]) -> tuple[float, ...]:
    """Choose exact-region representatives without arbitrary grid search."""
    critical = tuple(sorted(set(float(x) for x in critical if x > 0.0 and math.isfinite(x))))
    samples: list[float] = [0.0]
    if not critical:
        return tuple(samples)
    prior = 0.0
    for value in critical:
        if value > prior:
            samples.append((prior + value) / 2.0)
        samples.append(value)
        prior = value
    # One point beyond the last crossing is enough because rankings are fixed there.
    samples.append(critical[-1] * 2.0)
    return tuple(sorted(set(samples)))


def summarize_opportunity(
    rows: Sequence[QualityComputeOutcome],
    *,
    controller_compute: float = 0.0,
    actions: Sequence[str] | None = None,
) -> OpportunitySummary:
    """Summarize the complete finite-action opportunity geometry."""
    action_order = validate_quality_compute_replay(rows, actions=actions)
    regimes = tuple(sorted({r.regime for r in rows}))
    critical = critical_lambdas(rows, actions=action_order)
    sampled = representative_lambdas(critical)
    points = tuple(
        opportunity_at_lambda(
            rows,
            lambda_compute=lam,
            controller_compute=controller_compute,
            actions=action_order,
        )
        for lam in sampled
    )
    max_regime_gap = max(p.regime_gap for p in points)
    max_instance_gap = max(p.instance_gap for p in points)

    allowances = [
        p.regime_gap / p.lambda_compute
        for p in points
        if p.lambda_compute > 0.0 and p.regime_gap > 0.0
    ]
    max_allowance = max(allowances, default=0.0)
    positive = any(p.regime_net_gap > 1e-12 for p in points if p.lambda_compute > 0.0)
    return OpportunitySummary(
        actions=action_order,
        regimes=regimes,
        critical_lambdas=critical,
        sampled_lambdas=sampled,
        points=points,
        max_regime_gap=max_regime_gap,
        max_instance_gap=max_instance_gap,
        max_controller_compute_allowance=max_allowance,
        positive_regime_interval_found=positive,
    )


def capture_fraction(contextual_gap: float, instance_gap: float) -> float | None:
    """Fraction of instance-oracle opportunity captured by an observable context.

    Returns ``None`` when the denominator is zero: there is no latent opportunity
    to capture, so defining a ratio would manufacture meaning.
    """
    _finite(contextual_gap, "contextual_gap")
    _finite(instance_gap, "instance_gap")
    if contextual_gap < -1e-12 or instance_gap < -1e-12:
        raise ValueError("opportunity gaps must be non-negative")
    if contextual_gap > instance_gap + 1e-12:
        raise ValueError("contextual opportunity cannot exceed instance opportunity")
    if math.isclose(instance_gap, 0.0, abs_tol=1e-15, rel_tol=0.0):
        return None
    return contextual_gap / instance_gap
