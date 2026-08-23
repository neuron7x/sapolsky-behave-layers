from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from cwc.governance.adaptive_eprocess import AdaptiveImportanceSample, adaptive_importance_mean_eprocess
from cwc.governance.restricted_sampling import RestrictedAdaptiveSamplingPolicy


@dataclass(frozen=True, slots=True)
class AnytimeAdaptiveRiskCertificate:
    n: int
    risk_threshold: float
    risk_upper_confidence_bound: float
    safety_lower_confidence_bound: float
    e_value: float
    alpha: float
    certified_risk_control: bool
    sampling_policy_digest: str
    sampling_trace_digest: str
    method: str = "RESTRICTED_ADAPTIVE_IPW_ANYTIME_RISK_V1"


def certify_anytime_adaptive_risk(
    loss_samples: Sequence[AdaptiveImportanceSample], *,
    sampling_policy: RestrictedAdaptiveSamplingPolicy,
    sampling_trace_digest: str,
    risk_threshold: float,
    alpha: float,
    predictable_lambdas: Sequence[float],
    predictable_lambda_attested: bool,
) -> AnytimeAdaptiveRiskCertificate:
    """Anytime-valid target-risk certificate in the restricted DGC sampling class.

    Loss L is bounded in [0,1]. Define safety Y=1-L. The target risk condition
    E_q[L] <= r is equivalent to E_q[Y] >= 1-r. We therefore reuse the existing
    predictable-propensity IPW e-process on Y and test H0:E_q[Y] <= 1-r.

    Authority is deliberately narrow: the target distribution is frozen by the
    certified policy, propensities are logged before outcomes, importance weights
    are bounded by policy, and lambda_t must be predictable. This does not claim
    arbitrary adaptive-labeling or nonstationary-population risk control.
    """
    r = float(risk_threshold); alpha = float(alpha)
    if not 0.0 <= r <= 1.0 or not 0.0 < alpha < 1.0:
        raise ValueError("risk_threshold in [0,1] and alpha in (0,1) required")
    if not predictable_lambda_attested:
        raise ValueError("predictable lambda authority required")
    if not sampling_trace_digest.strip():
        raise ValueError("sampling_trace_digest required")
    if not loss_samples:
        raise ValueError("loss samples required")
    target = dict(sampling_policy.target_distribution)
    safety: list[AdaptiveImportanceSample] = []
    for sample in loss_samples:
        loss = float(sample.value)
        if not math.isfinite(loss) or loss < 0.0 or loss > 1.0:
            raise ValueError("loss must lie in [0,1]")
        safety.append(AdaptiveImportanceSample(sample.item_id, 1.0-loss, sample.selection_probability))
    ep = adaptive_importance_mean_eprocess(
        safety,
        target_distribution=target,
        lower=0.0,
        upper=1.0,
        alpha=alpha,
        lambdas=predictable_lambdas,
        max_importance_weight=sampling_policy.max_importance_weight,
        null_mean=1.0-r,
    )
    risk_ucb = min(1.0, max(0.0, 1.0-ep.lower_confidence_bound))
    return AnytimeAdaptiveRiskCertificate(
        n=len(safety),
        risk_threshold=r,
        risk_upper_confidence_bound=risk_ucb,
        safety_lower_confidence_bound=ep.lower_confidence_bound,
        e_value=ep.e_value,
        alpha=alpha,
        certified_risk_control=bool(ep.rejects and risk_ucb <= r + 1e-15),
        sampling_policy_digest=sampling_policy.policy_digest,
        sampling_trace_digest=sampling_trace_digest,
    )
