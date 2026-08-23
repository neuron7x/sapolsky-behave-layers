from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from statistics import fmean
from typing import Sequence

from cwc.governance.pareto import PairedBaselineEvidence

METHOD = "HOWARD_RAMDas_MCAULIFFE_SEKHON_EMPIRICAL_BERNSTEIN_CS_V1"
CLAIM_TARGET = "AVERAGE_CONDITIONAL_MEAN_OF_PRECOMMITTED_BOUNDED_SEQUENCE"
ASSUMPTION_BOUNDARY = "BOUNDED_ADAPTED_PROCESS_PREDICTABLE_VARIANCE_CENTER_NO_IID_REQUIRED"
SEQUENCE_ORDER_RULE = "TASK_ID_ASC_THEN_REPLICATE_ASC"

# Howard et al. (Annals of Statistics 2021) empirical-Bernstein stitching
# parameters recommended in later comparisons: eta=2, s=1.4.
ETA = 2.0
S = 1.4
# zeta(1.4), frozen to IEEE-754 double precision for deterministic replay.
ZETA_S = 3.1055472779775815


def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class AverageConditionalMeanBound:
    n: int
    sample_mean: float
    lower: float
    upper: float
    alpha: float
    support_lower: float
    support_upper: float
    empirical_variance_process: float
    half_width: float
    method: str = METHOD
    claim_target: str = CLAIM_TARGET
    assumption_boundary: str = ASSUMPTION_BOUNDARY


@dataclass(frozen=True, slots=True)
class AnytimeBaselineResult:
    baseline_id: str
    cost_gain: AverageConditionalMeanBound
    quality_gain: AverageConditionalMeanBound
    catastrophic_regret_gain: AverageConditionalMeanBound
    certified_cost_reduction: bool
    certified_quality_noninferiority: bool
    certified_catastrophic_noninferiority: bool
    certified_pareto_improvement: bool


@dataclass(frozen=True, slots=True)
class AnytimeMultiBaselineCertificate:
    paired_task_digest: str
    results: tuple[AnytimeBaselineResult, ...]
    familywise_alpha: float
    per_metric_alpha: float
    quality_noninferiority_margin: float
    catastrophic_noninferiority_margin: float
    all_baselines_certified: bool
    evidence_manifest_digest: str
    sequence_order_rule: str = SEQUENCE_ORDER_RULE
    method: str = METHOD
    claim_target: str = CLAIM_TARGET
    assumption_boundary: str = ASSUMPTION_BOUNDARY


def _validate_support(values: tuple[float, ...], lower: float, upper: float) -> None:
    if not (math.isfinite(lower) and math.isfinite(upper) and lower < upper):
        raise ValueError("finite ordered support required")
    if any((not math.isfinite(x)) or x < lower - 1e-12 or x > upper + 1e-12 for x in values):
        raise ValueError("observation outside declared support")


def average_conditional_mean_bound(
    observations: Sequence[float],
    *,
    lower: float,
    upper: float,
    alpha: float,
) -> AverageConditionalMeanBound:
    """Time-uniform nonparametric empirical-Bernstein CS terminal slice.

    The input sequence is rescaled to [0,1].  A predictable smoothed empirical
    center is used only for the variance process.  The returned interval targets
    the average conditional mean of the precommitted adapted sequence, not an iid
    population mean.  No independence or identical-distribution assumption is
    encoded by this primitive.
    """
    values = tuple(float(x) for x in observations)
    if not values:
        raise ValueError("at least one observation required")
    lower = float(lower)
    upper = float(upper)
    alpha = float(alpha)
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0,1)")
    _validate_support(values, lower, upper)

    span = upper - lower
    scaled = tuple((x - lower) / span for x in values)
    prefix_sum = 0.0
    variance_process = 0.0
    for index, value in enumerate(scaled, start=1):
        # Predictable because it depends only on observations before `index`.
        predictor = (0.5 + prefix_sum) / index
        variance_process += (value - predictor) ** 2
        prefix_sum += value

    v_hat = max(1.0, variance_process)
    log_eta = math.log(ETA)
    h = S * math.log(math.log(ETA * v_hat)) + math.log(
        (2.0 * ZETA_S) / (alpha * (log_eta ** S))
    )
    if not math.isfinite(h) or h <= 0.0:
        raise ValueError("invalid stitched empirical-Bernstein boundary state")
    k1 = (ETA ** 0.25 + ETA ** -0.25) / math.sqrt(2.0)
    k2 = (math.sqrt(ETA) + 1.0) / 2.0
    n = len(values)
    half_width_scaled = (k1 * math.sqrt(v_hat * h) + k2 * h) / n
    center_scaled = fmean(scaled)
    lower_scaled = max(0.0, center_scaled - half_width_scaled)
    upper_scaled = min(1.0, center_scaled + half_width_scaled)
    return AverageConditionalMeanBound(
        n=n,
        sample_mean=fmean(values),
        lower=lower + span * lower_scaled,
        upper=lower + span * upper_scaled,
        alpha=alpha,
        support_lower=lower,
        support_upper=upper,
        empirical_variance_process=v_hat,
        half_width=span * half_width_scaled,
    )


