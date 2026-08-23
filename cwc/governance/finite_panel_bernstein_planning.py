from __future__ import annotations

import math
from dataclasses import dataclass

METHOD = "EMPIRICAL_BERNSTEIN_WIDTH_PLANNING_V1"


@dataclass(frozen=True, slots=True)
class BernsteinPlanningResult:
    variance_proxy: float
    support_range: float
    target_half_width: float
    delta: float
    task_count: int
    required_total_observations: int
    required_replicates_per_task: int
    achieved_proxy_half_width: float
    method: str = METHOD


def empirical_bernstein_proxy_half_width(
    *,
    sample_variance_proxy: float,
    support_range: float,
    n: int,
    delta: float,
) -> float:
    """Planning proxy using the Maurer-Pontil Theorem-11 bound form.

    The sample variance is unknown before confirmatory execution, so this function
    accepts a frozen calibration-derived proxy. The result is planning-only and is
    never a substitute for the final observed-sample empirical-Bernstein bound.
    """
    variance_proxy = float(sample_variance_proxy)
    width = float(support_range)
    delta = float(delta)
    n = int(n)
    if not math.isfinite(variance_proxy) or variance_proxy < 0.0:
        raise ValueError("sample_variance_proxy must be finite and >= 0")
    if not math.isfinite(width) or width <= 0.0:
        raise ValueError("support_range must be finite and > 0")
    if n < 2:
        raise ValueError("n must be >= 2")
    if not 0.0 < delta < 1.0:
        raise ValueError("delta must be in (0,1)")
    # Any bounded variable on an interval of length width has variance <= width^2 / 4.
    if variance_proxy > width * width / 4.0 + 1e-15:
        raise ValueError("sample_variance_proxy exceeds the bounded-variance ceiling")
    log_term = math.log(2.0 / delta)
    return math.sqrt(2.0 * variance_proxy * log_term / n) + (
        7.0 * width * log_term / (3.0 * (n - 1))
    )


def required_replicates_for_proxy_width(
    *,
    sample_variance_proxy: float,
    support_range: float,
    target_half_width: float,
    delta: float,
    task_count: int,
    max_replicates_per_task: int,
) -> BernsteinPlanningResult:
    """Smallest integer R such that proxy width(N_tasks*R) <= target.

    This is a deterministic resource-planning calculation, not a power theorem.
    Confirmatory promotion must recompute the bound from the observed sample variance.
    """
    target = float(target_half_width)
    tasks = int(task_count)
    max_r = int(max_replicates_per_task)
    if not math.isfinite(target) or target <= 0.0:
        raise ValueError("target_half_width must be finite and > 0")
    if tasks <= 0 or max_r <= 0:
        raise ValueError("task_count and max_replicates_per_task must be > 0")

    def width_for(r: int) -> float:
        return empirical_bernstein_proxy_half_width(
            sample_variance_proxy=sample_variance_proxy,
            support_range=support_range,
            n=tasks * r,
            delta=delta,
        )

    if tasks * max_r < 2 or width_for(max_r) > target:
        raise RuntimeError(
            "UNDERPOWERED_EMPIRICAL_BERNSTEIN_PROXY: frozen replicate cap cannot meet planning width"
        )
    lo, hi = 1, max_r
    while lo < hi:
        mid = (lo + hi) // 2
        if tasks * mid >= 2 and width_for(mid) <= target:
            hi = mid
        else:
            lo = mid + 1
    achieved = width_for(lo)
    return BernsteinPlanningResult(
        variance_proxy=float(sample_variance_proxy),
        support_range=float(support_range),
        target_half_width=target,
        delta=float(delta),
        task_count=tasks,
        required_total_observations=tasks * lo,
        required_replicates_per_task=lo,
        achieved_proxy_half_width=achieved,
    )
