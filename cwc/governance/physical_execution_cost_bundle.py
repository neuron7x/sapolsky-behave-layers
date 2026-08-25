from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.confirmatory_execution_authority import verify_confirmatory_execution_authority_document
from cwc.governance.confirmatory_root_authority import verify_confirmatory_root_authority_document
from cwc.governance.distributed_eval_control import DistributedEvalSpec, WorkUnitId
from cwc.governance.execution_evidence_bundle import VerifiedExecutionBundle, verify_execution_bundle
from cwc.governance.materialization_transaction import canonical_json_bytes, file_manifest, sha256_bytes
from cwc.governance.physical_cost_authority import VerifiedPhysicalCost, verify_physical_trial_cost_document

SCHEMA = "DGC_PHYSICAL_EXECUTION_COST_BUNDLE_V1"


class PhysicalExecutionCostBundleError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise PhysicalExecutionCostBundleError(f"{name} must be lowercase SHA-256")
    return text


def _path(root: Path, value: object) -> tuple[Path, str]:
    rel = Path(str(value))
    if not str(value) or rel.is_absolute() or ".." in rel.parts:
        raise PhysicalExecutionCostBundleError("physical cost path must be relative and non-traversing")
    candidate = root / rel
    if candidate.is_symlink():
        raise PhysicalExecutionCostBundleError("physical cost path symlink rejected")
    path = candidate.resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise PhysicalExecutionCostBundleError("physical cost path escapes bundle") from exc
    if not path.is_file() or path.stat().st_size <= 0:
        raise PhysicalExecutionCostBundleError("physical cost path must be a non-empty regular file")
    return path, rel.as_posix()


def _json(path: Path) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise PhysicalExecutionCostBundleError("physical cost bundle manifest must be a regular file")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PhysicalExecutionCostBundleError("invalid physical cost bundle manifest") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise PhysicalExecutionCostBundleError("unexpected physical cost bundle schema")
    return doc


def _unit(stable_id: str, expected: Mapping[str, WorkUnitId]) -> WorkUnitId:
    try:
        return expected[stable_id]
    except KeyError as exc:
        raise PhysicalExecutionCostBundleError(f"physical cost row outside frozen execution population: {stable_id}") from exc


@dataclass(frozen=True, slots=True)
class PhysicalUnitCost:
    unit: WorkUnitId
    physical_cost_path: str
    certificate_digest: str
    physical_cost_document_digest: str
    total_operational_usd: float


@dataclass(frozen=True, slots=True)
class VerifiedPhysicalExecutionCostBundle:
    family_id: str
    confirmatory_execution_authority_digest: str
    execution_population_digest: str
    execution_bundle_digest: str
    distributed_spec_digest: str
    payload_manifest_sha256: str
    per_unit_cost_cap_usd: float
    costs: tuple[PhysicalUnitCost, ...]
    physical_cost_population_digest: str
    total_operational_usd: float
    bundle_digest: str

    def cost_by_unit(self) -> dict[WorkUnitId, float]:
        return {row.unit: row.total_operational_usd for row in self.costs}


