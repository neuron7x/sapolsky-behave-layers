from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.confirmatory_root_authority import verify_confirmatory_root_authority_document
from cwc.governance.distributed_eval_control import CompletionCertificate, DistributedEvalSpec, WorkUnitId
from cwc.governance.materialization_transaction import canonical_json_bytes, file_manifest, sha256_bytes, sha256_file

BUNDLE_SCHEMA = "DGC_CONFIRMATORY_EXECUTION_BUNDLE_V1"
RESULT_SCHEMA = "DGC_CONFIRMATORY_RESULT_V1"
AUDIT_SCHEMA = "DGC_DISTRIBUTED_AUDIT_LOG_V1"


class ExecutionEvidenceError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise ExecutionEvidenceError(f"{name} must be lowercase SHA-256")
    return text


def _req(name: str, value: object) -> str:
    text = str(value).strip()
    if not text:
        raise ExecutionEvidenceError(f"{name} required")
    return text


def _nonnegative_int(name: str, value: object) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ExecutionEvidenceError(f"{name} must be an integer") from exc
    if result < 0:
        raise ExecutionEvidenceError(f"{name} must be >= 0")
    return result


def _finite(name: str, value: object, *, lower: float | None = None, upper: float | None = None) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ExecutionEvidenceError(f"{name} must be numeric") from exc
    if not math.isfinite(result):
        raise ExecutionEvidenceError(f"{name} must be finite")
    if lower is not None and result < lower:
        raise ExecutionEvidenceError(f"{name} below lower bound")
    if upper is not None and result > upper:
        raise ExecutionEvidenceError(f"{name} above upper bound")
    return result


def _safe_relative(root: Path, value: object, *, require_file: bool = True) -> tuple[Path, str]:
    rel = Path(str(value))
    if not str(value) or rel.is_absolute() or ".." in rel.parts:
        raise ExecutionEvidenceError("execution evidence path must be relative and non-traversing")
    path = root / rel
    if path.is_symlink():
        raise ExecutionEvidenceError(f"execution evidence symlink rejected: {rel.as_posix()}")
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ExecutionEvidenceError("execution evidence path escapes bundle root") from exc
    if require_file and not resolved.is_file():
        raise ExecutionEvidenceError(f"execution evidence file missing: {rel.as_posix()}")
    return resolved, rel.as_posix()


def _json(path: Path, *, schema: str) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise ExecutionEvidenceError(f"missing regular JSON evidence: {path}")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExecutionEvidenceError(f"invalid JSON evidence: {path}") from exc
    if not isinstance(doc, dict) or doc.get("schema") != schema:
        raise ExecutionEvidenceError(f"unexpected schema for {path}")
    return doc


