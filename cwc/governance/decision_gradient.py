from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence

from cwc.governance.contracts import DecisionGradientCertificate, Perturbation, bind_decision_digest

UtilityEvaluator = Callable[[Perturbation], Mapping[str, float]]


def _validated_utilities(values: Mapping[str, float]) -> dict[str, float]:
    if len(values) < 2:
        raise ValueError("at least two actions are required")
    clean: dict[str, float] = {}
    for action, value in values.items():
        action = str(action).strip()
        value = float(value)
        if not action or not math.isfinite(value):
            raise ValueError("utilities require non-empty actions and finite values")
        clean[action] = value
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
    """Estimate decision-relevant counterfactual regret under declared perturbations.

    ``Decision Gradient`` is the programme name.  This estimator is a weighted
    regret/sensitivity functional, not a differential gradient unless a caller adds
    a perturbation geometry and derivative normalization.
    """
    baseline_action = baseline_action.strip()
    if not baseline_action:
        raise ValueError("baseline_action required")
    pp = tuple(perturbations)
    if not pp:
        raise ValueError("at least one perturbation required")
    ids = [p.perturbation_id for p in pp]
    if len(ids) != len(set(ids)):
        raise ValueError("perturbation ids must be unique")

    weight_sum = sum(p.plausibility_weight for p in pp)
    if not math.isfinite(weight_sum) or weight_sum <= 0:
        raise ValueError("positive total plausibility weight required")

    regrets: dict[str, float] = {}
    weighted_sum = 0.0
    flip_count = 0
    for perturbation in pp:
        utilities = _validated_utilities(utility_evaluator(perturbation))
        if baseline_action not in utilities:
            raise ValueError(f"baseline action {baseline_action!r} absent under {perturbation.perturbation_id}")
        best = _best_action(utilities)
        regret = max(0.0, utilities[best] - utilities[baseline_action])
        regrets[perturbation.perturbation_id] = regret
        weighted_sum += perturbation.plausibility_weight * regret
        if best != baseline_action and regret > 0:
            flip_count += 1

    weighted_regret = weighted_sum / weight_sum
    expected_regret = sum(regrets.values()) / len(regrets)
    worst_case_regret = max(regrets.values())
    digest = bind_decision_digest(
        baseline_action=baseline_action,
        source_state_digest=source_state_digest,
        utility_digest=utility_digest,
        perturbations=pp,
        regrets=regrets,
    )
    return DecisionGradientCertificate(
        baseline_action=baseline_action,
        perturbations_examined=tuple(ids),
        decision_flip_count=flip_count,
        expected_regret=expected_regret,
        worst_case_regret=worst_case_regret,
        weighted_regret=weighted_regret,
        effective_weight=weight_sum,
        regret_by_perturbation=regrets,
        decision_digest=digest,
    )
