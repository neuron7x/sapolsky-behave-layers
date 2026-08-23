from __future__ import annotations

import hashlib
import json
import math
from statistics import fmean, variance
from typing import Sequence

from cwc.governance.pareto import (
    BaselineParetoResult,
    EndpointNonInferiority,
    MeanBound,
    MultiBaselineParetoCertificate,
    PairedBaselineEvidence,
)

METHOD = "PAIRED_MULTI_BASELINE_BONFERRONI_EMPIRICAL_BERNSTEIN_LOWER_V1"
BOUND_METHOD = "MAURER_PONTIL_EMPIRICAL_BERNSTEIN_ONE_SIDED_LOWER_V1"


def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def empirical_bernstein_lower_bound(
    observations: Sequence[float],
    *,
    lower: float,
    upper: float,
    delta: float,
) -> MeanBound:
    """Finite-sample one-sided lower confidence bound for independent bounded variables.

    Uses the empirical Bernstein inequality of Maurer & Pontil (2009), Theorem 11,
    applied to -X. `upper` in the returned MeanBound is the deterministic support
    upper bound, not a simultaneously certified confidence upper endpoint. Product
    gates consume only `lower`.
    """
    values = tuple(float(x) for x in observations)
    if len(values) < 2:
        raise ValueError("empirical Bernstein requires at least two observations")
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
) -> MultiBaselineParetoCertificate:
    if not evidence:
        raise ValueError("at least one baseline required")
    if len({row.baseline_id for row in evidence}) != len(evidence):
        raise ValueError("baseline ids must be unique")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0,1)")
    if quality_noninferiority_margin < 0 or catastrophic_noninferiority_margin < 0:
        raise ValueError("non-inferiority margins must be >= 0")
    paired_digests = {row.paired_task_digest for row in evidence}
    if len(paired_digests) != 1:
        raise ValueError("all baselines must use the exact same paired task population")
    per_metric_delta = alpha / (len(evidence) * 3)
    results: list[BaselineParetoResult] = []
    evidence_manifest: list[dict[str, object]] = []
    for row in sorted(evidence, key=lambda item: item.baseline_id):
        n = len(row.baseline_minus_dgc_cost)
        if n < 2 or len(row.dgc_minus_baseline_quality) != n or len(row.baseline_minus_dgc_catastrophic_regret) != n:
            raise ValueError("paired metric vectors must have the same length >= 2")
        if not math.isclose(row.coverage, 1.0, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("full paired coverage is required")
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
        quality_ni = EndpointNonInferiority(
            point_delta=quality.mean,
            lower_bound=quality.lower,
            margin=quality_noninferiority_margin,
            certified=quality.lower >= -quality_noninferiority_margin,
        )
        catastrophic_ni = EndpointNonInferiority(
            point_delta=catastrophic.mean,
            lower_bound=catastrophic.lower,
            margin=catastrophic_noninferiority_margin,
            certified=catastrophic.lower >= -catastrophic_noninferiority_margin,
        )
        result = BaselineParetoResult(
            baseline_id=row.baseline_id,
            cost_gain=cost,
            quality=quality_ni,
            catastrophic_regret=catastrophic_ni,
            cost_superiority_certified=cost.lower > 0.0,
        )
        results.append(result)
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
    all_certified = all(
        result.cost_superiority_certified
        and result.quality.certified
        and result.catastrophic_regret.certified
        for result in results
    )
    payload = {
        "alpha": alpha,
        "per_metric_delta": per_metric_delta,
        "quality_noninferiority_margin": quality_noninferiority_margin,
        "catastrophic_noninferiority_margin": catastrophic_noninferiority_margin,
        "paired_task_digest": next(iter(paired_digests)),
        "evidence_manifest": evidence_manifest,
        "method": METHOD,
    }
    return MultiBaselineParetoCertificate(
        alpha=alpha,
        per_metric_delta=per_metric_delta,
        quality_noninferiority_margin=quality_noninferiority_margin,
        catastrophic_noninferiority_margin=catastrophic_noninferiority_margin,
        paired_task_digest=next(iter(paired_digests)),
        results=tuple(results),
        all_baselines_certified=all_certified,
        certificate_digest=_digest(payload),
        method=METHOD,
    )
