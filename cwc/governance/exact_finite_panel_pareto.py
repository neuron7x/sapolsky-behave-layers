from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from statistics import fmean
from typing import Sequence

from cwc.governance.pareto import PairedBaselineEvidence

METHOD = "EXACT_FROZEN_FINITE_PANEL_PARETO_V1"


def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class ExactFinitePanelBaselineResult:
    baseline_id: str
    n: int
    mean_cost_gain: float
    mean_quality_gain: float
    mean_catastrophic_regret_gain: float
    cost_reduction_observed: bool
    quality_noninferiority_observed: bool
    catastrophic_noninferiority_observed: bool
    exact_panel_pareto_observed: bool


@dataclass(frozen=True, slots=True)
class ExactFinitePanelCertificate:
    paired_panel_digest: str
    results: tuple[ExactFinitePanelBaselineResult, ...]
    quality_noninferiority_margin: float
    catastrophic_noninferiority_margin: float
    all_baselines_observed: bool
    evidence_manifest_digest: str
    method: str = METHOD


def certify_exact_finite_panel(
    evidence: Sequence[PairedBaselineEvidence],
    *,
    quality_noninferiority_margin: float,
    catastrophic_noninferiority_margin: float,
) -> ExactFinitePanelCertificate:
    """Exact arithmetic certificate for one fully observed frozen panel.

    This certificate makes no stochastic/generalization claim. It answers only whether
    the realized, preregistered paired population itself satisfies the declared cost,
    quality and catastrophic-regret inequalities.
    """
    rows = tuple(evidence)
    if not rows:
        raise ValueError("at least one baseline required")
    qmargin = float(quality_noninferiority_margin)
    cmargin = float(catastrophic_noninferiority_margin)
    if any(not math.isfinite(value) or value < 0.0 for value in (qmargin, cmargin)):
        raise ValueError("non-inferiority margins must be finite and >= 0")
    ids = [row.baseline_id for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("baseline ids must be unique")
    digests = {row.paired_task_digest for row in rows}
    ns = {len(row.baseline_minus_dgc_cost) for row in rows}
    if len(digests) != 1 or len(ns) != 1:
        raise ValueError("all baselines must use the same paired finite-panel population")
    if any(not math.isclose(float(row.coverage), 1.0, rel_tol=0.0, abs_tol=1e-12) for row in rows):
        raise ValueError("full paired coverage is required")

    results: list[ExactFinitePanelBaselineResult] = []
    manifest: list[dict[str, object]] = []
    for row in sorted(rows, key=lambda item: item.baseline_id):
        n = len(row.baseline_minus_dgc_cost)
        if n == 0 or len(row.dgc_minus_baseline_quality) != n or len(row.baseline_minus_dgc_catastrophic_regret) != n:
            raise ValueError("three equal non-empty paired series required")
        cost = tuple(float(x) for x in row.baseline_minus_dgc_cost)
        quality = tuple(float(x) for x in row.dgc_minus_baseline_quality)
        catastrophic = tuple(float(x) for x in row.baseline_minus_dgc_catastrophic_regret)
        supports = (
            (cost, row.cost_gain_support),
            (quality, row.quality_gain_support),
            (catastrophic, row.catastrophic_gain_support),
        )
        for values, support in supports:
            lo, hi = map(float, support)
            if not (math.isfinite(lo) and math.isfinite(hi) and lo <= hi):
                raise ValueError("finite ordered support required")
            if any(not math.isfinite(x) or x < lo - 1e-12 or x > hi + 1e-12 for x in values):
                raise ValueError("observation outside declared support")
        mean_cost = fmean(cost)
        mean_quality = fmean(quality)
        mean_catastrophic = fmean(catastrophic)
        cost_ok = mean_cost > 0.0
        quality_ok = mean_quality >= -qmargin
        catastrophic_ok = mean_catastrophic >= -cmargin
        results.append(ExactFinitePanelBaselineResult(
            baseline_id=row.baseline_id,
            n=n,
            mean_cost_gain=mean_cost,
            mean_quality_gain=mean_quality,
            mean_catastrophic_regret_gain=mean_catastrophic,
            cost_reduction_observed=cost_ok,
            quality_noninferiority_observed=quality_ok,
            catastrophic_noninferiority_observed=catastrophic_ok,
            exact_panel_pareto_observed=cost_ok and quality_ok and catastrophic_ok,
        ))
        manifest.append({
            "baseline_id": row.baseline_id,
            "n": n,
            "cost_series_digest": _digest(cost),
            "quality_series_digest": _digest(quality),
            "catastrophic_series_digest": _digest(catastrophic),
            "cost_support": row.cost_gain_support,
            "quality_support": row.quality_gain_support,
            "catastrophic_support": row.catastrophic_gain_support,
        })

    return ExactFinitePanelCertificate(
        paired_panel_digest=next(iter(digests)),
        results=tuple(results),
        quality_noninferiority_margin=qmargin,
        catastrophic_noninferiority_margin=cmargin,
        all_baselines_observed=all(row.exact_panel_pareto_observed for row in results),
        evidence_manifest_digest=_digest(manifest),
    )


def certificate_digest(certificate: ExactFinitePanelCertificate) -> str:
    return _digest(asdict(certificate))
