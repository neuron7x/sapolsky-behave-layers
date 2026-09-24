from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from cwc.governance.b2_fit_authority import verify_b2_fit_authority_document
from cwc.governance.calibration_variance import CalibrationObservation
from cwc.governance.execution_manifest_freeze import verify_execution_manifest_freeze_document
from cwc.governance.harness_freeze import verify_harness_freeze_document
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.product_statistical_plan import ProductStatisticalPlan
from cwc.governance.task_partition import verify_task_partition_document
from cwc.governance.trial_sizing_receipt import freeze_cluster_aware_trial_sizing

SCHEMA = "DGC_TRIAL_SIZING_AUTHORITY_V1"
INPUT_SCHEMA = "DGC_CLUSTER_AWARE_TRIAL_SIZING_INPUT_V1"
RECEIPT_SCHEMA = "DGC_CLUSTER_AWARE_TRIAL_SIZING_RECEIPT_V1"


class TrialSizingAuthorityError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise TrialSizingAuthorityError(f"{name} must be lowercase SHA-256")
    return text


def _json(path: Path, *, schema: str) -> dict[str, object]:
    candidate = Path(path)
    if not candidate.is_file() or candidate.is_symlink():
        raise TrialSizingAuthorityError(f"missing regular JSON file: {candidate}")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TrialSizingAuthorityError(f"invalid JSON file: {candidate}") from exc
    if not isinstance(doc, dict) or doc.get("schema") != schema:
        raise TrialSizingAuthorityError(f"unexpected schema for {candidate}")
    return doc


@dataclass(frozen=True, slots=True)
class TrialSizingAuthority:
    family_id: str
    execution_manifest_freeze_digest: str
    b2_fit_authority_digest: str
    harness_freeze_digest: str
    task_partition_receipt_digest: str
    sizing_input_sha256: str
    sizing_receipt_sha256: str
    plan_digest: str
    calibration_design_digest: str
    confirmatory_task_count: int
    required_trials_per_task: int
    comparison_count: int
    authority_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            **asdict(self),
            "planning_only": True,
            "confirmatory_execution_authorized": False,
            "product_promotion_authorized": False,
        }


