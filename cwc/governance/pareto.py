from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class MeanBound:
    n: int
    mean: float
    lower: float
    upper: float
    delta: float
    support_lower: float
    support_upper: float
    method: str = "FIXED_N_HOEFFDING_V1"


@dataclass(frozen=True, slots=True)
class ParetoCertificate:
    cost_gain: MeanBound
    quality_gain: MeanBound
    quality_noninferiority_margin: float
    certified_cost_reduction: bool
    certified_quality_noninferiority: bool
    certified_pareto_improvement: bool
    familywise_alpha: float
    method: str = "PAIRED_BONFERRONI_PARETO_V1"


def fixed_n_hoeffding_mean_bound(
    observations: Sequence[float], *, lower: float, upper: float, delta: float
) -> MeanBound:
    lower = float(lower)
    upper = float(upper)
    delta = float(delta)
    if not observations:
        raise ValueError("at least one observation required")
    if not math.isfinite(lower) or not math.isfinite(upper) or upper < lower:
        raise ValueError("finite lower <= upper required")
    if not 0.0 < delta < 1.0:
        raise ValueError("delta must be in (0,1)")
    vals = tuple(float(x) for x in observations)
    if any(not math.isfinite(x) or x < lower or x > upper for x in vals):
        raise ValueError("observation outside declared support")
    n = len(vals)
    mean = math.fsum(vals) / n
    if upper == lower:
        return MeanBound(n, mean, mean, mean, delta, lower, upper)
    width = (upper - lower) * math.sqrt(math.log(2.0 / delta) / (2.0 * n))
    return MeanBound(
        n=n,
        mean=mean,
        lower=max(lower, mean - width),
        upper=min(upper, mean + width),
        delta=delta,
        support_lower=lower,
        support_upper=upper,
    )


def certify_paired_pareto_improvement(
    *,
    baseline_minus_dgc_cost: Sequence[float],
    dgc_minus_baseline_quality: Sequence[float],
    cost_gain_support: tuple[float, float],
    quality_gain_support: tuple[float, float],
    alpha: float = 0.05,
    quality_noninferiority_margin: float = 0.0,
) -> ParetoCertificate:
    """Simultaneous paired inference for cost-quality Pareto improvement.

    Positive cost gain means DGC is cheaper. Positive quality gain means DGC is
    better. Bonferroni splits alpha across the two paired mean bounds, yielding
    simultaneous coverage >= 1-alpha without assuming independence between the
    metrics.
    """
    alpha = float(alpha)
    margin = float(quality_noninferiority_margin)
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0,1)")
    if not math.isfinite(margin) or margin < 0.0:
        raise ValueError("quality_noninferiority_margin must be finite and >= 0")
    if len(baseline_minus_dgc_cost) != len(dgc_minus_baseline_quality):
        raise ValueError("paired metrics must have equal length")
    per_metric = alpha / 2.0
    cost = fixed_n_hoeffding_mean_bound(
        baseline_minus_dgc_cost,
        lower=cost_gain_support[0], upper=cost_gain_support[1], delta=per_metric,
    )
    quality = fixed_n_hoeffding_mean_bound(
        dgc_minus_baseline_quality,
        lower=quality_gain_support[0], upper=quality_gain_support[1], delta=per_metric,
    )
    cheaper = cost.lower > 0.0
    noninferior = quality.lower >= -margin
    return ParetoCertificate(
        cost_gain=cost,
        quality_gain=quality,
        quality_noninferiority_margin=margin,
        certified_cost_reduction=cheaper,
        certified_quality_noninferiority=noninferior,
        certified_pareto_improvement=cheaper and noninferior,
        familywise_alpha=alpha,
    )
