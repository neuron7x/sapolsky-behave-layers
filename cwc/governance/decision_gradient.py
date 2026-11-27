from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from fractions import Fraction

from cwc.governance.contracts import (
    DecisionGradientCertificate,
    Perturbation,
    _action_identifier,
    _bind_decision_digest_v2,
    _empirical_mean,
)

UtilityEvaluator = Callable[[Perturbation], Mapping[str, float]]


def _validated_utilities(values: Mapping[str, float]) -> dict[str, float]:
    clean: dict[str, float] = {}
    for raw_action, raw_value in values.items():
        action = _action_identifier(raw_action)
        if action in clean:
            raise ValueError(f"action normalization collision for {action!r}")
        try:
            value = float(raw_value)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("utilities require finite numeric values") from exc
        if isinstance(raw_value, bool) or not math.isfinite(value):
            raise ValueError("utilities require finite numeric values")
        clean[action] = value
    if len(clean) < 2:
        raise ValueError("at least two distinct actions are required")
    return clean


def _best_action(utilities: Mapping[str, float]) -> str:
    # Lexicographic tie-break makes certificate replay deterministic.
    return min(utilities, key=lambda action: (-utilities[action], action))


def estimate_decision_gradient(
    *,
    baseline_action: str,
    perturbations: Sequence[Perturbation],
    utility_evaluator: UtilityEvaluator,
    source_state_digest: str,
    utility_digest: str,
) -> DecisionGradientCertificate:
    """Compute empirical regret under the supplied, ordered perturbation roster.

    Each regret is the best utility minus the baseline utility. A flip means
    a strictly better action exists. The best action uses a lexicographic tie
    break. Expected regret is the arithmetic mean over supplied cases.
    Weighted regret divides the sum of weight times regret by total weight.
    Such a mean estimates a population expectation under additional sampling
    assumptions. Worst-case regret is the sample maximum.

    Action IDs are stripped nonempty strings with no collisions. Utilities
    and computed regrets must fit binary64. Weights are finite, nonnegative
    and have a positive, representable total. Aggregation uses exact arithmetic
    over the represented inputs and rounds each output once to binary64.
    The V2 digest binds the ordered roster, normalized utility tables, baseline
    and supplied context identifiers.
    """
    baseline_action = _action_identifier(baseline_action)
    if any(not isinstance(value, str) or not value.strip() for value in (source_state_digest, utility_digest)):
        raise ValueError("source and utility context identifiers must be non-empty strings")
    pp = tuple(perturbations)
    if not pp:
        raise ValueError("at least one perturbation required")
    ids = [p.perturbation_id for p in pp]
    if len(ids) != len(set(ids)):
        raise ValueError("perturbation ids must be unique")

    weights = tuple(Fraction(p.plausibility_weight) for p in pp)
    total = sum(weights, Fraction())
    if total <= 0:
        raise ValueError("positive total plausibility weight required")
    try:
        weight_sum = float(total)
    except OverflowError as exc:
        raise ValueError("total plausibility weight is outside the finite float range") from exc

    regrets: dict[str, float] = {}
    utility_tables: dict[str, dict[str, float]] = {}
    for perturbation in pp:
        utilities = _validated_utilities(utility_evaluator(perturbation))
        if baseline_action not in utilities:
            raise ValueError(f"baseline action {baseline_action!r} absent under {perturbation.perturbation_id}")
        best = _best_action(utilities)
        regret = max(0.0, utilities[best] - utilities[baseline_action])
        if not math.isfinite(regret):
            raise ValueError("action regret is outside the finite float range")
        regrets[perturbation.perturbation_id] = regret
        utility_tables[perturbation.perturbation_id] = utilities

    weighted_sum = sum(
        (weight * Fraction(regret) for weight, regret in zip(weights, regrets.values(), strict=True)),
        Fraction(),
    )
    digest = _bind_decision_digest_v2(
        baseline_action=baseline_action,
        source_state_digest=source_state_digest,
        utility_digest=utility_digest,
        perturbations=pp,
        utilities=utility_tables,
    )
    return DecisionGradientCertificate(
        baseline_action=baseline_action,
        perturbations_examined=tuple(ids),
        decision_flip_count=sum(regret > 0 for regret in regrets.values()),
        expected_regret=_empirical_mean(tuple(regrets.values())),
        worst_case_regret=max(regrets.values()),
        weighted_regret=float(weighted_sum / total),
        effective_weight=weight_sum,
        regret_by_perturbation=regrets,
        decision_digest=digest,
        digest_version=2,
    )


def verify_decision_gradient_certificate(
    certificate: DecisionGradientCertificate,
    *,
    baseline_action: str,
    perturbations: Sequence[Perturbation],
    utility_evaluator: UtilityEvaluator,
    source_state_digest: str,
    utility_digest: str,
) -> DecisionGradientCertificate:
    """Replay a V2 certificate against independently supplied trusted inputs."""
    if type(certificate) is not DecisionGradientCertificate or certificate.digest_version != 2:
        raise ValueError("contextual verification requires a V2 decision-gradient certificate")
    replayed = estimate_decision_gradient(
        baseline_action=baseline_action,
        perturbations=perturbations,
        utility_evaluator=utility_evaluator,
        source_state_digest=source_state_digest,
        utility_digest=utility_digest,
    )
    if certificate != replayed:
        raise ValueError("decision-gradient certificate does not match contextual replay")
    return replayed
