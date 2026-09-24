from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import NormalDist
from typing import Iterable, Mapping

from cwc.governance.calibration_variance import (
    CalibrationObservation,
    estimate_all_balanced_variance_components,
)
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes
from cwc.governance.mechanism_evidence_plan import MechanismStatisticalPlan

SCHEMA = "DGC_MECHANISM_TRIAL_SIZING_RECEIPT_V1"


class MechanismTrialSizingError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class MechanismComparisonSizing:
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
    per_claim_alpha: float
    target_power: float


@dataclass(frozen=True, slots=True)
class MechanismTrialSizingReceipt:
    plan_digest: str
    confirmatory_task_count: int
    calibration_design_digest: str
    comparisons: tuple[MechanismComparisonSizing, ...]
    required_trials_per_task: int
    receipt_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "plan_digest": self.plan_digest,
            "confirmatory_task_count": self.confirmatory_task_count,
            "calibration_design_digest": self.calibration_design_digest,
            "comparisons": [asdict(row) for row in self.comparisons],
            "required_trials_per_task": self.required_trials_per_task,
            "receipt_digest": self.receipt_digest,
            "planning_only": True,
            "calibration_only": True,
            "confirmatory_outcomes_observed": False,
            "risk_qualification_authorized": False,
            "product_promotion_authorized": False,
        }


def _sizing(
    *,
    between_task_std: float,
    within_task_std: float,
    effect_of_interest: float,
    confirmatory_task_count: int,
    plan: MechanismStatisticalPlan,
) -> tuple[int, float, float, float]:
    between = float(between_task_std)
    within = float(within_task_std)
    effect = float(effect_of_interest)
    if not math.isfinite(between) or between < 0:
        raise MechanismTrialSizingError("between_task_std must be finite and >= 0")
    if not math.isfinite(within) or within < 0:
        raise MechanismTrialSizingError("within_task_std must be finite and >= 0")
    if not math.isfinite(effect) or effect <= 0:
        raise MechanismTrialSizingError("effect_of_interest must be finite and > 0")
    if int(confirmatory_task_count) <= 1:
        raise MechanismTrialSizingError("confirmatory_task_count must be > 1")

    z_alpha = NormalDist().inv_cdf(1.0 - plan.per_claim_alpha)
    z_power = NormalDist().inv_cdf(plan.target_power)
    target_se = effect / (z_alpha + z_power)
    n_tasks = int(confirmatory_task_count)
    between_var = between * between
    within_var = within * within
    asymptotic_se = math.sqrt(between_var / n_tasks)
    available_within_variance = n_tasks * target_se * target_se - between_var
    if available_within_variance <= 0:
        raise MechanismTrialSizingError(
            "UNDERPOWERED_TASK_HETEROGENEITY: no within-task repeat count can meet mechanism planning target"
        )
    raw_required = 1 if within_var == 0 else math.ceil(within_var / available_within_variance)
    required = max(int(plan.min_trials_per_task), int(raw_required))
    if required > int(plan.max_trials_per_task):
        raise MechanismTrialSizingError(
            f"UNDERPOWERED: required_trials_per_task={required} exceeds cap={plan.max_trials_per_task}"
        )
    achieved = math.sqrt(between_var / n_tasks + within_var / (n_tasks * required))
    return required, target_se, asymptotic_se, achieved