def _unit_from_mapping(value: object) -> WorkUnitId:
    if not isinstance(value, Mapping):
        raise ExecutionEvidenceError("result unit must be an object")
    try:
        return WorkUnitId(
            task_id=str(value["task_id"]),
            policy_id=str(value["policy_id"]),
            replicate=int(value["replicate"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ExecutionEvidenceError("invalid result work unit") from exc


def canonical_result_payload_digest(payload: Mapping[str, object]) -> str:
    return sha256_bytes(canonical_json_bytes(dict(payload)))


@dataclass(frozen=True, slots=True)
class VerifiedExecutionResult:
    unit: WorkUnitId
    attempt: int
    worker_id: str
    committed_tick: int
    result_payload: dict[str, object]
    result_digest: str
    quality: float
    catastrophic_regret: float
    actual_cost_usd: float
    evidence_path: str
    evidence_digest: str
    record_digest: str
    commit_event_sequence: int


@dataclass(frozen=True, slots=True)
class VerifiedExecutionBundle:
    family_id: str
    root_authority_digest: str
    root_digest: str
    distributed_spec_digest: str
    payload_manifest_sha256: str
    audit_root_digest: str
    result_population_digest: str
    total_cost_usd: float
    results: tuple[VerifiedExecutionResult, ...]
    completion: CompletionCertificate
    bundle_digest: str


def _verify_audit_log(path: Path, *, spec_digest: str) -> tuple[list[dict[str, object]], str]:
    doc = _json(path, schema=AUDIT_SCHEMA)
    if _sha("audit spec_digest", doc.get("spec_digest")) != spec_digest:
        raise ExecutionEvidenceError("audit log belongs to a different distributed spec")
    events = doc.get("events")
    if not isinstance(events, list) or not events:
        raise ExecutionEvidenceError("non-empty distributed audit event list required")
    previous = "GENESIS"
    normalized: list[dict[str, object]] = []
    for expected_sequence, row in enumerate(events):
        if not isinstance(row, Mapping):
            raise ExecutionEvidenceError("invalid audit event")
        try:
            sequence = int(row["sequence"])
            kind = _req("audit kind", row["kind"])
            unit_id_raw = row.get("unit_id")
            unit_id = None if unit_id_raw is None else _req("audit unit_id", unit_id_raw)
            payload_digest = _sha("audit payload_digest", row["payload_digest"])
            observed_previous = str(row["previous_digest"])
            event_digest = _sha("audit event_digest", row["event_digest"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ExecutionEvidenceError("malformed audit event") from exc
        if sequence != expected_sequence or observed_previous != previous:
            raise ExecutionEvidenceError("audit sequence/chain discontinuity")
        expected_digest = sha256_bytes(canonical_json_bytes({
            "sequence": sequence,
            "kind": kind,
            "unit_id": unit_id,
            "payload_digest": payload_digest,
            "previous_digest": previous,
        }))
        if event_digest != expected_digest:
            raise ExecutionEvidenceError("audit event digest mismatch")
        if kind == "QUARANTINE":
            raise ExecutionEvidenceError("confirmatory execution contains a quarantined work unit")
        normalized.append({
            "sequence": sequence,
            "kind": kind,
            "unit_id": unit_id,
            "payload_digest": payload_digest,
            "previous_digest": previous,
            "event_digest": event_digest,
        })
        previous = event_digest
    declared_root = _sha("audit_root_digest", doc.get("audit_root_digest"))
    if declared_root != previous:
        raise ExecutionEvidenceError("declared audit root does not equal replayed chain root")
    payload = {
        "spec_digest": spec_digest,
        "events": normalized,
        "audit_root_digest": previous,
    }
    if _sha("audit_log_digest", doc.get("audit_log_digest")) != sha256_bytes(canonical_json_bytes(payload)):
        raise ExecutionEvidenceError("audit log digest mismatch")
    return normalized, previous


def _verify_result(
    path: Path,
    *,
    bundle_root: Path,
    root_authority_digest: str,
    root_digest: str,
    spec: DistributedEvalSpec,
    audit_events: list[dict[str, object]],
) -> VerifiedExecutionResult:
    doc = _json(path, schema=RESULT_SCHEMA)
    if _sha("result root_authority_digest", doc.get("root_authority_digest")) != root_authority_digest:
        raise ExecutionEvidenceError("result belongs to a different confirmatory root authority")
    if _sha("result root_digest", doc.get("root_digest")) != root_digest:
        raise ExecutionEvidenceError("result belongs to a different confirmatory generation root")
    if _sha("result spec_digest", doc.get("distributed_spec_digest")) != spec.digest:
        raise ExecutionEvidenceError("result belongs to a different distributed spec")
    unit = _unit_from_mapping(doc.get("unit"))
    if unit not in set(spec.units()):
        raise ExecutionEvidenceError("result unit is outside frozen execution population")
    attempt = _nonnegative_int("attempt", doc.get("attempt"))
    if attempt < 1 or attempt > spec.max_attempts_per_unit:
        raise ExecutionEvidenceError("result attempt outside frozen attempt budget")
    worker_id = _req("worker_id", doc.get("worker_id"))
    committed_tick = _nonnegative_int("committed_tick", doc.get("committed_tick"))
    result_payload = doc.get("result_payload")
    if not isinstance(result_payload, Mapping):
        raise ExecutionEvidenceError("result_payload must be an object")
    result_payload = dict(result_payload)
    quality = _finite("quality", result_payload.get("quality"), lower=0.0, upper=1.0)
    catastrophic = _finite(
        "catastrophic_regret", result_payload.get("catastrophic_regret"), lower=0.0, upper=1.0
    )
    result_digest = canonical_result_payload_digest(result_payload)
    if _sha("result_digest", doc.get("result_digest")) != result_digest:
        raise ExecutionEvidenceError("result payload digest mismatch")
    cost = _finite(
        "actual_cost_usd", doc.get("actual_cost_usd"), lower=0.0, upper=spec.max_cost_per_unit_usd
    )
    evidence_path, evidence_rel = _safe_relative(bundle_root, doc.get("evidence_path"))
    evidence_digest = sha256_file(evidence_path)
    if evidence_path.stat().st_size <= 0:
        raise ExecutionEvidenceError("empty execution evidence artifact is not accepted")
    if _sha("evidence_sha256", doc.get("evidence_sha256")) != evidence_digest:
        raise ExecutionEvidenceError("execution evidence digest mismatch")

    record_payload = {
        "root_authority_digest": root_authority_digest,
        "root_digest": root_digest,
        "distributed_spec_digest": spec.digest,
        "unit": asdict(unit),
        "attempt": attempt,
        "worker_id": worker_id,
        "committed_tick": committed_tick,
        "result_payload": result_payload,
        "result_digest": result_digest,
        "actual_cost_usd": cost,
        "evidence_path": evidence_rel,
        "evidence_sha256": evidence_digest,
    }
    record_digest = sha256_bytes(canonical_json_bytes(record_payload))
    if _sha("record_digest", doc.get("record_digest")) != record_digest:
        raise ExecutionEvidenceError("execution result record digest mismatch")

    expected_commit_payload_digest = sha256_bytes(canonical_json_bytes({
        "attempt": attempt,
        "worker_id": worker_id,
        "result_digest": result_digest,
        "evidence_digest": evidence_digest,
        "actual_cost_usd": cost,
        "committed_tick": committed_tick,
    }))
    commit_matches = [
        event for event in audit_events
        if event["kind"] == "RESULT_COMMITTED"
        and event["unit_id"] == unit.stable_id
        and event["payload_digest"] == expected_commit_payload_digest
    ]
    if len(commit_matches) != 1:
        raise ExecutionEvidenceError("result cannot be bound to exactly one coordinator commit audit event")
    commit_sequence = int(commit_matches[0]["sequence"])
    lease_before_commit = any(
        event["kind"] == "LEASE_GRANTED"
        and event["unit_id"] == unit.stable_id
        and int(event["sequence"]) < commit_sequence
        for event in audit_events
    )
    if not lease_before_commit:
        raise ExecutionEvidenceError("result commit has no preceding lease audit event")

    return VerifiedExecutionResult(
        unit=unit,
        attempt=attempt,
        worker_id=worker_id,
        committed_tick=committed_tick,
        result_payload=result_payload,
        result_digest=result_digest,
        quality=quality,
        catastrophic_regret=catastrophic,
        actual_cost_usd=cost,
        evidence_path=evidence_rel,
        evidence_digest=evidence_digest,
        record_digest=record_digest,
        commit_event_sequence=commit_sequence,
    )


def verify_execution_bundle(
    bundle_root: Path,
    *,
    confirmatory_root_authority_path: Path,
) -> VerifiedExecutionBundle:
    supplied = Path(bundle_root)
    if supplied.is_symlink() or not supplied.is_dir():
        raise ExecutionEvidenceError("execution bundle root must be a real directory")
    root = supplied.resolve()
    manifest_path = root / "EXECUTION_BUNDLE.json"
    manifest = _json(manifest_path, schema=BUNDLE_SCHEMA)
    root_authority = verify_confirmatory_root_authority_document(Path(confirmatory_root_authority_path))
    root_authority_digest = _sha("root authority_digest", root_authority.get("authority_digest"))
    root_doc = root_authority.get("root")
    spec_doc = root_authority.get("distributed_spec")
    if not isinstance(root_doc, Mapping) or not isinstance(spec_doc, Mapping):
        raise ExecutionEvidenceError("confirmatory root/spec payload missing")
    root_digest = _sha("root_digest", root_doc.get("root_digest"))
    try:
        spec = DistributedEvalSpec(**dict(spec_doc))
    except (TypeError, ValueError) as exc:
        raise ExecutionEvidenceError("distributed spec cannot be reconstructed") from exc
    if spec.digest != _sha("distributed_spec_digest", root_authority.get("distributed_spec_digest")):
        raise ExecutionEvidenceError("distributed spec digest mismatch")

    if _sha("bundle root_authority_digest", manifest.get("root_authority_digest")) != root_authority_digest:
        raise ExecutionEvidenceError("execution bundle belongs to a different root authority")
    if _sha("bundle root_digest", manifest.get("root_digest")) != root_digest:
        raise ExecutionEvidenceError("execution bundle belongs to a different root")
    if _sha("bundle distributed_spec_digest", manifest.get("distributed_spec_digest")) != spec.digest:
        raise ExecutionEvidenceError("execution bundle belongs to a different distributed spec")
    if str(manifest.get("family_id", "")) != str(root_authority.get("family_id", "")):
        raise ExecutionEvidenceError("execution bundle family mismatch")
    if manifest.get("product_promotion_authorized") is not False:
        raise ExecutionEvidenceError("execution bundle cannot authorize product promotion")

    observed_rows = file_manifest(root, excluded_names=frozenset({"EXECUTION_BUNDLE.json"}))
    observed_payload_digest = sha256_bytes(canonical_json_bytes(observed_rows))
    if _sha("payload_manifest_sha256", manifest.get("payload_manifest_sha256")) != observed_payload_digest:
        raise ExecutionEvidenceError("execution bundle payload manifest mismatch")

    audit_path, audit_rel = _safe_relative(root, manifest.get("audit_log_path"))
    audit_events, audit_root = _verify_audit_log(audit_path, spec_digest=spec.digest)
    if audit_rel == "EXECUTION_BUNDLE.json":
        raise ExecutionEvidenceError("bundle manifest cannot be its own audit log")

    raw_result_paths = manifest.get("result_paths")
    if not isinstance(raw_result_paths, list) or not raw_result_paths:
        raise ExecutionEvidenceError("execution bundle requires result_paths")
    result_paths: list[tuple[Path, str]] = []
    seen_paths: set[str] = set()
    for value in raw_result_paths:
        path, rel = _safe_relative(root, value)
        if rel in seen_paths:
            raise ExecutionEvidenceError("duplicate result path")
        seen_paths.add(rel)
        result_paths.append((path, rel))

    results = tuple(
        _verify_result(
            path,
            bundle_root=root,
            root_authority_digest=root_authority_digest,
            root_digest=root_digest,
            spec=spec,
            audit_events=audit_events,
        )
        for path, _ in result_paths
    )
    expected_units = set(spec.units())
    observed_units = [row.unit for row in results]
    if len(observed_units) != len(set(observed_units)):
        raise ExecutionEvidenceError("duplicate work-unit results")
    if set(observed_units) != expected_units:
        missing = sorted(unit.stable_id for unit in expected_units - set(observed_units))
        extra = sorted(unit.stable_id for unit in set(observed_units) - expected_units)
        raise ExecutionEvidenceError(
            f"full frozen work population required; missing={missing[:5]}; extra={extra[:5]}"
        )
    commit_events = [event for event in audit_events if event["kind"] == "RESULT_COMMITTED"]
    if len(commit_events) != len(results):
        raise ExecutionEvidenceError("audit RESULT_COMMITTED population differs from result population")

    # Reproduce coordinator completion ordering: spend accumulates in commit-event order;
    # result_population_digest is sorted by WorkUnitId.
    by_commit = sorted(results, key=lambda row: row.commit_event_sequence)
    spent = 0.0
    for row in by_commit:
        spent += row.actual_cost_usd
    if spent > spec.global_budget_usd + 1e-12:
        raise ExecutionEvidenceError("replayed execution cost exceeds frozen global budget")
    by_unit = sorted(results, key=lambda row: row.unit)
    population_rows = [
        (
            row.unit.stable_id,
            row.attempt,
            row.worker_id,
            row.result_digest,
            row.evidence_digest,
            row.actual_cost_usd,
        )
        for row in by_unit
    ]
    population_digest = sha256_bytes(canonical_json_bytes(population_rows))
    completion = CompletionCertificate(
        experiment_id=spec.experiment_id,
        spec_digest=spec.digest,
        expected_units=len(expected_units),
        committed_units=len(results),
        total_cost_usd=spent,
        audit_root_digest=audit_root,
        result_population_digest=population_digest,
        complete=True,
    )

    manifest_payload = {
        "family_id": str(root_authority["family_id"]),
        "root_authority_digest": root_authority_digest,
        "root_digest": root_digest,
        "distributed_spec_digest": spec.digest,
        "payload_manifest_sha256": observed_payload_digest,
        "audit_log_path": audit_rel,
        "result_paths": [rel for _, rel in result_paths],
        "expected_units": len(expected_units),
        "committed_units": len(results),
        "audit_root_digest": audit_root,
        "result_population_digest": population_digest,
        "total_cost_usd": spent,
        "product_promotion_authorized": False,
    }
    bundle_digest = sha256_bytes(canonical_json_bytes(manifest_payload))
    if _sha("bundle_digest", manifest.get("bundle_digest")) != bundle_digest:
        raise ExecutionEvidenceError("execution bundle digest mismatch")
    for key in ("expected_units", "committed_units"):
        if int(manifest.get(key, -1)) != int(manifest_payload[key]):
            raise ExecutionEvidenceError(f"execution bundle {key} mismatch")
    for key in ("audit_root_digest", "result_population_digest"):
        if manifest.get(key) != manifest_payload[key]:
            raise ExecutionEvidenceError(f"execution bundle {key} mismatch")
    declared_cost = _finite("bundle total_cost_usd", manifest.get("total_cost_usd"), lower=0.0)
    if not math.isclose(declared_cost, spent, rel_tol=0.0, abs_tol=1e-12):
        raise ExecutionEvidenceError("execution bundle total cost mismatch")

    return VerifiedExecutionBundle(
        family_id=str(root_authority["family_id"]),
        root_authority_digest=root_authority_digest,
        root_digest=root_digest,
        distributed_spec_digest=spec.digest,
        payload_manifest_sha256=observed_payload_digest,
        audit_root_digest=audit_root,
        result_population_digest=population_digest,
        total_cost_usd=spent,
        results=results,
        completion=completion,
        bundle_digest=bundle_digest,
    )
