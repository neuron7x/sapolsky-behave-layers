from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.external_materialization import parse_terminal_dataset_manifest, verify_swe_parquet
from cwc.governance.git_tree_reconstruction import git_blob_oid_path
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.product_statistical_plan import ProductStatisticalPlan, deterministic_task_split

SCHEMA = "DGC_TASK_PARTITION_RECEIPT_V1"
REFERENCE_SCHEMA = "DGC_EXTERNAL_EVIDENCE_REFERENCE_V2"
REGISTRY_SCHEMA = "DGC_EXTERNAL_SOURCE_AUTHORITY_REGISTRY_V1"


class TaskPartitionError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise TaskPartitionError(f"{name} must be lowercase SHA-256")
    return text


def _read_json(path: Path, schema: str) -> dict[str, object]:
    if not path.is_file() or path.is_symlink():
        raise TaskPartitionError(f"missing regular JSON file: {path}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TaskPartitionError(f"invalid JSON file: {path}") from exc
    if not isinstance(value, dict) or value.get("schema") != schema:
        raise TaskPartitionError(f"unexpected schema for {path}")
    return value


def _task_digest(task_ids: tuple[str, ...]) -> str:
    return sha256_bytes(canonical_json_bytes(tuple(sorted(task_ids))))


def _reference_binding(reference: Mapping[str, object], family_id: str) -> Mapping[str, object]:
    bindings = reference.get("family_bindings")
    if not isinstance(bindings, list):
        raise TaskPartitionError("materialization reference bindings missing")
    rows = [row for row in bindings if isinstance(row, Mapping) and row.get("family_id") == family_id]
    if len(rows) != 1:
        raise TaskPartitionError("requested family binding missing or duplicated")
    return rows[0]


def _registry_row(registry: Mapping[str, object], family_id: str) -> Mapping[str, object]:
    rows = registry.get("families")
    if not isinstance(rows, list):
        raise TaskPartitionError("source registry families missing")
    matches = [row for row in rows if isinstance(row, Mapping) and row.get("family_id") == family_id]
    if len(matches) != 1:
        raise TaskPartitionError("requested source registry family missing or duplicated")
    return matches[0]


def _extract_task_ids(
    *, generation_root: Path, family_id: str, registry_row: Mapping[str, object]
) -> tuple[str, ...]:
    identity = registry_row.get("identity")
    if not isinstance(identity, Mapping):
        raise TaskPartitionError("source identity missing")
    root = Path(generation_root).resolve()
    if family_id == "SWE_BENCH_VERIFIED":
        rel = Path(str(identity.get("parquet_path", "")))
        if not str(rel) or rel.is_absolute() or ".." in rel.parts:
            raise TaskPartitionError("unsafe SWE parquet path")
        try:
            verified = verify_swe_parquet(
                root / family_id / rel,
                expected_sha256=_sha("SWE parquet_sha256", identity.get("parquet_sha256")),
                expected_bytes=None,
                expected_count=int(identity.get("expected_task_count")),
            )
        except (OSError, TypeError, ValueError, RuntimeError) as exc:
            raise TaskPartitionError("SWE task population cannot be reverified") from exc
        return tuple(sorted(verified.instance_ids))
    if family_id == "TERMINAL_BENCH_2_1":
        dataset = root / family_id / "repo" / "tasks" / "dataset.toml"
        expected_blob = str(identity.get("dataset_manifest_blob", "")).lower()
        if git_blob_oid_path(dataset) != expected_blob:
            raise TaskPartitionError("Terminal dataset manifest bytes do not match frozen Git blob")
        try:
            manifest = parse_terminal_dataset_manifest(
                dataset.read_text(encoding="utf-8"),
                expected_count=int(identity.get("expected_task_count")),
            )
        except (OSError, UnicodeError, TypeError, ValueError) as exc:
            raise TaskPartitionError("Terminal task population cannot be reverified") from exc
        return tuple(sorted(name for name, _ in manifest.tasks))
    raise TaskPartitionError("unsupported external workload family")


@dataclass(frozen=True, slots=True)
class TaskPartitionReceipt:
    family_id: str
    materialization_reference_digest: str
    task_manifest_digest: str
    task_count: int
    calibration_task_ids: tuple[str, ...]
    confirmatory_task_ids: tuple[str, ...]
    calibration_task_digest: str
    confirmatory_task_digest: str
    statistical_plan_digest: str
    calibration_fraction: float
    receipt_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            **asdict(self),
            "outcomes_observed": False,
            "confirmatory_execution_authorized": False,
            "product_promotion_authorized": False,
        }


