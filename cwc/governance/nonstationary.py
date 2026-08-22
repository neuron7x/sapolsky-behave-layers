from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class BoundedDriftMeanBound:
    n: int
    sample_mean: float
    stationary_mean_lower: float
    average_drift_budget: float
    current_mean_lower: float
    delta: float
    observation_lower: float
    observation_upper: float
    method: str = "INDEPENDENT_BOUNDED_DRIFT_HOEFFDING_V1"


def current_mean_lower_bound_under_bounded_drift(
    observations: Sequence[float],
    *,
    drift_to_current: Sequence[float],
    lower: float,
    upper: float,
    delta: float,
) -> BoundedDriftMeanBound:
    """Finite-n LCB for a current mean under an externally bounded drift envelope.

    Let independent X_i in [L,H] have means mu_i. Let mu_* be the current
    target mean and suppose external authority guarantees |mu_i-mu_*| <= d_i.
    Hoeffding for independent bounded (not necessarily identically distributed)
    observations gives, with probability >=1-delta,

        mean(mu_i) >= mean(X_i) - (H-L)*sqrt(log(1/delta)/(2n)).

    Since mu_* >= mean(mu_i) - mean(d_i), subtract the average drift budget.
    The function does not estimate d_i from the same observations and does not
    cover adversarial dependence or an unbounded/change-after-observation drift.
    """
    if not observations or len(observations) != len(drift_to_current):
        raise ValueError("equal non-empty observations/drift bounds required")
    lower = float(lower)
    upper = float(upper)
    delta = float(delta)
    if not math.isfinite(lower) or not math.isfinite(upper) or upper <= lower:
        raise ValueError("finite lower < upper required")
    if not 0.0 < delta < 1.0:
        raise ValueError("delta must be in (0,1)")
    xs = [float(x) for x in observations]
    ds = [float(d) for d in drift_to_current]
    if any(not math.isfinite(x) or x < lower or x > upper for x in xs):
        raise ValueError("observation outside declared support")
    if any(not math.isfinite(d) or d < 0.0 for d in ds):
        raise ValueError("drift bounds must be finite and >= 0")
    n = len(xs)
    mean = math.fsum(xs) / n
    width = (upper - lower) * math.sqrt(math.log(1.0 / delta) / (2.0 * n))
    stationary_lcb = mean - width
    avg_drift = math.fsum(ds) / n
    current_lcb = max(lower, stationary_lcb - avg_drift)
    return BoundedDriftMeanBound(
        n=n,
        sample_mean=mean,
        stationary_mean_lower=stationary_lcb,
        average_drift_budget=avg_drift,
        current_mean_lower=current_lcb,
        delta=delta,
        observation_lower=lower,
        observation_upper=upper,
    )
