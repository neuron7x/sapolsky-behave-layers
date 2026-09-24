from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class DriftDirection(str, Enum):
    UP = "UP"
    DOWN = "DOWN"


@dataclass(frozen=True, slots=True)
class DriftSensitivityCertificate:
    direction: DriftDirection
    horizon: int
    baseline_mean: float
    tolerance: float
    alternative_mean: float
    constant_lambda: float
    alarm_sample_mean_threshold: float
    detection_power_lower_bound: float
    minimum_required_power: float
    deployment_guard_satisfied: bool
    alpha: float
    method: str = "INDEPENDENT_BOUNDED_EPROCESS_POWER_LOWER_BOUND_V1"


def certify_drift_detection_sensitivity(*, lower: float, upper: float, baseline_mean: float, tolerance: float, alternative_mean: float, direction: DriftDirection, horizon: int, alpha: float = 0.05, minimum_required_power: float = 0.8) -> DriftSensitivityCertificate:
    """Lower-bound probability of an anytime e-process alarm by a fixed horizon.

    The deployed detector is anytime-valid under its conditional-mean null. This
    separate sensitivity theorem assumes a post-change block of independent
    bounded observations with fixed mean `alternative_mean`. We choose one
    constant lambda before the block, optimized for the declared horizon.

    For an upward alarm, e_n crosses when
      Xbar >= b+tol + width*(lambda/8 + log(2/alpha)/(n*lambda)).
    Hoeffding lower-bounds the probability of this event under a fixed alternative
    mean. The downward case is symmetric. Since crossing at n implies an alarm by
    n, this is a conservative detection-power lower bound.

    No claim is made for adversarial dependence, transient shifts, or alternatives
    smaller than the declared shift floor.
    """
    lower=float(lower); upper=float(upper); b=float(baseline_mean); tol=float(tolerance); alt=float(alternative_mean); alpha=float(alpha); min_power=float(minimum_required_power)
    if not all(math.isfinite(x) for x in (lower,upper,b,tol,alt,alpha,min_power)) or upper<=lower:
        raise ValueError("finite lower < upper and finite parameters required")
    if horizon<=0 or not 0<alpha<1 or not 0<=min_power<=1 or tol<0:
        raise ValueError("invalid horizon/alpha/power/tolerance")
    if not lower<=b<=upper or not lower<=alt<=upper or b-tol<lower-1e-12 or b+tol>upper+1e-12:
        raise ValueError("means/tolerance band outside support")
    if not isinstance(direction,DriftDirection): direction=DriftDirection(direction)
    width=upper-lower; logthr=math.log(2.0/alpha); n=int(horizon)
    lam=math.sqrt(8.0*logthr/n)
    normalized_margin=lam/8.0 + logthr/(n*lam)
    if direction is DriftDirection.UP:
        if alt<=b+tol: raise ValueError("upward alternative must exceed null boundary")
        threshold=b+tol+width*normalized_margin
        separation=alt-threshold
    else:
        if alt>=b-tol: raise ValueError("downward alternative must be below null boundary")
        threshold=b-tol-width*normalized_margin
        separation=threshold-alt
    if separation<=0:
        power=0.0
    else:
        power=max(0.0,min(1.0,1.0-math.exp(-2.0*n*(separation/width)**2)))
    return DriftSensitivityCertificate(direction,n,b,tol,alt,lam,threshold,power,min_power,power+1e-15>=min_power,alpha)