def freeze_task_partition(
    *,
    generation_root: Path,
    materialization_reference_path: Path,
    source_registry_path: Path,
    family_id: str,
    statistical_plan: ProductStatisticalPlan,
) -> TaskPartitionReceipt:
    reference = _read_json(Path(materialization_reference_path), REFERENCE_SCHEMA)
    registry = _read_json(Path(source_registry_path), REGISTRY_SCHEMA)
    reference_digest = _sha("materialization reference_digest", reference.get("reference_digest"))
    reference_payload = dict(reference)
    reference_payload.pop("reference_digest", None)
    if sha256_bytes(canonical_json_bytes(reference_payload)) != reference_digest:
        raise TaskPartitionError("materialization reference digest mismatch")
    if _sha("source_registry_sha256", reference.get("source_registry_sha256")) != sha256_file(Path(source_registry_path)):
        raise TaskPartitionError("task partition source registry differs from materialization authority")
    binding = _reference_binding(reference, family_id)
    row = _registry_row(registry, family_id)
    task_ids = _extract_task_ids(generation_root=generation_root, family_id=family_id, registry_row=row)
    observed_task_digest = _task_digest(task_ids)
    if observed_task_digest != _sha("materialized_task_manifest_sha256", binding.get("materialized_task_manifest_sha256")):
        raise TaskPartitionError("reverified task population does not match materialization reference")
    calibration, confirmatory = deterministic_task_split(
        task_ids,
        calibration_fraction=statistical_plan.calibration_fraction,
    )
    calibration_digest = _task_digest(calibration)
    confirmatory_digest = _task_digest(confirmatory)
    payload = {
        "family_id": family_id,
        "materialization_reference_digest": reference_digest,
        "task_manifest_digest": observed_task_digest,
        "task_count": len(task_ids),
        "calibration_task_ids": calibration,
        "confirmatory_task_ids": confirmatory,
        "calibration_task_digest": calibration_digest,
        "confirmatory_task_digest": confirmatory_digest,
        "statistical_plan_digest": statistical_plan.digest,
        "calibration_fraction": statistical_plan.calibration_fraction,
    }
    return TaskPartitionReceipt(
        **payload,
        receipt_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_task_partition_document(path: Path) -> dict[str, object]:
    doc = _read_json(Path(path), SCHEMA)
    if doc.get("outcomes_observed") is not False:
        raise TaskPartitionError("task partition must be frozen before outcomes")
    if doc.get("confirmatory_execution_authorized") is not False or doc.get("product_promotion_authorized") is not False:
        raise TaskPartitionError("task partition illegally grants downstream authority")
    calibration = tuple(str(x) for x in doc.get("calibration_task_ids", ()))
    confirmatory = tuple(str(x) for x in doc.get("confirmatory_task_ids", ()))
    if not calibration or not confirmatory or set(calibration) & set(confirmatory):
        raise TaskPartitionError("invalid calibration/confirmatory partition")
    if len(calibration) + len(confirmatory) != int(doc.get("task_count", -1)):
        raise TaskPartitionError("task partition count mismatch")
    if _task_digest(calibration) != _sha("calibration_task_digest", doc.get("calibration_task_digest")):
        raise TaskPartitionError("calibration task digest mismatch")
    if _task_digest(confirmatory) != _sha("confirmatory_task_digest", doc.get("confirmatory_task_digest")):
        raise TaskPartitionError("confirmatory task digest mismatch")
    payload = {
        key: doc[key]
        for key in (
            "family_id", "materialization_reference_digest", "task_manifest_digest", "task_count",
            "calibration_task_ids", "confirmatory_task_ids", "calibration_task_digest",
            "confirmatory_task_digest", "statistical_plan_digest", "calibration_fraction",
        )
    }
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("receipt_digest", doc.get("receipt_digest")):
        raise TaskPartitionError("task partition receipt digest mismatch")
    return doc
