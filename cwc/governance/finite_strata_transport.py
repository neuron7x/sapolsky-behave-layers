from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Hashable, Sequence


def _required(name: str, value: str) -> str:
    value = str(value).strip()
    if not value:
        raise ValueError(f"{name} required")
    return value


@dataclass(frozen=True, slots=True)
class FiniteStrataTransportLowerBound:
    source_n: int
    target_n: int
    strata_count: int
    source_counts: tuple[tuple[str, int], ...]
    target_counts: tuple[tuple[str, int], ...]
    stratum_lower_bounds: tuple[tuple[str, float], ...]
    target_proxy_mean: float
    target_sampling_radius: float
    target_mean_lower: float
    confidence: float
    stratum_schema_digest: str
    invariance_authority_digest: str
    certificate_digest: str
    method: str = "FINITE_STRATA_RATIO_FREE_COVARIATE_SHIFT_LCB_V1"


def target_mean_lcb_under_finite_strata_shift(
    source_values: Sequence[float],
    source_strata: Sequence[Hashable],
    target_strata: Sequence[Hashable],
    *,
    lower: float,
    upper: float,
    delta: float,
    conditional_mean_invariance_attested: bool,
    source_target_independence_attested: bool,
    stratum_schema_digest: str,
    invariance_authority_digest: str,
) -> FiniteStrataTransportLowerBound:
    """Lower confidence bound for a target mean under finite-strata covariate shift.

    Assumptions / authority boundary:
    - (Z_i, Y_i) are iid source draws; Y_i is bounded in [lower, upper].
    - target Z'_j are iid target draws independent of the source sample.
    - conditional-mean invariance is externally attested:
          E_P[Y | Z=z] = E_Q[Y | Z=z]
      for every target-observed stratum.
    - every target-observed stratum has at least one labeled source observation.

    Construction:
    1. Split total error probability delta equally between source conditional-mean
       estimation and target-mixture sampling.
    2. Build simultaneous one-sided Hoeffding LCBs for every target-observed
       source stratum (Bonferroni over strata).
    3. Treat those frozen LCBs as a bounded function g(Z) and use the independent
       target stratum sample to lower-bound E_Q[g(Z)] with one-sided Hoeffding.
    4. On the simultaneous source event, g(z) <= E_Q[Y|Z=z], so
       E_Q[g(Z)] <= E_Q[Y]. A union bound yields confidence >= 1-delta.

    This is ratio-free but restricted. It is not valid for unobserved target
    strata, conditional shift, dependent source/target samples, post-hoc strata,
    or continuous covariates without a declared finite partition.
    """
    if not source_values or not target_strata:
        raise ValueError("non-empty source values and target strata required")
    if len(source_values) != len(source_strata):
        raise ValueError("source_values and source_strata must have equal length")
    if not conditional_mean_invariance_attested:
        raise ValueError("conditional-mean invariance attestation required")
    if not source_target_independence_attested:
        raise ValueError("source/target independence attestation required")

    lower = float(lower)
    upper = float(upper)
    delta = float(delta)
    if not math.isfinite(lower) or not math.isfinite(upper) or upper <= lower:
        raise ValueError("finite lower < upper required")
    if not math.isfinite(delta) or not 0.0 < delta < 1.0:
        raise ValueError("delta must be in (0,1)")
    schema_digest = _required("stratum_schema_digest", stratum_schema_digest)
    invariance_digest = _required("invariance_authority_digest", invariance_authority_digest)

    xs = [float(x) for x in source_values]
    if any(not math.isfinite(x) or x < lower or x > upper for x in xs):
        raise ValueError("source value outside declared support")

    source_by_stratum: dict[str, list[float]] = {}
    for raw_z, x in zip(source_strata, xs, strict=True):
        z = str(raw_z)
        if not z:
            raise ValueError("empty source stratum")
        source_by_stratum.setdefault(z, []).append(x)

    target_labels = [str(z) for z in target_strata]
    if any(not z for z in target_labels):
        raise ValueError("empty target stratum")
    target_counts_map: dict[str, int] = {}
    for z in target_labels:
        target_counts_map[z] = target_counts_map.get(z, 0) + 1

    target_observed = tuple(sorted(target_counts_map))
    missing = [z for z in target_observed if z not in source_by_stratum]
    if missing:
        raise ValueError(f"positivity/support failure: target strata absent from source: {missing}")

    width = upper - lower
    delta_source = delta / 2.0
    delta_target = delta / 2.0
    m = len(target_observed)
    per_stratum_delta = delta_source / m

    lcbs: dict[str, float] = {}
    for z in target_observed:
        values = source_by_stratum[z]
        mean = math.fsum(values) / len(values)
        radius = width * math.sqrt(math.log(1.0 / per_stratum_delta) / (2.0 * len(values)))
        lcbs[z] = max(lower, mean - radius)

    proxy_values = [lcbs[z] for z in target_labels]
    proxy_mean = math.fsum(proxy_values) / len(proxy_values)
    target_radius = width * math.sqrt(math.log(1.0 / delta_target) / (2.0 * len(proxy_values)))
    target_lower = max(lower, proxy_mean - target_radius)

    source_counts = tuple(sorted((z, len(source_by_stratum[z])) for z in target_observed))
    target_counts = tuple(sorted(target_counts_map.items()))
    stratum_bounds = tuple(sorted(lcbs.items()))
    payload = {
        "version": "FINITE_STRATA_RATIO_FREE_COVARIATE_SHIFT_LCB_V1",
        "source_n": len(xs),
        "target_n": len(target_labels),
        "source_counts": source_counts,
        "target_counts": target_counts,
        "stratum_lower_bounds": stratum_bounds,
        "target_proxy_mean": proxy_mean,
        "target_sampling_radius": target_radius,
        "target_mean_lower": target_lower,
        "confidence": 1.0 - delta,
        "stratum_schema_digest": schema_digest,
        "invariance_authority_digest": invariance_digest,
    }
    cert_digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return FiniteStrataTransportLowerBound(
        source_n=len(xs),
        target_n=len(target_labels),
        strata_count=m,
        source_counts=source_counts,
        target_counts=target_counts,
        stratum_lower_bounds=stratum_bounds,
        target_proxy_mean=proxy_mean,
        target_sampling_radius=target_radius,
        target_mean_lower=target_lower,
        confidence=1.0 - delta,
        stratum_schema_digest=schema_digest,
        invariance_authority_digest=invariance_digest,
        certificate_digest=cert_digest,
    )
