from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from typing import Iterable, Mapping

from cwc.governance.calibration_variance import (
    CalibrationObservation,
    estimate_all_balanced_variance_components,
)
from cwc.governance.product_statistical_plan import (
    ProductStatisticalPlan,
    cluster_aware_required_trials_per_task,
)


def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class ComparisonSizingReceipt:
    comparison_id: str
    calibration_population_digest: str
    task_count: int
    calibration_replicates_per_task: int
    between_task_std: float
    within_task_std: float
    effect_of_interest: float
    required_trials_per_task: int
    target_standard_error: float
    asymptotic_between_task_standard_error: float
    achieved_standard_error: float


@dataclass(frozen=True, slots=True)
class TrialSizingReceipt:
    schema: str
    plan_digest: str
    confirmatory_task_count: int
    calibration_design_digest: str
    comparisons: tuple[ComparisonSizingReceipt, ...]
    required_trials_per_task: int
    planning_only: bool
    receipt_digest: str


def freeze_cluster_aware_trial_sizing(
    *,
    observations: Iterable[CalibrationObservation],
    effects_of_interest: Mapping[str, float],
    confirmatory_task_count: int,
    plan: ProductStatisticalPlan,
) -> TrialSizingReceipt:
    rows = tuple(observations)
    if not rows:
        raise ValueError("non-empty calibration observations required")
    estimates = estimate_all_balanced_variance_components(rows)
    comparison_ids = tuple(estimate.comparison_id for estimate in estimates)
    effects = {str(key).strip(): float(value) for key, value in effects_of_interest.items()}
    if set(effects) != set(comparison_ids):
        raise ValueError("effects_of_interest must match calibration comparison IDs exactly")
    if confirmatory_task_count <= 1:
        raise ValueError("confirmatory_task_count must be > 1")

    keysets = {
        comparison: tuple(
            sorted((row.task_id, row.replicate) for row in rows if row.comparison_id == comparison)
        )
        for comparison in comparison_ids
    }
    first = keysets[comparison_ids[0]]
    if any(keys != first for keys in keysets.values()):
        raise ValueError("all comparisons must share the identical calibration task/replicate design")
    calibration_design_digest = _digest(first)

    receipts = []
    required = 0
    for estimate in estimates:
        effect = effects[estimate.comparison_id]
        if not math.isfinite(effect) or effect <= 0:
            raise ValueError(f"invalid effect_of_interest for {estimate.comparison_id}")
        sizing = cluster_aware_required_trials_per_task(
            between_task_std=estimate.between_task_std,
            within_task_std=estimate.within_task_std,
            effect_of_interest=effect,
            confirmatory_task_count=confirmatory_task_count,
            plan=plan,
        )
        required = max(required, sizing.required_trials_per_task)
        receipts.append(
            ComparisonSizingReceipt(
                comparison_id=estimate.comparison_id,
                calibration_population_digest=estimate.population_digest,
                task_count=estimate.task_count,
                calibration_replicates_per_task=estimate.replicates_per_task,
                between_task_std=estimate.between_task_std,
                within_task_std=estimate.within_task_std,
                effect_of_interest=effect,
                required_trials_per_task=sizing.required_trials_per_task,
                target_standard_error=sizing.target_standard_error,
                asymptotic_between_task_standard_error=sizing.asymptotic_between_task_standard_error,
                achieved_standard_error=sizing.achieved_standard_error_at_required_trials,
            )
        )
    ordered = tuple(sorted(receipts, key=lambda row: row.comparison_id))
    payload = {
        "schema": "DGC_CLUSTER_AWARE_TRIAL_SIZING_RECEIPT_V1",
        "plan_digest": plan.digest,
        "confirmatory_task_count": int(confirmatory_task_count),
        "calibration_design_digest": calibration_design_digest,
        "comparisons": [asdict(row) for row in ordered],
        "required_trials_per_task": required,
        "planning_only": True,
    }
    return TrialSizingReceipt(
        schema=payload["schema"],
        plan_digest=plan.digest,
        confirmatory_task_count=int(confirmatory_task_count),
        calibration_design_digest=calibration_design_digest,
        comparisons=ordered,
        required_trials_per_task=required,
        planning_only=True,
        receipt_digest=_digest(payload),
    )