def verify_physical_execution_cost_bundle(
    bundle_root: Path,
    *,
    confirmatory_execution_authority_path: Path,
    execution_bundle_root: Path,
    confirmatory_root_authority_path: Path,
) -> VerifiedPhysicalExecutionCostBundle:
    supplied = Path(bundle_root)
    if supplied.is_symlink() or not supplied.is_dir():
        raise PhysicalExecutionCostBundleError("physical cost bundle root must be a real directory")
    root = supplied.resolve()
    manifest = _json(root / "PHYSICAL_COST_BUNDLE.json")
    execution_authority = verify_confirmatory_execution_authority_document(
        Path(confirmatory_execution_authority_path)
    )
    execution_bundle: VerifiedExecutionBundle = verify_execution_bundle(
        Path(execution_bundle_root),
        confirmatory_root_authority_path=Path(confirmatory_root_authority_path),
    )
    root_authority = verify_confirmatory_root_authority_document(Path(confirmatory_root_authority_path))
    spec_doc = root_authority.get("distributed_spec")
    if not isinstance(spec_doc, Mapping):
        raise PhysicalExecutionCostBundleError("distributed spec missing from confirmatory root")
    try:
        spec = DistributedEvalSpec(**dict(spec_doc))
    except (TypeError, ValueError) as exc:
        raise PhysicalExecutionCostBundleError("distributed spec cannot be reconstructed") from exc
    if spec.digest != root_authority.get("distributed_spec_digest"):
        raise PhysicalExecutionCostBundleError("distributed spec digest mismatch")

    execution_authority_digest = _sha(
        "confirmatory_execution_authority_digest", execution_authority.get("authority_digest")
    )
    if manifest.get("confirmatory_execution_authority_digest") != execution_authority_digest:
        raise PhysicalExecutionCostBundleError("physical cost bundle bound to different execution authority")
    if manifest.get("execution_population_digest") != execution_authority.get("execution_population_digest"):
        raise PhysicalExecutionCostBundleError("physical cost bundle execution population mismatch")
    if manifest.get("execution_bundle_digest") != execution_bundle.bundle_digest:
        raise PhysicalExecutionCostBundleError("physical cost bundle execution subject mismatch")
    if manifest.get("distributed_spec_digest") != spec.digest:
        raise PhysicalExecutionCostBundleError("physical cost bundle distributed spec mismatch")
    if manifest.get("family_id") != execution_authority.get("family_id"):
        raise PhysicalExecutionCostBundleError("physical cost bundle family mismatch")
    if manifest.get("product_promotion_authorized") is not False:
        raise PhysicalExecutionCostBundleError("physical cost bundle cannot authorize product promotion")

    payload_rows = file_manifest(root, excluded_names=frozenset({"PHYSICAL_COST_BUNDLE.json"}))
    payload_digest = sha256_bytes(canonical_json_bytes(payload_rows))
    if _sha("payload_manifest_sha256", manifest.get("payload_manifest_sha256")) != payload_digest:
        raise PhysicalExecutionCostBundleError("physical cost bundle payload manifest mismatch")

    per_unit_cap = float(spec.max_cost_per_unit_usd)
    if not math.isfinite(per_unit_cap) or per_unit_cap <= 0:
        raise PhysicalExecutionCostBundleError("frozen per-unit cost cap invalid")
    declared_cap = float(manifest.get("per_unit_cost_cap_usd", -1))
    if not math.isclose(declared_cap, per_unit_cap, rel_tol=0.0, abs_tol=1e-12):
        raise PhysicalExecutionCostBundleError("physical cost bundle cap differs from frozen distributed spec")

    expected_units = {unit.stable_id: unit for unit in spec.units()}
    execution_units = {row.unit.stable_id for row in execution_bundle.results}
    if execution_units != set(expected_units):
        raise PhysicalExecutionCostBundleError("execution subject is not complete before physical cost binding")
    rows = manifest.get("cost_rows")
    if not isinstance(rows, list) or len(rows) != len(expected_units):
        raise PhysicalExecutionCostBundleError("physical cost bundle requires exactly one row per frozen work unit")

    verified: list[PhysicalUnitCost] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise PhysicalExecutionCostBundleError("invalid physical cost bundle row")
        stable_id = str(row.get("unit_id", ""))
        if not stable_id or stable_id in seen:
            raise PhysicalExecutionCostBundleError("physical cost unit ids must be unique")
        seen.add(stable_id)
        unit = _unit(stable_id, expected_units)
        path, rel = _path(root, row.get("physical_cost_path"))
        try:
            cost: VerifiedPhysicalCost = verify_physical_trial_cost_document(
                path,
                bundle_root=root,
                expected_trial_id=stable_id,
            )
        except RuntimeError as exc:
            raise PhysicalExecutionCostBundleError("physical trial cost verification failed") from exc
        if cost.total_operational_usd > per_unit_cap + 1e-12:
            raise PhysicalExecutionCostBundleError("all-in physical trial cost exceeds preregistered per-unit cap")
        if row.get("certificate_digest") != cost.certificate_digest:
            raise PhysicalExecutionCostBundleError("physical cost row certificate mismatch")
        if row.get("physical_cost_document_digest") != cost.physical_cost_document_digest:
            raise PhysicalExecutionCostBundleError("physical cost row document digest mismatch")
        declared = float(row.get("total_operational_usd", -1))
        if not math.isclose(declared, cost.total_operational_usd, rel_tol=0.0, abs_tol=1e-12):
            raise PhysicalExecutionCostBundleError("physical cost row total mismatch")
        verified.append(PhysicalUnitCost(
            unit=unit,
            physical_cost_path=rel,
            certificate_digest=cost.certificate_digest,
            physical_cost_document_digest=cost.physical_cost_document_digest,
            total_operational_usd=cost.total_operational_usd,
        ))
    if seen != set(expected_units):
        raise PhysicalExecutionCostBundleError("physical cost population does not equal frozen execution population")

    ordered = tuple(sorted(verified, key=lambda item: item.unit))
    population_rows = [
        (
            row.unit.stable_id,
            row.certificate_digest,
            row.physical_cost_document_digest,
            row.total_operational_usd,
        )
        for row in ordered
    ]
    population_digest = sha256_bytes(canonical_json_bytes(population_rows))
    total = math.fsum(row.total_operational_usd for row in ordered)
    if manifest.get("physical_cost_population_digest") != population_digest:
        raise PhysicalExecutionCostBundleError("physical cost population digest mismatch")
    if not math.isclose(float(manifest.get("total_operational_usd", -1)), total, rel_tol=0.0, abs_tol=1e-12):
        raise PhysicalExecutionCostBundleError("physical cost bundle total mismatch")

    manifest_payload = {
        "family_id": str(execution_authority["family_id"]),
        "confirmatory_execution_authority_digest": execution_authority_digest,
        "execution_population_digest": str(execution_authority["execution_population_digest"]),
        "execution_bundle_digest": execution_bundle.bundle_digest,
        "distributed_spec_digest": spec.digest,
        "payload_manifest_sha256": payload_digest,
        "per_unit_cost_cap_usd": per_unit_cap,
        "cost_rows": [
            {
                "unit_id": row.unit.stable_id,
                "physical_cost_path": row.physical_cost_path,
                "certificate_digest": row.certificate_digest,
                "physical_cost_document_digest": row.physical_cost_document_digest,
                "total_operational_usd": row.total_operational_usd,
            }
            for row in ordered
        ],
        "physical_cost_population_digest": population_digest,
        "total_operational_usd": total,
        "product_promotion_authorized": False,
    }
    bundle_digest = sha256_bytes(canonical_json_bytes(manifest_payload))
    if _sha("bundle_digest", manifest.get("bundle_digest")) != bundle_digest:
        raise PhysicalExecutionCostBundleError("physical cost bundle digest mismatch")
    return VerifiedPhysicalExecutionCostBundle(
        family_id=str(execution_authority["family_id"]),
        confirmatory_execution_authority_digest=execution_authority_digest,
        execution_population_digest=str(execution_authority["execution_population_digest"]),
        execution_bundle_digest=execution_bundle.bundle_digest,
        distributed_spec_digest=spec.digest,
        payload_manifest_sha256=payload_digest,
        per_unit_cost_cap_usd=per_unit_cap,
        costs=ordered,
        physical_cost_population_digest=population_digest,
        total_operational_usd=total,
        bundle_digest=bundle_digest,
    )
