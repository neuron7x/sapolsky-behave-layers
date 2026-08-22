from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class FinancialGateResult:
    n: int
    mean_reference_cost: float
    mean_dgc_core_cost: float
    mean_governance_overhead: float
    mean_dgc_total_cost: float
    net_inference_savings: float
    savings_lcb: float
    savings_ucb: float
    delta_quality: float
    quality_lcb: float
    quality_ucb: float
    threshold: float
    threshold_met: bool
    max_mean_overhead_for_threshold: float
    method: str


def _fixed_n_hoeffding(values: Sequence[float], lo: float, hi: float, delta: float) -> tuple[float, float, float]:
    if not values or not (0 < delta < 1) or hi < lo:
        raise ValueError("invalid fixed-n Hoeffding inputs")
    mean = sum(values) / len(values)
    if hi == lo:
        return mean, mean, mean
    radius = (hi - lo) * math.sqrt(math.log(2.0 / delta) / (2.0 * len(values)))
    return mean, max(lo, mean - radius), min(hi, mean + radius)


def _stratified_bound(
    values: Sequence[float], strata: Sequence[str], *, lo: float, hi: float, delta: float
) -> tuple[float, float, float]:
    if len(values) != len(strata) or not values:
        raise ValueError("paired values/strata required")
    groups: dict[str, list[float]] = {}
    for value, stratum in zip(values, strata):
        groups.setdefault(str(stratum), []).append(float(value))
    keys = sorted(groups)
    counts = {len(groups[k]) for k in keys}
    if len(counts) != 1:
        raise ValueError("financial stratified contract requires equal sample count per regime")
    per_delta = delta / len(keys)
    parts = [_fixed_n_hoeffding(groups[k], lo, hi, per_delta) for k in keys]
    weight = 1.0 / len(parts)
    return (
        sum(x[0] for x in parts) * weight,
        sum(x[1] for x in parts) * weight,
        sum(x[2] for x in parts) * weight,
    )


def evaluate_financial_gate(
    *,
    reference_costs: Sequence[float],
    dgc_core_costs: Sequence[float],
    reference_losses: Sequence[float],
    dgc_losses: Sequence[float],
    governance_overhead_per_task: float,
    strata: Sequence[str] | None = None,
    threshold: float = 0.30,
    delta: float = 0.05,
    max_reference_cost: float = 0.12,
    max_dgc_core_cost: float = 0.12,
    max_loss: float = 1.6,
) -> FinancialGateResult:
    n = len(reference_costs)
    if n == 0 or not (n == len(dgc_core_costs) == len(reference_losses) == len(dgc_losses)):
        raise ValueError("paired non-empty sequences required")
    if strata is not None and len(strata) != n:
        raise ValueError("strata must align with paired sequences")
    if governance_overhead_per_task < 0:
        raise ValueError("governance overhead must be non-negative")
    if not (0 < delta < 1) or not (0 <= threshold < 1):
        raise ValueError("invalid delta/threshold")

    ref = [float(x) for x in reference_costs]
    core = [float(x) for x in dgc_core_costs]
    dgc = [x + governance_overhead_per_task for x in core]
    deltas = [r - d for r, d in zip(ref, dgc)]
    qd = [float(lr) - float(ld) for lr, ld in zip(reference_losses, dgc_losses)]
    if any(x < 0 or x > max_reference_cost for x in ref):
        raise ValueError("reference cost outside frozen support")
    max_dgc_total = max_dgc_core_cost + governance_overhead_per_task
    if any(x < 0 or x > max_dgc_total + 1e-15 for x in dgc):
        raise ValueError("DGC cost outside frozen support")
    if any(x < -max_loss or x > max_loss for x in qd):
        raise ValueError("quality delta outside frozen support")

    mean_ref = sum(ref) / n
    mean_core = sum(core) / n
    mean_total = sum(dgc) / n
    if mean_ref <= 0:
        raise ValueError("positive reference mean cost required")
    point_savings = (mean_ref - mean_total) / mean_ref

    component_delta = delta / 3.0
    delta_lo, delta_hi = -max_dgc_total, max_reference_cost
    if strata is None:
        _, d_lo, d_hi = _fixed_n_hoeffding(deltas, delta_lo, delta_hi, component_delta)
        _, r_lo, r_hi = _fixed_n_hoeffding(ref, 0.0, max_reference_cost, component_delta)
        _, q_lo, q_hi = _fixed_n_hoeffding(qd, -max_loss, max_loss, component_delta)
        method = "FIXED_N_HOEFFDING_BONFERRONI_V1"
    else:
        _, d_lo, d_hi = _stratified_bound(deltas, strata, lo=delta_lo, hi=delta_hi, delta=component_delta)
        _, r_lo, r_hi = _stratified_bound(ref, strata, lo=0.0, hi=max_reference_cost, delta=component_delta)
        _, q_lo, q_hi = _stratified_bound(qd, strata, lo=-max_loss, hi=max_loss, delta=component_delta)
        method = "STRATIFIED_FIXED_N_HOEFFDING_BONFERRONI_V1"

    if r_hi <= 0:
        raise RuntimeError("invalid non-positive reference upper bound")
    savings_lcb = d_lo / r_hi
    savings_ucb = d_hi / max(r_lo, 1e-15)

    mean_q = sum(qd) / n
    exact_quality_equality = all(x == 0.0 for x in qd)
    quality_lcb = 0.0 if exact_quality_equality else q_lo
    quality_ucb = 0.0 if exact_quality_equality else q_hi

    max_overhead = (1.0 - threshold) * mean_ref - mean_core
    return FinancialGateResult(
        n=n,
        mean_reference_cost=mean_ref,
        mean_dgc_core_cost=mean_core,
        mean_governance_overhead=governance_overhead_per_task,
        mean_dgc_total_cost=mean_total,
        net_inference_savings=point_savings,
        savings_lcb=savings_lcb,
        savings_ucb=savings_ucb,
        delta_quality=mean_q,
        quality_lcb=quality_lcb,
        quality_ucb=quality_ucb,
        threshold=threshold,
        threshold_met=savings_lcb >= threshold and quality_lcb >= 0.0,
        max_mean_overhead_for_threshold=max_overhead,
        method=method,
    )
