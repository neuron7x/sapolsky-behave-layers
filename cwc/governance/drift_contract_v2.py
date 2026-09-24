from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class DriftAdjustedMeanBound:
    n: int
    sample_mean: float
    stationary_lower: float
    average_drift_budget: float
    current_mean_lower: float
    confidence: float
    lower: float
    upper: float
    method: str = "INDEPENDENT_BOUNDED_DRIFT_HOEFFDING_V1"


def bounded_drift_current_mean_lcb(
    observations: Sequence[float],
    *,
    lower: float,
    upper: float,
    delta: float,
    drift_to_current: Sequence[float],
) -> DriftAdjustedMeanBound:
    """Lower confidence bound for a current mean under an external drift envelope.

    Assumptions:
    - X_i are independent and X_i in [lower, upper].
    - mu_i = E[X_i].
    - an external authority certifies |mu_i - mu_T| <= d_i for each i.

    Hoeffding gives a lower bound on the average historical mean. Since
    mu_T >= average(mu_i) - average(d_i), subtracting the average certified
    drift budget yields a valid lower bound for the current mean.

    This is NOT valid for arbitrary dependence, adversarially chosen envelopes,
    or post-hoc drift budgets.
    """
    if not observations:
        raise ValueError("at least one observation required")
    if len(observations) != len(drift_to_current):
        raise ValueError("one drift budget per observation required")
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
        raise ValueError("drift budgets must be finite and >=0")

    n = len(xs)
    mean = math.fsum(xs) / n
    width = upper - lower
    radius = width * math.sqrt(math.log(1.0 / delta) / (2.0 * n))
    stationary = max(lower, mean - radius)
    avg_drift = math.fsum(ds) / n
    current = max(lower, stationary - avg_drift)
    return DriftAdjustedMeanBound(
        n=n,
        sample_mean=mean,
        stationary_lower=stationary,
        average_drift_budget=avg_drift,
        current_mean_lower=current,
        confidence=1.0 - delta,
        lower=lower,
        upper=upper,
    )
