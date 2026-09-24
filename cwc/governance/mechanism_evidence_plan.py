from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Sequence

from cwc.governance.pareto import MeanBound, fixed_n_hoeffding_mean_bound

METHOD = "DGC_REAL_WORKLOAD_MECHANISM_PARETO_V1"


@dataclass(frozen=True, slots=True)
class MechanismStatisticalPlan:
    family_count: int = 2
    baseline_count: int = 4
    endpoint_count: int = 2
    familywise_alpha: float = 0.05
    quality_noninferiority_margin: float = 0.02
    minimum_cost_effect_of_interest: float = 0.05
    risk_qualification_required_for_product: bool = True
    product_promotion_authorized: bool = False
    method: str = METHOD

    def __post_init__(self) -> None:
        if (self.family_count, self.baseline_count, self.endpoint_count) != (2, 4, 2):
            raise ValueError("mechanism lane is frozen to 2 families × 4 baselines × 2 endpoints")
        if not 0.0 < float(self.familywise_alpha) < 1.0:
            raise ValueError("familywise_alpha must be in (0,1)")
        if not 0.0 <= float(self.quality_noninferiority_margin) < 1.0:
            raise ValueError("quality_noninferiority_margin must be in [0,1)")
        if not 0.0 < float(self.minimum_cost_effect_of_interest) < 1.0:
            raise ValueError("minimum_cost_effect_of_interest must be in (0,1)")
        if self.risk_qualification_required_for_product is not True:
            raise ValueError("mechanism evidence cannot waive downstream risk qualification")
        if self.product_promotion_authorized is not False:
            raise ValueError("mechanism plan cannot authorize product promotion")
        if self.method != METHOD:
            raise ValueError("mechanism plan method identity mismatch")

    @property
    def per_family_alpha(self) -> float:
        return self.familywise_alpha / self.family_count

    @property
    def per_claim_alpha(self) -> float:
        return self.familywise_alpha / (
            self.family_count * self.baseline_count * self.endpoint_count
        )

    @property
    def digest(self) -> str:
        payload = {
            "family_count": self.family_count,
            "baseline_count": self.baseline_count,
            "endpoint_count": self.endpoint_count,
            "familywise_alpha": self.familywise_alpha,
            "quality_noninferiority_margin": self.quality_noninferiority_margin,
            "minimum_cost_effect_of_interest": self.minimum_cost_effect_of_interest,
            "risk_qualification_required_for_product": self.risk_qualification_required_for_product,
            "product_promotion_authorized": self.product_promotion_authorized,
            "method": self.method,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


@dataclass(frozen=True, slots=True)
class PairedMechanismEvidence:
    baseline_id: str
    paired_task_digest: str
    coverage: float
    baseline_minus_dgc_cost: tuple[float, ...]
    dgc_minus_baseline_quality: tuple[float, ...]
    cost_gain_support: tuple[float, float]
    quality_gain_support: tuple[float, float]

    def __post_init__(self) -> None:
        if not self.baseline_id.strip() or not self.paired_task_digest.strip():
            raise ValueError("baseline_id and paired_task_digest required")
        if not math.isclose(float(self.coverage), 1.0, rel_tol=0.0, abs_tol=1e-12):
            raise ValueError("full matched coverage is required")
        n = len(self.baseline_minus_dgc_cost)
        if n == 0 or len(self.dgc_minus_baseline_quality) != n:
            raise ValueError("two equal non-empty paired series required")


@dataclass(frozen=True, slots=True)
class MechanismBaselineResult:
    baseline_id: str
    cost_gain: MeanBound
    quality_gain: MeanBound
    certified_cost_reduction: bool
    certified_quality_noninferiority: bool
    certified_mechanism_pareto: bool


@dataclass(frozen=True, slots=True)
class MechanismParetoCertificate:
    paired_task_digest: str
    results: tuple[MechanismBaselineResult, ...]
    familywise_alpha: float
    per_metric_delta: float
    quality_noninferiority_margin: float
    all_baselines_certified: bool
    risk_qualification_required_for_product: bool = True
    product_promotion_authorized: bool = False
    method: str = METHOD


def certify_multi_baseline_mechanism_pareto(
    evidence: Sequence[PairedMechanismEvidence],
    *,
    alpha: float,
    quality_noninferiority_margin: float,
) -> MechanismParetoCertificate:
    rows = tuple(evidence)
    if len(rows) != 4:
        raise ValueError("mechanism lane requires exactly four preregistered baselines")
    alpha = float(alpha)
    margin = float(quality_noninferiority_margin)
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0,1)")
    if not math.isfinite(margin) or margin < 0.0:
        raise ValueError("quality_noninferiority_margin must be finite and >= 0")
    ids = [row.baseline_id for row in rows]
    if len(set(ids)) != 4:
        raise ValueError("baseline ids must be unique")
    digests = {row.paired_task_digest for row in rows}
    ns = {len(row.baseline_minus_dgc_cost) for row in rows}
    if len(digests) != 1 or len(ns) != 1:
        raise ValueError("all baselines must share the same paired task population")

    delta = alpha / (2.0 * len(rows))
    results: list[MechanismBaselineResult] = []
    for row in sorted(rows, key=lambda item: item.baseline_id):
        cost = fixed_n_hoeffding_mean_bound(
            row.baseline_minus_dgc_cost,
            lower=row.cost_gain_support[0],
            upper=row.cost_gain_support[1],
            delta=delta,
        )
        quality = fixed_n_hoeffding_mean_bound(
            row.dgc_minus_baseline_quality,
            lower=row.quality_gain_support[0],
            upper=row.quality_gain_support[1],
            delta=delta,
        )
        cheaper = cost.lower > 0.0
        noninferior = quality.lower >= -margin
        results.append(
            MechanismBaselineResult(
                baseline_id=row.baseline_id,
                cost_gain=cost,
                quality_gain=quality,
                certified_cost_reduction=cheaper,
                certified_quality_noninferiority=noninferior,
                certified_mechanism_pareto=cheaper and noninferior,
            )
        )
    return MechanismParetoCertificate(
        paired_task_digest=next(iter(digests)),
        results=tuple(results),
        familywise_alpha=alpha,
        per_metric_delta=delta,
        quality_noninferiority_margin=margin,
        all_baselines_certified=all(row.certified_mechanism_pareto for row in results),
    )