def certify_multi_baseline_anytime_valid(
    evidence: Sequence[PairedBaselineEvidence],
    *,
    alpha: float,
    quality_noninferiority_margin: float,
    catastrophic_noninferiority_margin: float,
) -> AnytimeMultiBaselineCertificate:
    rows = tuple(evidence)
    if not rows:
        raise ValueError("at least one baseline required")
    alpha = float(alpha)
    qmargin = float(quality_noninferiority_margin)
    cmargin = float(catastrophic_noninferiority_margin)
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0,1)")
    if any(not math.isfinite(value) or value < 0.0 for value in (qmargin, cmargin)):
        raise ValueError("noninferiority margins must be finite and >= 0")
    if len({row.baseline_id for row in rows}) != len(rows):
        raise ValueError("baseline ids must be unique")
    paired_digests = {row.paired_task_digest for row in rows}
    ns = {len(row.baseline_minus_dgc_cost) for row in rows}
    if len(paired_digests) != 1 or len(ns) != 1:
        raise ValueError("all baselines must use one identical paired observation sequence")
    if any(not math.isclose(float(row.coverage), 1.0, rel_tol=0.0, abs_tol=1e-12) for row in rows):
        raise ValueError("full paired coverage is required")

    per_metric_alpha = alpha / (len(rows) * 3)
    results: list[AnytimeBaselineResult] = []
    manifest: list[dict[str, object]] = []
    for row in sorted(rows, key=lambda item: item.baseline_id):
        n = len(row.baseline_minus_dgc_cost)
        if n <= 0 or len(row.dgc_minus_baseline_quality) != n or len(row.baseline_minus_dgc_catastrophic_regret) != n:
            raise ValueError("paired metric vectors must have equal nonzero length")
        cost = average_conditional_mean_bound(
            row.baseline_minus_dgc_cost,
            lower=row.cost_gain_support[0],
            upper=row.cost_gain_support[1],
            alpha=per_metric_alpha,
        )
        quality = average_conditional_mean_bound(
            row.dgc_minus_baseline_quality,
            lower=row.quality_gain_support[0],
            upper=row.quality_gain_support[1],
            alpha=per_metric_alpha,
        )
        catastrophic = average_conditional_mean_bound(
            row.baseline_minus_dgc_catastrophic_regret,
            lower=row.catastrophic_gain_support[0],
            upper=row.catastrophic_gain_support[1],
            alpha=per_metric_alpha,
        )
        cheaper = cost.lower > 0.0
        quality_ok = quality.lower >= -qmargin
        catastrophic_ok = catastrophic.lower >= -cmargin
        results.append(AnytimeBaselineResult(
            baseline_id=row.baseline_id,
            cost_gain=cost,
            quality_gain=quality,
            catastrophic_regret_gain=catastrophic,
            certified_cost_reduction=cheaper,
            certified_quality_noninferiority=quality_ok,
            certified_catastrophic_noninferiority=catastrophic_ok,
            certified_pareto_improvement=cheaper and quality_ok and catastrophic_ok,
        ))
        manifest.append({
            "baseline_id": row.baseline_id,
            "paired_task_digest": row.paired_task_digest,
            "n": n,
            "coverage": row.coverage,
            "cost_series_digest": _digest(row.baseline_minus_dgc_cost),
            "quality_series_digest": _digest(row.dgc_minus_baseline_quality),
            "catastrophic_series_digest": _digest(row.baseline_minus_dgc_catastrophic_regret),
            "cost_support": row.cost_gain_support,
            "quality_support": row.quality_gain_support,
            "catastrophic_support": row.catastrophic_gain_support,
            "sequence_order_rule": SEQUENCE_ORDER_RULE,
        })
    return AnytimeMultiBaselineCertificate(
        paired_task_digest=next(iter(paired_digests)),
        results=tuple(results),
        familywise_alpha=alpha,
        per_metric_alpha=per_metric_alpha,
        quality_noninferiority_margin=qmargin,
        catastrophic_noninferiority_margin=cmargin,
        all_baselines_certified=all(item.certified_pareto_improvement for item in results),
        evidence_manifest_digest=_digest(manifest),
    )
