from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from statistics import fmean
from typing import Sequence

from cwc.governance.pareto import PairedBaselineEvidence

# Exact author-reference runtime identity for Howard et al. polynomial stitching.
# The parameter digest binds every numeric constant that affects the boundary.
ETA = 2.0
S = 1.4
V_MIN = 1.0
BOUNDARY_C = 1.0
# boost::math::zeta(1.4) at the pinned confseq reference path, frozen by binary64 hex.
ZETA_S_HEX = "0x1.8d8292bd8c3a6p+1"
ZETA_S = float.fromhex(ZETA_S_HEX)
BOUNDARY_PARAMETER_DIGEST = "4deabb17370edfc770b7612235ee9dfddf932dfc21e894161fb2757ea45a1329"

METHOD = "HOWARD_RAMDAS_MCAULIFFE_SEKHON_THEOREM4_POLY_STITCHING_EXACT_V3"
BOUNDARY_METHOD = f"HOWARD_EQ10_POLYNOMIAL_STITCHING_EXACT_V2_{BOUNDARY_PARAMETER_DIGEST[:16]}"
CLAIM_TARGET = "AVERAGE_CONDITIONAL_MEAN_OF_PRECOMMITTED_BOUNDED_SEQUENCE"
ASSUMPTION_BOUNDARY = "BOUNDED_ADAPTED_PROCESS_PREDICTABLE_CENTER_NO_IID_REQUIRED"
SEQUENCE_ORDER_RULE = "TASK_ID_ASC_THEN_REPLICATE_ASC"
PREDICTOR_RULE = "BETA_HALF_SMOOTHED_PREVISIBLE_MEAN_V1"
CONFSEQ_REFERENCE_COMMIT = "5ffe733ca2447a2e28c2c91f3b00086173f2ab2c"


def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def boundary_parameter_payload() -> dict[str, object]:
    """Canonical numeric identity for the frozen polynomial-stitching runtime."""
    payload = {
        "eta": ETA,
        "s": S,
        "v_min": V_MIN,
        "c": BOUNDARY_C,
        "zeta_s_binary64_hex": ZETA_S_HEX,
    }
    if _digest(payload) != BOUNDARY_PARAMETER_DIGEST:
        raise RuntimeError("boundary parameter identity drift")
    return payload


def polynomial_stitching_boundary(
    variance_process: float,
    *,
    crossing_alpha: float,
    v_min: float = V_MIN,
    c: float = BOUNDARY_C,
) -> float:
    """Exact Howard et al. Eq. (10) polynomial-stitching boundary.

    This mirrors the authors' ``PolyStitchingBound`` implementation at
    ``CONFSEQ_REFERENCE_COMMIT``. ``crossing_alpha`` is the *one-boundary*
    crossing probability. Theorem 4 is two-sided, so callers targeting total
    interval error ``delta`` must pass ``crossing_alpha=delta/2``.

    The default protocol parameters are content-identified by
    ``BOUNDARY_PARAMETER_DIGEST``. Any parameter change must therefore change
    the boundary method identity before outcome-bearing execution.
    """
    v = float(variance_process)
    crossing = float(crossing_alpha)
    v_floor = float(v_min)
    scale = float(c)
    if not math.isfinite(v) or v < 0.0:
        raise ValueError("variance_process must be finite and >= 0")
    if not 0.0 < crossing < 1.0:
        raise ValueError("crossing_alpha must be in (0,1)")
    if not math.isfinite(v_floor) or v_floor <= 0.0:
        raise ValueError("v_min must be finite and > 0")
    if not math.isfinite(scale):
        raise ValueError("c must be finite")

    use_v = max(v, v_floor)
    log_eta = math.log(ETA)
    ell = S * math.log(math.log(ETA * use_v / v_floor)) + math.log(
        ZETA_S / (crossing * (log_eta ** S))
    )
    if not math.isfinite(ell) or ell <= 0.0:
        raise ValueError("invalid polynomial-stitching boundary state")
    k1 = (ETA ** 0.25 + ETA ** -0.25) / math.sqrt(2.0)
    k2 = (math.sqrt(ETA) + 1.0) / 2.0
    term2 = k2 * scale * ell
    return math.sqrt(k1 * k1 * use_v * ell + term2 * term2) + term2


@dataclass(frozen=True, slots=True)
class AverageConditionalMeanBound:
    n: int
    sample_mean: float
    lower: float
    upper: float
    alpha: float
    boundary_crossing_alpha: float
    support_lower: float
    support_upper: float
    empirical_variance_process: float
    half_width: float
    method: str = METHOD
    boundary_method: str = BOUNDARY_METHOD
    claim_target: str = CLAIM_TARGET
    assumption_boundary: str = ASSUMPTION_BOUNDARY
    predictor_rule: str = PREDICTOR_RULE


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
    boundary_method: str = BOUNDARY_METHOD
    claim_target: str = CLAIM_TARGET
    assumption_boundary: str = ASSUMPTION_BOUNDARY
    predictor_rule: str = PREDICTOR_RULE
    confseq_reference_commit: str = CONFSEQ_REFERENCE_COMMIT


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
    """Terminal slice of a time-uniform confidence sequence for an ACM.

    Observations are rescaled to [0,1]. The predictor is previsible: at time t it
    depends only on observations strictly before t. Theorem 4 then targets the
    average conditional mean of the bounded adapted sequence; it does not require
    a common iid population mean or independence across provider requests.

    ``alpha`` is the desired two-sided interval error. The underlying one-boundary
    crossing probability is therefore ``alpha/2`` exactly as required by the
    Theorem-4 ``1-2*crossing_alpha`` coverage statement.
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
        # (1/2 + sum_{j<t} X_j) / t is F_{t-1}-measurable and lies in [0,1].
        predictor = (0.5 + prefix_sum) / index
        variance_process += (value - predictor) ** 2
        prefix_sum += value

    crossing_alpha = alpha / 2.0
    radius_scaled = polynomial_stitching_boundary(
        variance_process,
        crossing_alpha=crossing_alpha,
        v_min=V_MIN,
        c=BOUNDARY_C,
    ) / len(values)
    center_scaled = fmean(scaled)
    lower_scaled = max(0.0, center_scaled - radius_scaled)
    upper_scaled = min(1.0, center_scaled + radius_scaled)
    return AverageConditionalMeanBound(
        n=len(values),
        sample_mean=fmean(values),
        lower=lower + span * lower_scaled,
        upper=lower + span * upper_scaled,
        alpha=alpha,
        boundary_crossing_alpha=crossing_alpha,
        support_lower=lower,
        support_upper=upper,
        empirical_variance_process=variance_process,
        half_width=span * radius_scaled,
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

    # Bonferroni over four baseline arms x three endpoints within this workload family.
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
            "predictor_rule": PREDICTOR_RULE,
            "boundary_parameter_digest": BOUNDARY_PARAMETER_DIGEST,
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
