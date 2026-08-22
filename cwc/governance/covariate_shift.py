from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class CovariateShiftMeanLowerBound:
    n: int
    weighted_normalized_mean: float
    concentration_radius: float
    ratio_induced_mean_error_budget: float
    target_mean_lower: float
    confidence: float
    max_density_ratio: float
    weight_authority_digest: str
    method: str = "KNOWN_RATIO_COVARIATE_SHIFT_HOEFFDING_LCB_V1"


def target_mean_lcb_under_covariate_shift(
    values: Sequence[float], density_ratios: Sequence[float], *,
    lower: float, upper: float, delta: float, max_density_ratio: float,
    ratio_induced_mean_error_budget: float, weight_authority_digest: str,
) -> CovariateShiftMeanLowerBound:
    """Finite-sample target-mean LCB under source-to-target covariate shift.

    Source samples are iid P. For normalized Y in [0,1], exact density ratio
    w=dQ/dP gives E_P[wY]=E_Q[Y]. With 0<=w<=W, wY lies in [0,W], so Hoeffding
    applies. If approximate weights are used, an EXTERNAL authority may provide
    epsilon >= |E_P[(w_hat-w)Y]|; epsilon is subtracted. This is a target-mean
    guarantee, not per-example conformal coverage, and it is invalid under
    unbounded/unsupported target shift or post-hoc weight-error budgets.
    """
    if not values or len(values) != len(density_ratios):
        raise ValueError("equal non-empty values and density ratios required")
    lower, upper, delta = float(lower), float(upper), float(delta)
    wmax, eps = float(max_density_ratio), float(ratio_induced_mean_error_budget)
    if not weight_authority_digest.strip():
        raise ValueError("weight authority digest required")
    if not math.isfinite(lower) or not math.isfinite(upper) or upper <= lower:
        raise ValueError("finite lower < upper required")
    if not 0.0 < delta < 1.0 or not math.isfinite(wmax) or wmax <= 0.0:
        raise ValueError("valid delta and positive finite max_density_ratio required")
    if not math.isfinite(eps) or eps < 0.0:
        raise ValueError("ratio-induced mean error budget must be finite and >=0")
    width = upper - lower
    zs = []
    for raw_y, raw_w in zip(values, density_ratios, strict=True):
        y, w = float(raw_y), float(raw_w)
        if not math.isfinite(y) or y < lower or y > upper:
            raise ValueError("value outside declared support")
        if not math.isfinite(w) or w < 0.0 or w > wmax + 1e-12:
            raise ValueError("density ratio outside declared cap")
        zs.append(w * ((y - lower) / width))
    n = len(zs)
    mean_z = math.fsum(zs) / n
    radius = wmax * math.sqrt(math.log(1.0 / delta) / (2.0 * n))
    lcb_norm = max(0.0, min(1.0, mean_z - radius - eps))
    return CovariateShiftMeanLowerBound(
        n=n, weighted_normalized_mean=mean_z, concentration_radius=radius,
        ratio_induced_mean_error_budget=eps,
        target_mean_lower=lower + width * lcb_norm,
        confidence=1.0-delta, max_density_ratio=wmax,
        weight_authority_digest=weight_authority_digest,
    )