def authorize_trial_sizing(
    *,
    execution_manifest_freeze_path: Path,
    b2_fit_authority_path: Path,
    harness_freeze_path: Path,
    task_partition_path: Path,
    sizing_input_path: Path,
    sizing_receipt_path: Path,
) -> TrialSizingAuthority:
    execution = verify_execution_manifest_freeze_document(Path(execution_manifest_freeze_path))
    b2 = verify_b2_fit_authority_document(Path(b2_fit_authority_path))
    harness = verify_harness_freeze_document(Path(harness_freeze_path))
    partition = verify_task_partition_document(Path(task_partition_path))
    sizing_input = _json(Path(sizing_input_path), schema=INPUT_SCHEMA)
    declared_receipt = _json(Path(sizing_receipt_path), schema=RECEIPT_SCHEMA)

    execution_digest = _sha("execution freeze_digest", execution.get("freeze_digest"))
    b2_digest = _sha("B2 authority_digest", b2.get("authority_digest"))
    harness_digest = _sha("harness_freeze_digest", harness.get("harness_freeze_digest"))
    partition_digest = _sha("task partition receipt_digest", partition.get("receipt_digest"))
    family = str(execution.get("family_id", ""))

    if b2.get("execution_manifest_freeze_digest") != execution_digest:
        raise TrialSizingAuthorityError("B2 authority lineage differs from execution freeze")
    if harness.get("execution_manifest_freeze_digest") != execution_digest:
        raise TrialSizingAuthorityError("harness lineage differs from execution freeze")
    if harness.get("b2_fit_authority_digest") != b2_digest:
        raise TrialSizingAuthorityError("harness lineage differs from B2 authority")
    if b2.get("task_partition_receipt_digest") != partition_digest:
        raise TrialSizingAuthorityError("B2 authority lineage differs from task partition")
    if any(str(doc.get("family_id", "")) != family for doc in (b2, harness, partition)):
        raise TrialSizingAuthorityError("trial-sizing family lineage mismatch")

    try:
        plan = ProductStatisticalPlan(**dict(sizing_input.get("plan", {})))
    except (TypeError, ValueError) as exc:
        raise TrialSizingAuthorityError("invalid trial-sizing statistical plan") from exc
    if plan.digest != execution.get("statistical_plan_digest"):
        raise TrialSizingAuthorityError("trial-sizing plan differs from execution freeze")
    if partition.get("statistical_plan_digest") != plan.digest:
        raise TrialSizingAuthorityError("task partition plan differs from sizing plan")

    try:
        observations = tuple(
            CalibrationObservation(
                comparison_id=row["comparison_id"],
                task_id=row["task_id"],
                replicate=int(row["replicate"]),
                value=float(row["value"]),
            )
            for row in sizing_input["observations"]
        )
        effects = {str(key): float(value) for key, value in sizing_input["effects_of_interest"].items()}
        confirmatory_task_count = int(sizing_input["confirmatory_task_count"])
    except (KeyError, TypeError, ValueError) as exc:
        raise TrialSizingAuthorityError("malformed trial-sizing input") from exc

    calibration = tuple(sorted(str(x) for x in partition["calibration_task_ids"]))
    confirmatory = tuple(sorted(str(x) for x in partition["confirmatory_task_ids"]))
    if confirmatory_task_count != len(confirmatory):
        raise TrialSizingAuthorityError("confirmatory_task_count must equal frozen confirmatory partition size")
    comparison_ids = tuple(sorted({row.comparison_id for row in observations}))
    if not comparison_ids:
        raise TrialSizingAuthorityError("trial-sizing observations are empty")
    for comparison_id in comparison_ids:
        tasks = tuple(sorted({row.task_id for row in observations if row.comparison_id == comparison_id}))
        if tasks != calibration:
            raise TrialSizingAuthorityError(
                f"{comparison_id}: observations must cover the exact frozen calibration task population"
            )
        if set(tasks) & set(confirmatory):
            raise TrialSizingAuthorityError("confirmatory task leaked into variance calibration")

    try:
        recomputed = freeze_cluster_aware_trial_sizing(
            observations=observations,
            effects_of_interest=effects,
            confirmatory_task_count=confirmatory_task_count,
            plan=plan,
        )
    except (TypeError, ValueError, RuntimeError) as exc:
        raise TrialSizingAuthorityError("cluster-aware trial sizing failed") from exc
    if asdict(recomputed) != declared_receipt:
        raise TrialSizingAuthorityError("declared trial-sizing receipt does not equal deterministic recomputation")
    if recomputed.plan_digest != plan.digest:
        raise TrialSizingAuthorityError("trial-sizing receipt plan digest mismatch")

    payload = {
        "family_id": family,
        "execution_manifest_freeze_digest": execution_digest,
        "b2_fit_authority_digest": b2_digest,
        "harness_freeze_digest": harness_digest,
        "task_partition_receipt_digest": partition_digest,
        "sizing_input_sha256": sha256_file(Path(sizing_input_path)),
        "sizing_receipt_sha256": sha256_file(Path(sizing_receipt_path)),
        "plan_digest": recomputed.plan_digest,
        "calibration_design_digest": recomputed.calibration_design_digest,
        "confirmatory_task_count": recomputed.confirmatory_task_count,
        "required_trials_per_task": recomputed.required_trials_per_task,
        "comparison_count": len(recomputed.comparisons),
    }
    return TrialSizingAuthority(
        **payload,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_trial_sizing_authority_document(path: Path) -> dict[str, object]:
    doc = _json(Path(path), schema=SCHEMA)
    if doc.get("planning_only") is not True:
        raise TrialSizingAuthorityError("trial-sizing authority must remain planning_only")
    if doc.get("confirmatory_execution_authorized") is not False or doc.get("product_promotion_authorized") is not False:
        raise TrialSizingAuthorityError("trial-sizing authority illegally grants downstream authority")
    payload = {
        key: doc[key]
        for key in (
            "family_id", "execution_manifest_freeze_digest", "b2_fit_authority_digest",
            "harness_freeze_digest", "task_partition_receipt_digest", "sizing_input_sha256",
            "sizing_receipt_sha256", "plan_digest", "calibration_design_digest",
            "confirmatory_task_count", "required_trials_per_task", "comparison_count",
        )
    }
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("authority_digest", doc.get("authority_digest")):
        raise TrialSizingAuthorityError("trial-sizing authority digest mismatch")
    if int(doc.get("confirmatory_task_count", 0)) <= 1:
        raise TrialSizingAuthorityError("confirmatory_task_count must be > 1")
    if int(doc.get("required_trials_per_task", 0)) <= 0:
        raise TrialSizingAuthorityError("required_trials_per_task must be > 0")
    if int(doc.get("comparison_count", 0)) <= 0:
        raise TrialSizingAuthorityError("comparison_count must be > 0")
    return doc
