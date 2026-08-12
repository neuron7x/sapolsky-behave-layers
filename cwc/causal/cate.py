"""Causal value estimands for adaptive-compute decisions.

The primary CWC-VIA-V1 estimand is *value*, not routing accuracy.  For exhaustive
frozen-action replay the context-specific potential-outcome matrix directly
identifies the oracle-vs-static opportunity.  For randomized trials, policy value
can additionally be estimated with inverse-propensity or doubly-robust estimators.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence

from .potential_outcomes import TrialObservation


def _matrix_shape(matrix: Sequence[Sequence[float]]) -> tuple[int, int]:
    if not matrix or not matrix[0]:
        raise ValueError("utility matrix must be non-empty")
    width = len(matrix[0])
    if any(len(row) != width for row in matrix):
        raise ValueError("utility matrix must be rectangular")
    if any(not math.isfinite(float(x)) for row in matrix for x in row):
        raise ValueError("utility matrix entries must be finite")
    return len(matrix), width


def oracle_gap(matrix: Sequence[Sequence[float]], prior: Sequence[float] | None = None) -> dict[str, float | int]:
    """Compute context-conditional oracle value minus the best fixed action."""
    n_contexts, n_actions = _matrix_shape(matrix)
    if prior is None:
        weights = [1.0 / n_contexts] * n_contexts
    else:
        weights = list(map(float, prior))
        if len(weights) != n_contexts or any(w < 0 or not math.isfinite(w) for w in weights):
            raise ValueError("prior must be finite, non-negative, and match contexts")
        if not math.isclose(sum(weights), 1.0, abs_tol=1e-9, rel_tol=0.0):
            raise ValueError("prior must sum to one")
    oracle = sum(weights[c] * max(map(float, matrix[c])) for c in range(n_contexts))
    fixed_values = [sum(weights[c] * float(matrix[c][a]) for c in range(n_contexts)) for a in range(n_actions)]
    fixed = max(fixed_values)
    return {
        "oracle_value": oracle,
        "fixed_value": fixed,
        "gap": oracle - fixed,
        "best_fixed_action_index": fixed_values.index(fixed),
    }


def treatment_effects_against(
    matrix: Sequence[Sequence[float]],
    *,
    baseline_action: int,
) -> list[list[float]]:
    """Return context-specific treatment effects relative to one fixed action."""
    _, n_actions = _matrix_shape(matrix)
    if not 0 <= baseline_action < n_actions:
        raise ValueError("baseline_action out of range")
    return [[float(value) - float(row[baseline_action]) for value in row] for row in matrix]


def destroy_interaction(matrix: Sequence[Sequence[float]]) -> list[list[float]]:
    """Project a matrix onto additive context + action main effects.

    The resulting matrix has no context×action interaction, hence one global action
    ranking and exactly zero oracle gap up to floating-point error.  It is the
    strongest structural null for the opportunity question.
    """
    n_contexts, n_actions = _matrix_shape(matrix)
    grand = sum(float(x) for row in matrix for x in row) / (n_contexts * n_actions)
    row_mean = [sum(map(float, row)) / n_actions for row in matrix]
    col_mean = [sum(float(matrix[c][a]) for c in range(n_contexts)) / n_contexts for a in range(n_actions)]
    return [[row_mean[c] + col_mean[a] - grand for a in range(n_actions)] for c in range(n_contexts)]


def collapse_context(matrix: Sequence[Sequence[float]]) -> list[list[float]]:
    """Remove all context information while preserving action marginal means."""
    n_contexts, n_actions = _matrix_shape(matrix)
    return [[sum(float(matrix[c][a]) for c in range(n_contexts)) / n_contexts for a in range(n_actions)]]


def _policy_probs(policy: Mapping[str, Mapping[str, float]], context: str, actions: Sequence[str]) -> dict[str, float]:
    if context not in policy:
        raise ValueError(f"target policy missing context {context!r}")
    probs = {a: float(policy[context].get(a, 0.0)) for a in actions}
    if any(p < 0 or not math.isfinite(p) for p in probs.values()):
        raise ValueError("target policy probabilities must be finite and non-negative")
    if not math.isclose(sum(probs.values()), 1.0, abs_tol=1e-9, rel_tol=0.0):
        raise ValueError("target policy probabilities must sum to one")
    return probs


def ips_policy_value(
    observations: Sequence[TrialObservation],
    target_policy: Mapping[str, Mapping[str, float]],
) -> float:
    """Inverse-propensity estimate of a target policy under known randomization."""
    if not observations:
        raise ValueError("observations must be non-empty")
    actions = tuple(sorted({o.action for o in observations}))
    total = 0.0
    for obs in observations:
        if not (0.0 < obs.propensity <= 1.0) or not math.isfinite(obs.propensity):
            raise ValueError("propensity must be in (0, 1]")
        probs = _policy_probs(target_policy, obs.context, actions)
        total += probs[obs.action] * obs.utility / obs.propensity
    return total / len(observations)


def doubly_robust_policy_value(
    observations: Sequence[TrialObservation],
    target_policy: Mapping[str, Mapping[str, float]],
) -> float:
    """Cross-fitted doubly-robust policy-value estimator.

    Either the known propensity model or the cross-fitted outcome model may be
    correct for consistency.  This implementation cannot verify cross-fitting;
    that provenance requirement is enforced by the experiment protocol/gate.
    """
    if not observations:
        raise ValueError("observations must be non-empty")
    actions = tuple(sorted({a for o in observations for a in o.outcome_model}))
    if not actions:
        raise ValueError("outcome_model must predict at least one action")
    total = 0.0
    for obs in observations:
        if obs.action not in actions or set(obs.outcome_model) != set(actions):
            raise ValueError("every outcome model must cover the same action set")
        if not (0.0 < obs.propensity <= 1.0) or not math.isfinite(obs.propensity):
            raise ValueError("propensity must be in (0, 1]")
        if not math.isfinite(obs.utility) or any(not math.isfinite(v) for v in obs.outcome_model.values()):
            raise ValueError("utilities and outcome-model predictions must be finite")
        probs = _policy_probs(target_policy, obs.context, actions)
        direct = sum(probs[a] * obs.outcome_model[a] for a in actions)
        correction = probs[obs.action] / obs.propensity * (obs.utility - obs.outcome_model[obs.action])
        total += direct + correction
    return total / len(observations)
