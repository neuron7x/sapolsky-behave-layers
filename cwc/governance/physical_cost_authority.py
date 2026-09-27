from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.physical_cost_evidence import (
    CostAuthority,
    CostComponentEvidence,
    PRODUCT_COST_COMPONENTS,
    PhysicalCostCertificate,
    certify_physical_trial_cost,
)

COST_SCHEMA = "DGC_PHYSICAL_TRIAL_COST_V1"
SOURCE_SCHEMA = "DGC_PHYSICAL_COST_SOURCE_V1"


class PhysicalCostAuthorityError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise PhysicalCostAuthorityError(f"{name} must be lowercase SHA-256")
    return text


def _req(name: str, value: object) -> str:
    text = str(value).strip()
    if not text:
        raise PhysicalCostAuthorityError(f"{name} required")
    return text


def _finite_nonnegative(name: str, value: object) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise PhysicalCostAuthorityError(f"{name} must be numeric") from exc
    if not math.isfinite(result) or result < 0.0:
        raise PhysicalCostAuthorityError(f"{name} must be finite and >= 0")
    return result


def _bundle_file(root: Path, value: object, *, label: str) -> tuple[Path, str]:
    rel = Path(str(value))
    if not str(value) or rel.is_absolute() or ".." in rel.parts:
        raise PhysicalCostAuthorityError(f"{label} path must be relative and non-traversing")
    candidate = root / rel
    if candidate.is_symlink():
        raise PhysicalCostAuthorityError(f"{label} symlink rejected")
    path = candidate.resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise PhysicalCostAuthorityError(f"{label} path escapes execution bundle") from exc
    if not path.is_file() or path.stat().st_size <= 0:
        raise PhysicalCostAuthorityError(f"{label} must be a non-empty regular file")
    return path, rel.as_posix()


