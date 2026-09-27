from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.mechanism_b2_fit_receipt import SCHEMA as RECEIPT_SCHEMA, fit_mechanism_b2_with_receipt
from cwc.governance.mechanism_execution_freeze import verify_mechanism_execution_freeze_document
from cwc.governance.mechanism_learned_baseline import MechanismCalibrationExample, MechanismLearnedRouterConfig
from cwc.governance.task_partition import verify_task_partition_document

SCHEMA = "DGC_MECHANISM_B2_FIT_AUTHORITY_V1"
FIT_INPUT_SCHEMA = "DGC_MECHANISM_B2_FIT_INPUT_V1"


class MechanismB2FitAuthorityError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise MechanismB2FitAuthorityError(f"{name} must be lowercase SHA-256")
    return text


def _json(path: Path, schema: str) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise MechanismB2FitAuthorityError(f"missing regular JSON: {candidate}")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise MechanismB2FitAuthorityError(f"invalid JSON: {candidate}") from exc
    if not isinstance(doc, dict) or doc.get("schema") != schema:
        raise MechanismB2FitAuthorityError(f"unexpected schema for {candidate}")
    return doc


@dataclass(frozen=True, slots=True)
class MechanismB2FitAuthority:
    family_id: str
    execution_manifest_freeze_digest: str
    task_partition_receipt_digest: str
    fit_input_sha256: str
    fit_receipt_sha256: str
    feature_schema_digest: str
    training_algorithm_digest: str
    calibration_task_digest: str
    confirmatory_task_digest: str
    generalization_task_digest: str
    fitted_model_digest: str
    calibration_task_count: int
    authority_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            **asdict(self),
            "risk_fields_consumed": False,
            "mechanism_execution_authorized": False,
            "risk_qualification_authorized": False,
            "product_promotion_authorized": False,
        }


