from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Mapping

from cwc.credit.ablation_shapley import AblationShapleyEstimate, ranked_by_absolute_credit


@dataclass(frozen=True, slots=True)
class ShadowCreditPolicy:
    version: str
    interval_z: float
    delta: float
    max_unique_forward_evaluations: int


@dataclass(frozen=True, slots=True)
class ShadowCreditDecision:
    state: str
    candidate: str | None
    sign: int | None
    reason: str
    policy_version: str
    architecture_authority: bool = False


def magnitude_intervals(
    estimate: AblationShapleyEstimate, *, z: float
) -> dict[str, tuple[float, float]]:
    out: dict[str, tuple[float, float]] = {}
    for name, mean in estimate.credits.items():
        variance = max(float(estimate.estimator_variance.get(name, 0.0)), 0.0)
        half = float(z) * math.sqrt(variance)
        magnitude = abs(float(mean))
        out[name] = (max(0.0, magnitude - half), magnitude + half)
    return out


def decide_shadow_credit(
    estimate: AblationShapleyEstimate,
    policy: ShadowCreditPolicy,
    *,
    context: str,
) -> ShadowCreditDecision:
    if estimate.unique_forward_evaluations > policy.max_unique_forward_evaluations:
        return ShadowCreditDecision(
            "ABSTAIN_COMPUTE_BUDGET", None, None, "UNIQUE_FORWARD_BUDGET_EXCEEDED", policy.version
        )
    if not estimate.variance_estimable:
        return ShadowCreditDecision(
            "ABSTAIN_UNRESOLVED_CREDIT", None, None, "ESTIMATOR_VARIANCE_NOT_ESTIMABLE", policy.version
        )
    ranked = ranked_by_absolute_credit(estimate.credits)
    top = ranked[0]
    intervals = magnitude_intervals(estimate, z=policy.interval_z)
    top_lower = intervals[top][0]
    other_upper = max(intervals[p][1] for p in ranked[1:]) if len(ranked) > 1 else 0.0
    if not (top_lower > other_upper + policy.delta):
        return ShadowCreditDecision(
            "ABSTAIN_UNRESOLVED_CREDIT", None, None, "CREDIT_MAGNITUDE_INTERVALS_OVERLAP", policy.version
        )
    mean = float(estimate.credits[top])
    sign = 0 if mean == 0 else (1 if mean > 0 else -1)
    return ShadowCreditDecision(
        "ACCEPT_SHADOW_CREDIT_CONTEXT_BOUND",
        top,
        sign,
        f"FROZEN_INTERVAL_SEPARATION_PASSED_IN_CONTEXT_{context}",
        policy.version,
        False,
    )
