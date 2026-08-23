from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence


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


@dataclass(frozen=True, slots=True)
class PairedBaselineEvidence:
    baseline_id: str
    paired_task_digest: str
    coverage: float
    baseline_minus_dgc_cost: tuple[float, ...]
    dgc_minus_baseline_quality: tuple[float, ...]
    baseline_minus_dgc_catastrophic_regret: tuple[float, ...]
    cost_gain_support: tuple[float, float]
    quality_gain_support: tuple[float, float]
    catastrophic_gain_support: tuple[float, float]

    def __post_init__(self) -> None:
        if not self.baseline_id.strip() or not self.paired_task_digest.strip():
            raise ValueError("baseline_id and paired_task_digest required")
        if not math.isfinite(float(self.coverage)) or not 0.0 <= float(self.coverage) <= 1.0:
            raise ValueError("coverage must be in [0,1]")
        n = len(self.baseline_minus_dgc_cost)
        if n == 0 or len(self.dgc_minus_baseline_quality) != n or len(self.baseline_minus_dgc_catastrophic_regret) != n:
            raise ValueError("three equal non-empty paired series required")


@dataclass(frozen=True, slots=True)
class BaselineParetoResult:
    baseline_id: str
    cost_gain: MeanBound
    quality_gain: MeanBound
    catastrophic_regret_gain: MeanBound
    certified_cost_reduction: bool
    certified_quality_noninferiority: bool
    certified_catastrophic_noninferiority: bool
    certified_pareto_improvement: bool


@dataclass(frozen=True, slots=True)
class MultiBaselineParetoCertificate:
    paired_task_digest: str
    results: tuple[BaselineParetoResult, ...]
    familywise_alpha: float
    per_metric_delta: float
    quality_noninferiority_margin: float
    catastrophic_noninferiority_margin: float
    all_baselines_certified: bool
    method: str = "PAIRED_MULTI_BASELINE_BONFERRONI_PARETO_V1"


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
    """Simultaneous paired inference for cost-quality Pareto improvement."""
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


def certify_multi_baseline_pareto_improvement(
    evidence: Sequence[PairedBaselineEvidence], *,
    alpha: float = 0.05,
    quality_noninferiority_margin: float = 0.0,
    catastrophic_noninferiority_margin: float = 0.0,
) -> MultiBaselineParetoCertificate:
    """Familywise simultaneous DGC dominance certificate over K paired baselines.

    For every baseline we certify three paired means on the SAME frozen task set:
    cost gain (baseline-DGC), quality gain (DGC-baseline), and catastrophic-regret
    gain (baseline-DGC, so positive is safer). Bonferroni allocates alpha/(3K)
    to each two-sided Hoeffding interval. The union bound gives simultaneous
    coverage at least 1-alpha without independence assumptions across baselines
    or metrics. Coverage must be exactly one and task digests/sample sizes must
    match, preventing selective-coverage and benchmark-subset gaming.
    """
    rows = tuple(evidence)
    if not rows:
        raise ValueError("at least one baseline required")
    alpha = float(alpha)
    qmargin = float(quality_noninferiority_margin)
    cmargin = float(catastrophic_noninferiority_margin)
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0,1)")
    if any(not math.isfinite(m) or m < 0.0 for m in (qmargin, cmargin)):
        raise ValueError("noninferiority margins must be finite and >=0")
    ids = [r.baseline_id for r in rows]
    if len(set(ids)) != len(ids):
        raise ValueError("baseline ids must be unique")
    digests = {r.paired_task_digest for r in rows}
    ns = {len(r.baseline_minus_dgc_cost) for r in rows}
    if len(digests) != 1 or len(ns) != 1:
        raise ValueError("all baselines must use the same paired task population")
    if any(not math.isclose(float(r.coverage), 1.0, rel_tol=0.0, abs_tol=1e-12) for r in rows):
        raise ValueError("full matched coverage is required")

    delta = alpha / (3.0 * len(rows))
    results: list[BaselineParetoResult] = []
    for row in sorted(rows, key=lambda r: r.baseline_id):
        cost = fixed_n_hoeffding_mean_bound(
            row.baseline_minus_dgc_cost, lower=row.cost_gain_support[0], upper=row.cost_gain_support[1], delta=delta
        )
        quality = fixed_n_hoeffding_mean_bound(
            row.dgc_minus_baseline_quality, lower=row.quality_gain_support[0], upper=row.quality_gain_support[1], delta=delta
        )
        catastrophic = fixed_n_hoeffding_mean_bound(
            row.baseline_minus_dgc_catastrophic_regret,
            lower=row.catastrophic_gain_support[0], upper=row.catastrophic_gain_support[1], delta=delta,
        )
        cheaper = cost.lower > 0.0
        quality_ok = quality.lower >= -qmargin
        catastrophic_ok = catastrophic.lower >= -cmargin
        results.append(BaselineParetoResult(
            baseline_id=row.baseline_id,
            cost_gain=cost,
            quality_gain=quality,
            catastrophic_regret_gain=catastrophic,
            certified_cost_reduction=cheaper,
            certified_quality_noninferiority=quality_ok,
            certified_catastrophic_noninferiority=catastrophic_ok,
            certified_pareto_improvement=cheaper and quality_ok and catastrophic_ok,
        ))
    return MultiBaselineParetoCertificate(
        paired_task_digest=next(iter(digests)),
        results=tuple(results),
        familywise_alpha=alpha,
        per_metric_delta=delta,
        quality_noninferiority_margin=qmargin,
        catastrophic_noninferiority_margin=cmargin,
        all_baselines_certified=all(r.certified_pareto_improvement for r in results),
    )