def freeze_mechanism_trial_sizing(
    *,
    observations: Iterable[CalibrationObservation],
    effects_of_interest: Mapping[str, float],
    confirmatory_task_count: int,
    plan: MechanismStatisticalPlan | None = None,
) -> MechanismTrialSizingReceipt:
    mechanism_plan = plan or MechanismStatisticalPlan()
    rows = tuple(observations)
    if not rows:
        raise MechanismTrialSizingError("non-empty calibration observations required")
    estimates = estimate_all_balanced_variance_components(rows)
    expected_comparisons = mechanism_plan.baseline_count * mechanism_plan.endpoint_count
    if len(estimates) != expected_comparisons:
        raise MechanismTrialSizingError(
            f"mechanism sizing requires exactly {expected_comparisons} baseline×endpoint comparisons"
        )
    comparison_ids = tuple(estimate.comparison_id for estimate in estimates)
    effects = {str(key).strip(): float(value) for key, value in effects_of_interest.items()}
    if set(effects) != set(comparison_ids):
        raise MechanismTrialSizingError(
            "effects_of_interest must match mechanism calibration comparison IDs exactly"
        )
    if int(confirmatory_task_count) <= 1:
        raise MechanismTrialSizingError("confirmatory_task_count must be > 1")

    keysets = {
        comparison: tuple(
            sorted(
                (row.task_id, row.replicate)
                for row in rows
                if row.comparison_id == comparison
            )
        )
        for comparison in comparison_ids
    }
    first = keysets[comparison_ids[0]]
    if any(keys != first for keys in keysets.values()):
        raise MechanismTrialSizingError(
            "all mechanism comparisons must share identical calibration task/replicate design"
        )
    calibration_design_digest = sha256_bytes(canonical_json_bytes(first))

    receipts: list[MechanismComparisonSizing] = []
    required = 0
    for estimate in estimates:
        effect = effects[estimate.comparison_id]
        needed, target_se, asymptotic_se, achieved = _sizing(
            between_task_std=estimate.between_task_std,
            within_task_std=estimate.within_task_std,
            effect_of_interest=effect,
            confirmatory_task_count=int(confirmatory_task_count),
            plan=mechanism_plan,
        )
        required = max(required, needed)
        receipts.append(
            MechanismComparisonSizing(
                comparison_id=estimate.comparison_id,
                calibration_population_digest=estimate.population_digest,
                task_count=estimate.task_count,
                calibration_replicates_per_task=estimate.replicates_per_task,
                between_task_std=estimate.between_task_std,
                within_task_std=estimate.within_task_std,
                effect_of_interest=effect,
                required_trials_per_task=needed,
                target_standard_error=target_se,
                asymptotic_between_task_standard_error=asymptotic_se,
                achieved_standard_error=achieved,
                per_claim_alpha=mechanism_plan.per_claim_alpha,
                target_power=mechanism_plan.target_power,
            )
        )
    ordered = tuple(sorted(receipts, key=lambda row: row.comparison_id))
    payload = {
        "plan_digest": mechanism_plan.digest,
        "confirmatory_task_count": int(confirmatory_task_count),
        "calibration_design_digest": calibration_design_digest,
        "comparisons": [asdict(row) for row in ordered],
        "required_trials_per_task": required,
    }
    return MechanismTrialSizingReceipt(
        **payload,
        receipt_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_mechanism_trial_sizing_document(
    path: Path,
    *,
    plan: MechanismStatisticalPlan | None = None,
) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise MechanismTrialSizingError("mechanism sizing receipt must be a regular file")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MechanismTrialSizingError("invalid mechanism sizing receipt JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise MechanismTrialSizingError("unexpected mechanism sizing receipt schema")
    if (
        doc.get("planning_only") is not True
        or doc.get("calibration_only") is not True
        or doc.get("confirmatory_outcomes_observed") is not False
        or doc.get("risk_qualification_authorized") is not False
        or doc.get("product_promotion_authorized") is not False
    ):
        raise MechanismTrialSizingError("mechanism sizing receipt authority boundary violated")

    mechanism_plan = plan or MechanismStatisticalPlan()
    if doc.get("plan_digest") != mechanism_plan.digest:
        raise MechanismTrialSizingError("mechanism sizing plan digest mismatch")
    try:
        confirmatory_count = int(doc.get("confirmatory_task_count"))
        required = int(doc.get("required_trials_per_task"))
    except (TypeError, ValueError) as exc:
        raise MechanismTrialSizingError("invalid mechanism sizing integer field") from exc
    if confirmatory_count <= 1 or not (
        mechanism_plan.min_trials_per_task
        <= required
        <= mechanism_plan.max_trials_per_task
    ):
        raise MechanismTrialSizingError("invalid mechanism sizing population/bounds")
    comparisons = doc.get("comparisons")
    expected_n = mechanism_plan.baseline_count * mechanism_plan.endpoint_count
    if not isinstance(comparisons, list) or len(comparisons) != expected_n:
        raise MechanismTrialSizingError("mechanism sizing comparison population mismatch")
    ids = [str(row.get("comparison_id", "")).strip() for row in comparisons if isinstance(row, Mapping)]
    if len(ids) != expected_n or ids != sorted(set(ids)):
        raise MechanismTrialSizingError("mechanism sizing comparison IDs must be sorted and unique")
    required_rows: list[int] = []
    for row in comparisons:
        if not isinstance(row, Mapping):
            raise MechanismTrialSizingError("invalid mechanism sizing comparison row")
        if not math.isclose(
            float(row.get("per_claim_alpha")),
            mechanism_plan.per_claim_alpha,
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            raise MechanismTrialSizingError("mechanism sizing alpha differs from frozen plan")
        if not math.isclose(
            float(row.get("target_power")),
            mechanism_plan.target_power,
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            raise MechanismTrialSizingError("mechanism sizing power differs from frozen plan")
        try:
            row_required = int(row.get("required_trials_per_task"))
        except (TypeError, ValueError) as exc:
            raise MechanismTrialSizingError("invalid comparison repeat count") from exc
        required_rows.append(row_required)
    if required != max(required_rows):
        raise MechanismTrialSizingError("global mechanism repeat count must equal comparison maximum")

    payload = {
        "plan_digest": doc["plan_digest"],
        "confirmatory_task_count": confirmatory_count,
        "calibration_design_digest": doc["calibration_design_digest"],
        "comparisons": comparisons,
        "required_trials_per_task": required,
    }
    if sha256_bytes(canonical_json_bytes(payload)) != str(doc.get("receipt_digest", "")).lower():
        raise MechanismTrialSizingError("mechanism sizing receipt digest mismatch")
    return doc