def authorize_mechanism_b2_fit(
    *,
    execution_manifest_freeze_path: Path,
    task_partition_path: Path,
    fit_input_path: Path,
    fit_receipt_path: Path,
) -> MechanismB2FitAuthority:
    execution = verify_mechanism_execution_freeze_document(Path(execution_manifest_freeze_path))
    partition = verify_task_partition_document(Path(task_partition_path))
    fit_input = _json(Path(fit_input_path), FIT_INPUT_SCHEMA)
    declared = _json(Path(fit_receipt_path), RECEIPT_SCHEMA)
    if partition.get("family_id") != execution.get("family_id"):
        raise MechanismB2FitAuthorityError("mechanism B2 partition family mismatch")
    if partition.get("materialization_reference_digest") != execution.get("materialization_reference_digest"):
        raise MechanismB2FitAuthorityError("mechanism B2 materialization subject mismatch")
    if partition.get("task_manifest_digest") != execution.get("task_manifest_digest"):
        raise MechanismB2FitAuthorityError("mechanism B2 task population mismatch")
    if partition.get("statistical_plan_digest") != execution.get("statistical_plan_digest"):
        raise MechanismB2FitAuthorityError("mechanism B2 partition plan lineage mismatch")
    forbidden_keys = {"catastrophic_regret", "risk", "risk_score", "risk_endpoint"}
    if forbidden_keys.intersection(fit_input):
        raise MechanismB2FitAuthorityError("mechanism B2 fit input contains forbidden risk field")
    try:
        config = MechanismLearnedRouterConfig(**fit_input["config"])
        examples = [
            MechanismCalibrationExample(
                task_id=str(row["task_id"]),
                action_id=str(row["action_id"]),
                features=tuple(row["features"]),
                quality=float(row["quality"]),
                cost_usd=float(row["cost_usd"]),
            )
            for row in fit_input["examples"]
        ]
        if any(forbidden_keys.intersection(row) for row in fit_input["examples"] if isinstance(row, dict)):
            raise MechanismB2FitAuthorityError("mechanism B2 example contains forbidden risk field")
        forbidden = tuple(sorted(str(x).strip() for x in fit_input["forbidden_task_ids"] if str(x).strip()))
    except MechanismB2FitAuthorityError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise MechanismB2FitAuthorityError("malformed mechanism B2 fit input") from exc

    calibration = tuple(sorted(str(x) for x in partition["calibration_task_ids"]))
    confirmatory = tuple(sorted(str(x) for x in partition["confirmatory_task_ids"]))
    generalization = tuple(sorted(str(x) for x in partition["generalization_task_ids"]))
    if tuple(sorted({row.task_id for row in examples})) != calibration:
        raise MechanismB2FitAuthorityError("mechanism B2 examples must cover exact calibration tasks")
    if forbidden != tuple(sorted(set(confirmatory) | set(generalization))):
        raise MechanismB2FitAuthorityError("mechanism B2 forbidden tasks must equal confirmatory + G1 holdout")
    if _sha("expected_feature_schema_digest", fit_input.get("expected_feature_schema_digest")) != config.feature_schema_digest:
        raise MechanismB2FitAuthorityError("mechanism B2 feature schema digest mismatch")
    if _sha("expected_training_algorithm_digest", fit_input.get("expected_training_algorithm_digest")) != config.training_algorithm_digest:
        raise MechanismB2FitAuthorityError("mechanism B2 training algorithm digest mismatch")

    recomputed = fit_mechanism_b2_with_receipt(
        config=config,
        examples=examples,
        forbidden_task_ids=forbidden,
        expected_feature_schema_digest=config.feature_schema_digest,
        expected_training_algorithm_digest=config.training_algorithm_digest,
    )
    if asdict(recomputed) != declared:
        raise MechanismB2FitAuthorityError("declared mechanism B2 receipt differs from deterministic recomputation")
    if recomputed.calibration_task_digest != partition.get("calibration_task_digest"):
        raise MechanismB2FitAuthorityError("mechanism B2 calibration digest differs from partition")
    payload = {
        "family_id": execution["family_id"],
        "execution_manifest_freeze_digest": _sha("execution freeze_digest", execution.get("freeze_digest")),
        "task_partition_receipt_digest": _sha("partition receipt_digest", partition.get("receipt_digest")),
        "fit_input_sha256": sha256_file(Path(fit_input_path)),
        "fit_receipt_sha256": sha256_file(Path(fit_receipt_path)),
        "feature_schema_digest": recomputed.feature_schema_digest,
        "training_algorithm_digest": recomputed.training_algorithm_digest,
        "calibration_task_digest": recomputed.calibration_task_digest,
        "confirmatory_task_digest": _sha("confirmatory_task_digest", partition.get("confirmatory_task_digest")),
        "generalization_task_digest": _sha("generalization_task_digest", partition.get("generalization_task_digest")),
        "fitted_model_digest": recomputed.fitted_model_digest,
        "calibration_task_count": recomputed.calibration_task_count,
    }
    return MechanismB2FitAuthority(
        **payload,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_mechanism_b2_fit_authority_document(path: Path) -> dict[str, object]:
    doc = _json(Path(path), SCHEMA)
    if (
        doc.get("risk_fields_consumed") is not False
        or doc.get("mechanism_execution_authorized") is not False
        or doc.get("risk_qualification_authorized") is not False
        or doc.get("product_promotion_authorized") is not False
    ):
        raise MechanismB2FitAuthorityError("mechanism B2 authority boundary violated")
    payload = {
        key: doc[key]
        for key in (
            "family_id", "execution_manifest_freeze_digest", "task_partition_receipt_digest",
            "fit_input_sha256", "fit_receipt_sha256", "feature_schema_digest",
            "training_algorithm_digest", "calibration_task_digest", "confirmatory_task_digest",
            "generalization_task_digest", "fitted_model_digest", "calibration_task_count",
        )
    }
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("authority_digest", doc.get("authority_digest")):
        raise MechanismB2FitAuthorityError("mechanism B2 authority digest mismatch")
    if int(doc.get("calibration_task_count", 0)) <= 0:
        raise MechanismB2FitAuthorityError("mechanism B2 calibration_task_count must be > 0")
    return doc