def _json(path: Path, *, schema: str) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise PhysicalCostAuthorityError("physical cost JSON must be a regular file")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PhysicalCostAuthorityError("invalid physical cost JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != schema:
        raise PhysicalCostAuthorityError(f"unexpected physical cost schema; expected {schema}")
    return doc


def _verify_source(
    root: Path,
    *,
    source_path: object,
    component: str,
    authority: CostAuthority,
    value_usd: float,
) -> tuple[str, str]:
    path, rel = _bundle_file(root, source_path, label="physical cost source")
    doc = _json(path, schema=SOURCE_SCHEMA)
    if doc.get("component") != component:
        raise PhysicalCostAuthorityError("physical cost source component mismatch")
    if doc.get("authority") != authority.value:
        raise PhysicalCostAuthorityError("physical cost source authority mismatch")
    observed = _finite_nonnegative("physical cost source observed_value_usd", doc.get("observed_value_usd"))
    if not math.isclose(observed, value_usd, rel_tol=0.0, abs_tol=1e-12):
        raise PhysicalCostAuthorityError("physical cost source value mismatch")
    _req("physical cost source_id", doc.get("source_id"))

    raw_path, raw_rel = _bundle_file(root, doc.get("raw_artifact_path"), label="raw cost artifact")
    raw_sha = sha256_file(raw_path)
    if _sha("raw_artifact_sha256", doc.get("raw_artifact_sha256")) != raw_sha:
        raise PhysicalCostAuthorityError("raw cost artifact digest mismatch")
    if raw_rel == rel:
        raise PhysicalCostAuthorityError("physical cost source cannot self-reference as raw artifact")

    if authority is CostAuthority.PROVIDER_METER:
        _req("provider_request_id", doc.get("provider_request_id"))
    elif authority in {CostAuthority.TOOL_METER, CostAuthority.INFRA_METER}:
        _req("meter_record_id", doc.get("meter_record_id"))
    elif authority is CostAuthority.HUMAN_TIME_LOG:
        _req("time_log_id", doc.get("time_log_id"))
    elif authority is CostAuthority.FAILURE_LEDGER:
        _req("failure_record_id", doc.get("failure_record_id"))
    elif authority is CostAuthority.ZERO_BY_CONTRACT:
        if value_usd != 0.0:
            raise PhysicalCostAuthorityError("ZERO_BY_CONTRACT requires zero observed value")
        _req("contract_clause_id", doc.get("contract_clause_id"))

    source_payload = dict(doc)
    declared = source_payload.pop("source_digest", None)
    expected = sha256_bytes(canonical_json_bytes(source_payload))
    if _sha("source_digest", declared) != expected:
        raise PhysicalCostAuthorityError("physical cost source digest mismatch")
    return rel, expected


@dataclass(frozen=True, slots=True)
class VerifiedPhysicalCost:
    trial_id: str
    certificate_digest: str
    total_operational_usd: float
    component_source_rows: tuple[tuple[str, str, str, str], ...]
    physical_cost_document_digest: str


def verify_physical_trial_cost_document(
    path: Path,
    *,
    bundle_root: Path,
    expected_trial_id: str,
) -> VerifiedPhysicalCost:
    root = Path(bundle_root).resolve()
    if not root.is_dir():
        raise PhysicalCostAuthorityError("execution bundle root missing")
    doc = _json(Path(path), schema=COST_SCHEMA)
    trial_id = _req("trial_id", doc.get("trial_id"))
    if trial_id != expected_trial_id:
        raise PhysicalCostAuthorityError("physical cost trial_id does not match work unit")
    rows = doc.get("components")
    if not isinstance(rows, list) or len(rows) != len(PRODUCT_COST_COMPONENTS):
        raise PhysicalCostAuthorityError("physical cost document requires exactly all product cost components")

    evidence: dict[str, CostComponentEvidence] = {}
    source_rows: list[tuple[str, str, str, str]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise PhysicalCostAuthorityError("invalid physical cost component row")
        component = str(row.get("component", ""))
        if component in seen:
            raise PhysicalCostAuthorityError("duplicate physical cost component")
        seen.add(component)
        if component not in PRODUCT_COST_COMPONENTS:
            raise PhysicalCostAuthorityError("unknown physical cost component")
        value = _finite_nonnegative(f"{component}.value_usd", row.get("value_usd"))
        try:
            authority = CostAuthority(str(row.get("authority", "")))
        except ValueError as exc:
            raise PhysicalCostAuthorityError("unknown physical cost authority") from exc
        source_rel, source_digest = _verify_source(
            root,
            source_path=row.get("source_path"),
            component=component,
            authority=authority,
            value_usd=value,
        )
        if _sha(f"{component}.source_digest", row.get("source_digest")) != source_digest:
            raise PhysicalCostAuthorityError("physical cost component source digest mismatch")
        evidence[component] = CostComponentEvidence(
            component=component,
            value_usd=value,
            authority=authority,
            source_digest=source_digest,
        )
        source_rows.append((component, authority.value, source_rel, source_digest))

    if set(evidence) != set(PRODUCT_COST_COMPONENTS):
        raise PhysicalCostAuthorityError("physical cost component population incomplete")
    try:
        certificate: PhysicalCostCertificate = certify_physical_trial_cost(
            trial_id=trial_id,
            evidence=evidence,
        )
    except (TypeError, ValueError) as exc:
        raise PhysicalCostAuthorityError("physical cost certificate reconstruction failed") from exc
    declared_total = _finite_nonnegative("total_operational_usd", doc.get("total_operational_usd"))
    if not math.isclose(
        declared_total,
        certificate.cost.total_operational_usd,
        rel_tol=0.0,
        abs_tol=1e-12,
    ):
        raise PhysicalCostAuthorityError("physical cost total does not match component sum")
    if _sha("certificate_digest", doc.get("certificate_digest")) != certificate.digest:
        raise PhysicalCostAuthorityError("physical cost certificate digest mismatch")

    payload = {
        "trial_id": trial_id,
        "components": [
            {
                "component": row.component,
                "value_usd": row.value_usd,
                "authority": row.authority.value,
                "source_digest": row.source_digest,
            }
            for row in certificate.component_evidence
        ],
        "component_source_rows": sorted(source_rows),
        "total_operational_usd": certificate.cost.total_operational_usd,
        "certificate_digest": certificate.digest,
    }
    document_digest = sha256_bytes(canonical_json_bytes(payload))
    if _sha("physical_cost_document_digest", doc.get("physical_cost_document_digest")) != document_digest:
        raise PhysicalCostAuthorityError("physical cost document digest mismatch")
    return VerifiedPhysicalCost(
        trial_id=trial_id,
        certificate_digest=certificate.digest,
        total_operational_usd=certificate.cost.total_operational_usd,
        component_source_rows=tuple(sorted(source_rows)),
        physical_cost_document_digest=document_digest,
    )
