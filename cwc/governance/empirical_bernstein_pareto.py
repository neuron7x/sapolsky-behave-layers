from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from statistics import fmean, variance
from typing import Sequence

from cwc.governance.pareto import MeanBound, PairedBaselineEvidence

METHOD = "PAIRED_MULTI_BASELINE_BONFERRONI_EMPIRICAL_BERNSTEIN_LOWER_V1"
BOUND_METHOD = "MAURER_PONTIL_THEOREM_11_EMPIRICAL_BERNSTEIN_LOWER_V1"


def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class EmpiricalBernsteinBaselineResult:
    baseline_id: str
    cost_gain: MeanBound
    quality_gain: MeanBound
    catastrophic_regret_gain: MeanBound
    certified_cost_reduction: bool
    certified_quality_noninferiority: bool
    certified_catastrophic_noninferiority: bool
    certified_pareto_improvement: bool


@dataclass(frozen=True, slots=True)
class EmpiricalBernsteinMultiBaselineCertificate:
    paired_task_digest: str
    results: tuple[EmpiricalBernsteinBaselineResult, ...]
    familywise_alpha: float
    per_metric_delta: float
    quality_noninferiority_margin: float
    catastrophic_noninferiority_margin: float
    all_baselines_certified: bool
    evidence_manifest_digest: str
    method: str = METHOD


def empirical_bernstein_lower_bound(
    observations: Sequence[float],
    *,
    lower: float,
    upper: float,
    delta: float,
) -> MeanBound:
    """One-sided finite-sample lower bound for independent bounded variables.

    This is Maurer & Pontil (2009), Theorem 11, rescaled from [0, 1] to
    [lower, upper] and applied to -X for a lower confidence bound. The theorem
    permits independent variables that are not identically distributed. The
    caller remains responsible for establishing or explicitly declaring the
    cross-observation independence assumption.

    `upper` in the returned MeanBound is the deterministic support endpoint;
    product gates consume only the certified lower endpoint.
    """
    values = tuple(float(x) for x in observations)
    if len(values) < 2:
        raise ValueError("empirical Bernstein requires at least two observations")
    lower = float(lower)
    upper = float(upper)
    delta = float(delta)
    if not (math.isfinite(lower) and math.isfinite(upper) and lower < upper):
        raise ValueError("finite ordered support required")
    if not 0.0 < delta < 1.0:
        raise ValueError("delta must be in (0,1)")
    if any((not math.isfinite(x)) or x < lower - 1e-12 or x > upper + 1e-12 for x in values):
        raise ValueError("observation outside declared support")

    n = len(values)
    mean = fmean(values)
    sample_variance = variance(values)
    log_term = math.log(2.0 / delta)
    width = math.sqrt(2.0 * sample_variance * log_term / n)
    width += 7.0 * (upper - lower) * log_term / (3.0 * (n - 1))
    lower_bound = max(lower, mean - width)
    return MeanBound(
        n=n,
        mean=mean,
        lower=lower_bound,
        upper=upper,
        delta=delta,
        support_lower=lower,
        support_upper=upper,
        method=BOUND_METHOD,
    )


def certify_multi_baseline_empirical_bernstein(
    evidence: Sequence[PairedBaselineEvidence],
    *,
    alpha: float,
    quality_noninferiority_margin: float,
    catastrophic_noninferiority_margin: float,
) -> EmpiricalBernsteinMultiBaselineCertificate:
    rows = tuple(evidence)
    if not rows:
        raise ValueError("at least one baseline required")
    alpha = float(alpha)
    qmargin = float(quality_noninferiority_margin)
    cmargin = float(catastrophic_noninferiority_margin)
    if len({row.baseline_id for row in rows}) != len(rows):
        raise ValueError("baseline ids must be unique")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0,1)")
    if any(not math.isfinite(value) or value < 0.0 for value in (qmargin, cmargin)):
        raise ValueError("non-inferiority margins must be finite and >= 0")

    paired_digests = {row.paired_task_digest for row in rows}
    ns = {len(row.baseline_minus_dgc_cost) for row in rows}
    if len(paired_digests) != 1 or len(ns) != 1:
        raise ValueError("all baselines must use the same paired observation population")
    if any(not math.isclose(float(row.coverage), 1.0, rel_tol=0.0, abs_tol=1e-12) for row in rows):
        raise ValueError("full paired coverage is required")

    per_metric_delta = alpha / (len(rows) * 3)
    results: list[EmpiricalBernsteinBaselineResult] = []
    evidence_manifest: list[dict[str, object]] = []
    for row in sorted(rows, key=lambda item: item.baseline_id):
        n = len(row.baseline_minus_dgc_cost)
        if n < 2 or len(row.dgc_minus_baseline_quality) != n or len(row.baseline_minus_dgc_catastrophic_regret) != n:
            raise ValueError("paired metric vectors must have the same length >= 2")

        cost = empirical_bernstein_lower_bound(
            row.baseline_minus_dgc_cost,
            lower=row.cost_gain_support[0],
            upper=row.cost_gain_support[1],
            delta=per_metric_delta,
        )
        quality = empirical_bernstein_lower_bound(
            row.dgc_minus_baseline_quality,
            lower=row.quality_gain_support[0],
            upper=row.quality_gain_support[1],
            delta=per_metric_delta,
        )
        catastrophic = empirical_bernstein_lower_bound(
            row.baseline_minus_dgc_catastrophic_regret,
            lower=row.catastrophic_gain_support[0],
            upper=row.catastrophic_gain_support[1],
            delta=per_metric_delta,
        )
        cheaper = cost.lower > 0.0
        quality_ok = quality.lower >= -qmargin
        catastrophic_ok = catastrophic.lower >= -cmargin
        results.append(EmpiricalBernsteinBaselineResult(
            baseline_id=row.baseline_id,
            cost_gain=cost,
            quality_gain=quality,
            catastrophic_regret_gain=catastrophic,
            certified_cost_reduction=cheaper,
            certified_quality_noninferiority=quality_ok,
            certified_catastrophic_noninferiority=catastrophic_ok,
            certified_pareto_improvement=cheaper and quality_ok and catastrophic_ok,
        ))
        evidence_manifest.append({
            "baseline_id": row.baseline_id,
            "paired_task_digest": row.paired_task_digest,
            "coverage": row.coverage,
            "n": n,
            "cost_series_digest": _digest(row.baseline_minus_dgc_cost),
            "quality_series_digest": _digest(row.dgc_minus_baseline_quality),
            "catastrophic_series_digest": _digest(row.baseline_minus_dgc_catastrophic_regret),
            "cost_support": row.cost_gain_support,
            "quality_support": row.quality_gain_support,
            "catastrophic_support": row.catastrophic_gain_support,
        })

    all_certified = all(row.certified_pareto_improvement for row in results)
    return EmpiricalBernsteinMultiBaselineCertificate(
        paired_task_digest=next(iter(paired_digests)),
        results=tuple(results),
        familywise_alpha=alpha,
        per_metric_delta=per_metric_delta,
        quality_noninferiority_margin=qmargin,
        catastrophic_noninferiority_margin=cmargin,
        all_baselines_certified=all_certified,
        evidence_manifest_digest=_digest(evidence_manifest),
    )
