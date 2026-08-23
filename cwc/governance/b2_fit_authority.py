from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from cwc.governance.b2_fit_receipt import fit_b2_with_receipt
from cwc.governance.execution_manifest_freeze import verify_execution_manifest_freeze_document
from cwc.governance.learned_baseline import CalibrationExample, LearnedRouterConfig
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.task_partition import verify_task_partition_document

SCHEMA = "DGC_B2_FIT_AUTHORITY_V1"
FIT_INPUT_SCHEMA = "DGC_B2_FIT_INPUT_V1"
FIT_RECEIPT_SCHEMA = "DGC_B2_FIT_RECEIPT_V1"


class B2FitAuthorityError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise B2FitAuthorityError(f"{name} must be lowercase SHA-256")
    return text


def _json(path: Path, *, schema: str) -> dict[str, object]:
    candidate = Path(path)
    if not candidate.is_file() or candidate.is_symlink():
        raise B2FitAuthorityError(f"missing regular JSON file: {candidate}")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise B2FitAuthorityError(f"invalid JSON file: {candidate}") from exc
    if not isinstance(doc, dict) or doc.get("schema") != schema:
        raise B2FitAuthorityError(f"unexpected schema for {candidate}")
    return doc


@dataclass(frozen=True, slots=True)
class B2FitAuthority:
    family_id: str
    execution_manifest_freeze_digest: str
    task_partition_receipt_digest: str
    fit_input_sha256: str
    fit_receipt_sha256: str
    feature_schema_digest: str
    training_algorithm_digest: str
    calibration_task_digest: str
    confirmatory_task_digest: str
    fitted_model_digest: str
    calibration_task_count: int
    authority_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            **asdict(self),
            "confirmatory_execution_authorized": False,
            "product_promotion_authorized": False,
        }


def authorize_b2_fit(
    *,
    execution_manifest_freeze_path: Path,
    task_partition_path: Path,
    fit_input_path: Path,
    fit_receipt_path: Path,
) -> B2FitAuthority:
    execution = verify_execution_manifest_freeze_document(Path(execution_manifest_freeze_path))
    partition = verify_task_partition_document(Path(task_partition_path))
    fit_input = _json(Path(fit_input_path), schema=FIT_INPUT_SCHEMA)
    declared_receipt = _json(Path(fit_receipt_path), schema=FIT_RECEIPT_SCHEMA)

    if partition.get("family_id") != execution.get("family_id"):
        raise B2FitAuthorityError("B2 partition family differs from frozen execution family")
    if partition.get("materialization_reference_digest") != execution.get("materialization_reference_digest"):
        raise B2FitAuthorityError("B2 partition materialization subject differs from execution freeze")
    if partition.get("task_manifest_digest") != execution.get("task_manifest_digest"):
        raise B2FitAuthorityError("B2 partition task population differs from execution freeze")
    if partition.get("statistical_plan_digest") != execution.get("statistical_plan_digest"):
        raise B2FitAuthorityError("B2 partition statistical plan differs from execution freeze")

    try:
        config = LearnedRouterConfig(**fit_input["config"])
        examples = [
            CalibrationExample(
                task_id=row["task_id"],
                action_id=row["action_id"],
                features=tuple(row["features"]),
                quality=float(row["quality"]),
                cost_usd=float(row["cost_usd"]),
                catastrophic_regret=float(row["catastrophic_regret"]),
            )
            for row in fit_input["examples"]
        ]
        forbidden = tuple(sorted(str(x).strip() for x in fit_input["forbidden_task_ids"] if str(x).strip()))
    except (KeyError, TypeError, ValueError) as exc:
        raise B2FitAuthorityError("malformed B2 fit input") from exc

    calibration = tuple(sorted(str(x) for x in partition["calibration_task_ids"]))
    confirmatory = tuple(sorted(str(x) for x in partition["confirmatory_task_ids"]))
    observed_tasks = tuple(sorted({example.task_id for example in examples}))
    if observed_tasks != calibration:
        raise B2FitAuthorityError("B2 examples must cover the exact frozen calibration task population")
    if forbidden != confirmatory:
        raise B2FitAuthorityError("B2 forbidden_task_ids must equal the exact frozen confirmatory population")
    if _sha("expected_feature_schema_digest", fit_input.get("expected_feature_schema_digest")) != config.feature_schema_digest:
        raise B2FitAuthorityError("B2 input feature schema digest does not match config")
    if _sha("expected_training_algorithm_digest", fit_input.get("expected_training_algorithm_digest")) != config.training_algorithm_digest:
        raise B2FitAuthorityError("B2 input training algorithm digest does not match config")

    try:
        recomputed = fit_b2_with_receipt(
            config=config,
            examples=examples,
            forbidden_task_ids=forbidden,
            expected_feature_schema_digest=config.feature_schema_digest,
            expected_training_algorithm_digest=config.training_algorithm_digest,
        )
    except (TypeError, ValueError, RuntimeError) as exc:
        raise B2FitAuthorityError("B2 fit cannot be deterministically recomputed") from exc
    if asdict(recomputed) != declared_receipt:
        raise B2FitAuthorityError("declared B2 fit receipt does not equal deterministic recomputation")
    if recomputed.calibration_task_digest != partition.get("calibration_task_digest"):
        raise B2FitAuthorityError("B2 fitted calibration task digest differs from frozen partition")
    if recomputed.calibration_task_count != len(calibration):
        raise B2FitAuthorityError("B2 fitted calibration task count differs from frozen partition")

    payload = {
        "family_id": execution["family_id"],
        "execution_manifest_freeze_digest": _sha("execution freeze_digest", execution.get("freeze_digest")),
        "task_partition_receipt_digest": _sha("task partition receipt_digest", partition.get("receipt_digest")),
        "fit_input_sha256": sha256_file(Path(fit_input_path)),
        "fit_receipt_sha256": sha256_file(Path(fit_receipt_path)),
        "feature_schema_digest": recomputed.feature_schema_digest,
        "training_algorithm_digest": recomputed.training_algorithm_digest,
        "calibration_task_digest": recomputed.calibration_task_digest,
        "confirmatory_task_digest": _sha("confirmatory_task_digest", partition.get("confirmatory_task_digest")),
        "fitted_model_digest": recomputed.fitted_model_digest,
        "calibration_task_count": recomputed.calibration_task_count,
    }
    return B2FitAuthority(
        **payload,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_b2_fit_authority_document(path: Path) -> dict[str, object]:
    doc = _json(Path(path), schema=SCHEMA)
    if doc.get("confirmatory_execution_authorized") is not False or doc.get("product_promotion_authorized") is not False:
        raise B2FitAuthorityError("B2 fit authority illegally grants downstream authority")
    payload = {
        key: doc[key]
        for key in (
            "family_id", "execution_manifest_freeze_digest", "task_partition_receipt_digest",
            "fit_input_sha256", "fit_receipt_sha256", "feature_schema_digest",
            "training_algorithm_digest", "calibration_task_digest", "confirmatory_task_digest",
            "fitted_model_digest", "calibration_task_count",
        )
    }
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("authority_digest", doc.get("authority_digest")):
        raise B2FitAuthorityError("B2 fit authority digest mismatch")
    if int(doc.get("calibration_task_count", 0)) <= 0:
        raise B2FitAuthorityError("B2 calibration_task_count must be > 0")
    return doc
