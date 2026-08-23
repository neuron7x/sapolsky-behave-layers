from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.execution_manifest_freeze import verify_execution_manifest_freeze_document
from cwc.governance.fault_injection_spec import (
    SPEC_SCHEMA,
    load_fault_spec,
    verify_fault_injection_spec_authority_document,
)
from cwc.governance.harness_freeze import DGC_ROLE, verify_harness_freeze_document
from cwc.governance.materialization_transaction import canonical_json_bytes, file_manifest, sha256_bytes, sha256_file

BUNDLE_SCHEMA = "DGC_FAULT_TOLERANCE_EVIDENCE_BUNDLE_V1"
TRACE_SCHEMA = "DGC_FAULT_TRACE_V1"
AUTHORITY_SCHEMA = "DGC_FAULT_TOLERANCE_AUTHORITY_V1"


class FaultToleranceError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise FaultToleranceError(f"{name} must be lowercase SHA-256")
    return text


def _safe_file(root: Path, value: object) -> tuple[Path, str]:
    rel = Path(str(value))
    if not str(value) or rel.is_absolute() or ".." in rel.parts:
        raise FaultToleranceError("fault evidence path must be relative and non-traversing")
    candidate = root / rel
    if candidate.is_symlink():
        raise FaultToleranceError("fault evidence symlink rejected")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise FaultToleranceError("fault evidence path escapes bundle") from exc
    if not resolved.is_file() or resolved.stat().st_size <= 0:
        raise FaultToleranceError("fault evidence path must be a non-empty regular file")
    return resolved, rel.as_posix()


def _json(path: Path, *, schema: str) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise FaultToleranceError("fault JSON subject must be a regular file")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FaultToleranceError("invalid fault JSON subject") from exc
    if not isinstance(doc, dict) or doc.get("schema") != schema:
        raise FaultToleranceError(f"unexpected fault JSON schema; expected {schema}")
    return doc


def _dgc_policy_id(harness: Mapping[str, object]) -> str:
    rows = harness.get("policy_role_bindings")
    if not isinstance(rows, list):
        raise FaultToleranceError("harness policy-role bindings missing")
    matches = [row for row in rows if isinstance(row, Mapping) and row.get("role") == DGC_ROLE]
    if len(matches) != 1 or not str(matches[0].get("policy_id", "")).strip():
        raise FaultToleranceError("harness must contain exactly one DGC policy binding")
    return str(matches[0]["policy_id"])


def _budget_cap(repository_root: Path, execution: Mapping[str, object]) -> float:
    components = execution.get("components")
    if not isinstance(components, list):
        raise FaultToleranceError("execution freeze component population missing")
    matches = [row for row in components if isinstance(row, Mapping) and row.get("component") == "budget"]
    if len(matches) != 1:
        raise FaultToleranceError("execution freeze must contain exactly one budget manifest")
    row = matches[0]
    path = repository_root / str(row.get("path", ""))
    if path.is_symlink() or not path.is_file() or sha256_file(path) != row.get("sha256"):
        raise FaultToleranceError("frozen budget manifest bytes unavailable or changed")
    budget = _json(path, schema="DGC_BUDGET_MANIFEST_V1")
    try:
        cap = float(budget["max_cost_usd"])
    except (KeyError, TypeError, ValueError) as exc:
        raise FaultToleranceError("frozen budget max_cost_usd invalid") from exc
    if not math.isfinite(cap) or cap < 0.0:
        raise FaultToleranceError("frozen budget max_cost_usd must be finite and >= 0")
    return cap


def _verify_event_chain(events: object) -> str:
    if not isinstance(events, list) or not events:
        raise FaultToleranceError("fault trace requires non-empty event chain")
    prior: str | None = None
    for index, raw in enumerate(events):
        if not isinstance(raw, Mapping):
            raise FaultToleranceError("malformed fault trace event")
        if int(raw.get("sequence", -1)) != index:
            raise FaultToleranceError("fault event sequence must be contiguous from zero")
        event_type = str(raw.get("event_type", "")).strip()
        action = str(raw.get("action", "")).strip()
        details = raw.get("details")
        if not event_type or not action or not isinstance(details, Mapping):
            raise FaultToleranceError("fault event type/action/details required")
        if raw.get("prior_event_digest") != prior:
            raise FaultToleranceError("fault event prior digest mismatch")
        payload = {
            "sequence": index,
            "event_type": event_type,
            "action": action,
            "details": dict(details),
            "prior_event_digest": prior,
        }
        observed = _sha("event_digest", raw.get("event_digest"))
        expected = sha256_bytes(canonical_json_bytes(payload))
        if observed != expected:
            raise FaultToleranceError("fault event digest mismatch")
        prior = observed
    assert prior is not None
    return prior


@dataclass(frozen=True, slots=True)
class VerifiedFaultCase:
    case_id: str
    fault_class: str
    injection_point: str
    terminal_action: str
    trace_sha256: str
    trace_audit_root_digest: str
    injection_evidence_sha256: str
    observed_cost_usd: float
    supported: bool
    record_digest: str


@dataclass(frozen=True, slots=True)
class FaultToleranceAuthority:
    family_id: str
    fault_spec_authority_digest: str
    execution_manifest_freeze_digest: str
    harness_freeze_digest: str
    dgc_policy_id: str
    frozen_max_cost_usd: float
    evidence_bundle_digest: str
    evidence_payload_manifest_sha256: str
    case_records: tuple[VerifiedFaultCase, ...]
    case_population_digest: str
    all_required_cases_supported: bool
    authority_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": AUTHORITY_SCHEMA,
            **asdict(self),
            "fault_tolerance_supported": self.all_required_cases_supported,
            "production_fault_tolerance_claim": False,
            "product_promotion_authorized": False,
        }


def build_fault_tolerance_authority(
    bundle_root: Path,
    *,
    repository_root: Path,
    fault_spec_authority_path: Path,
    execution_manifest_freeze_path: Path,
    harness_freeze_path: Path,
) -> FaultToleranceAuthority:
    repo = Path(repository_root).resolve()
    authority = verify_fault_injection_spec_authority_document(
        Path(fault_spec_authority_path), repository_root=repo
    )
    execution = verify_execution_manifest_freeze_document(Path(execution_manifest_freeze_path))
    harness = verify_harness_freeze_document(Path(harness_freeze_path))
    if authority.get("execution_manifest_freeze_digest") != execution.get("freeze_digest"):
        raise FaultToleranceError("fault spec belongs to a different execution freeze")
    if harness.get("execution_manifest_freeze_digest") != execution.get("freeze_digest"):
        raise FaultToleranceError("fault execution harness belongs to a different execution freeze")
    if harness.get("family_id") != authority.get("family_id"):
        raise FaultToleranceError("fault spec/harness family mismatch")
    if harness.get("generalization_registry_digest") != authority.get("generalization_registry_digest"):
        raise FaultToleranceError("fault spec/harness preregistration lineage mismatch")
    dgc_policy = _dgc_policy_id(harness)
    cap = _budget_cap(repo, execution)

    spec_path = repo / str(authority["fault_spec_path"])
    spec = load_fault_spec(spec_path)
    spec_cases = {str(row["case_id"]): row for row in spec["cases"]}

    supplied = Path(bundle_root)
    if supplied.is_symlink() or not supplied.is_dir():
        raise FaultToleranceError("fault tolerance bundle root must be a real directory")
    root = supplied.resolve()
    manifest = _json(root / "FAULT_TOLERANCE_BUNDLE.json", schema=BUNDLE_SCHEMA)
    if manifest.get("fault_spec_authority_digest") != authority.get("authority_digest"):
        raise FaultToleranceError("fault evidence bundle spec authority mismatch")
    if manifest.get("harness_freeze_digest") != harness.get("harness_freeze_digest"):
        raise FaultToleranceError("fault evidence bundle harness mismatch")
    if manifest.get("dgc_policy_id") != dgc_policy:
        raise FaultToleranceError("fault evidence bundle DGC policy mismatch")
    if manifest.get("product_promotion_authorized") is not False:
        raise FaultToleranceError("fault evidence bundle cannot authorize product promotion")

    payload_rows = file_manifest(root, excluded_names=frozenset({"FAULT_TOLERANCE_BUNDLE.json"}))
    payload_manifest_sha = sha256_bytes(canonical_json_bytes(payload_rows))
    if manifest.get("payload_manifest_sha256") != payload_manifest_sha:
        raise FaultToleranceError("fault evidence bundle payload manifest mismatch")

    rows = manifest.get("rows")
    if not isinstance(rows, list) or len(rows) != len(spec_cases):
        raise FaultToleranceError("fault evidence bundle requires exactly one row per frozen case")
    seen: set[str] = set()
    verified: list[VerifiedFaultCase] = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise FaultToleranceError("malformed fault evidence row")
        case_id = str(row.get("case_id", "")).strip()
        if case_id not in spec_cases or case_id in seen:
            raise FaultToleranceError("fault evidence contains duplicate/unknown case")
        seen.add(case_id)
        frozen = spec_cases[case_id]
        trace_path, trace_rel = _safe_file(root, row.get("trace_path"))
        injection_path, injection_rel = _safe_file(root, row.get("injection_evidence_path"))
        trace_sha = sha256_file(trace_path)
        injection_sha = sha256_file(injection_path)
        if row.get("trace_sha256") != trace_sha or row.get("injection_evidence_sha256") != injection_sha:
            raise FaultToleranceError("fault row evidence digest mismatch")
        trace = _json(trace_path, schema=TRACE_SCHEMA)
        if trace.get("case_id") != case_id:
            raise FaultToleranceError("fault trace case identity mismatch")
        if trace.get("fault_class") != frozen["fault_class"] or trace.get("injection_point") != frozen["injection_point"]:
            raise FaultToleranceError("fault trace semantics differ from preregistered case")
        if trace.get("policy_id") != dgc_policy or trace.get("fault_injected") is not True:
            raise FaultToleranceError("fault trace does not prove the frozen DGC arm was injected")
        if trace.get("injection_evidence_sha256") != injection_sha:
            raise FaultToleranceError("fault trace injection evidence binding mismatch")
        audit_root = _verify_event_chain(trace.get("events"))
        if trace.get("audit_root_digest") != audit_root:
            raise FaultToleranceError("fault trace audit root mismatch")
        terminal = str(trace.get("terminal_action", "")).strip()
        if terminal not in set(str(x) for x in frozen["expected_terminal_actions"]):
            raise FaultToleranceError("fault trace ended outside preregistered safe terminal actions")
        try:
            observed_cost = float(trace.get("observed_cost_usd"))
        except (TypeError, ValueError) as exc:
            raise FaultToleranceError("fault trace observed cost invalid") from exc
        if not math.isfinite(observed_cost) or observed_cost < 0.0 or observed_cost > cap + 1e-12:
            raise FaultToleranceError("fault trace violates frozen budget cap")
        count_fields = (
            "unauthorized_promotion_count", "budget_limit_bypass_count",
            "duplicate_side_effect_commit_count", "unverified_output_promotion_count",
        )
        if any(int(trace.get(field, -1)) != 0 for field in count_fields):
            raise FaultToleranceError("fault trace violates fail-closed safety invariant")
        record_payload = {
            "case_id": case_id,
            "fault_class": str(frozen["fault_class"]),
            "injection_point": str(frozen["injection_point"]),
            "terminal_action": terminal,
            "trace_path": trace_rel,
            "trace_sha256": trace_sha,
            "trace_audit_root_digest": audit_root,
            "injection_evidence_path": injection_rel,
            "injection_evidence_sha256": injection_sha,
            "observed_cost_usd": observed_cost,
            "supported": True,
        }
        verified.append(VerifiedFaultCase(
            case_id=case_id,
            fault_class=str(frozen["fault_class"]),
            injection_point=str(frozen["injection_point"]),
            terminal_action=terminal,
            trace_sha256=trace_sha,
            trace_audit_root_digest=audit_root,
            injection_evidence_sha256=injection_sha,
            observed_cost_usd=observed_cost,
            supported=True,
            record_digest=sha256_bytes(canonical_json_bytes(record_payload)),
        ))
    if seen != set(spec_cases):
        raise FaultToleranceError("fault evidence population is incomplete")

    ordered = tuple(sorted(verified, key=lambda item: item.case_id))
    case_population_digest = sha256_bytes(canonical_json_bytes([
        (row.case_id, row.record_digest) for row in ordered
    ]))
    manifest_payload = {
        "fault_spec_authority_digest": str(authority["authority_digest"]),
        "harness_freeze_digest": str(harness["harness_freeze_digest"]),
        "dgc_policy_id": dgc_policy,
        "payload_manifest_sha256": payload_manifest_sha,
        "rows": rows,
        "case_population_digest": case_population_digest,
        "product_promotion_authorized": False,
    }
    bundle_digest = sha256_bytes(canonical_json_bytes(manifest_payload))
    if manifest.get("case_population_digest") != case_population_digest:
        raise FaultToleranceError("fault evidence case population digest mismatch")
    if manifest.get("bundle_digest") != bundle_digest:
        raise FaultToleranceError("fault evidence bundle digest mismatch")

    payload = {
        "family_id": str(authority["family_id"]),
        "fault_spec_authority_digest": str(authority["authority_digest"]),
        "execution_manifest_freeze_digest": str(execution["freeze_digest"]),
        "harness_freeze_digest": str(harness["harness_freeze_digest"]),
        "dgc_policy_id": dgc_policy,
        "frozen_max_cost_usd": cap,
        "evidence_bundle_digest": bundle_digest,
        "evidence_payload_manifest_sha256": payload_manifest_sha,
        "case_records": [asdict(row) for row in ordered],
        "case_population_digest": case_population_digest,
        "all_required_cases_supported": True,
    }
    return FaultToleranceAuthority(
        family_id=payload["family_id"],
        fault_spec_authority_digest=payload["fault_spec_authority_digest"],
        execution_manifest_freeze_digest=payload["execution_manifest_freeze_digest"],
        harness_freeze_digest=payload["harness_freeze_digest"],
        dgc_policy_id=dgc_policy,
        frozen_max_cost_usd=cap,
        evidence_bundle_digest=bundle_digest,
        evidence_payload_manifest_sha256=payload_manifest_sha,
        case_records=ordered,
        case_population_digest=case_population_digest,
        all_required_cases_supported=True,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_fault_tolerance_authority_document(path: Path) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise FaultToleranceError("fault tolerance authority must be a regular file")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FaultToleranceError("invalid fault tolerance authority JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != AUTHORITY_SCHEMA:
        raise FaultToleranceError("unexpected fault tolerance authority schema")
    if doc.get("fault_tolerance_supported") is not True or doc.get("all_required_cases_supported") is not True:
        raise FaultToleranceError("fault tolerance support is incomplete")
    if doc.get("production_fault_tolerance_claim") is not False or doc.get("product_promotion_authorized") is not False:
        raise FaultToleranceError("fault tolerance claim boundary malformed")
    keys = (
        "family_id", "fault_spec_authority_digest", "execution_manifest_freeze_digest",
        "harness_freeze_digest", "dgc_policy_id", "frozen_max_cost_usd", "evidence_bundle_digest",
        "evidence_payload_manifest_sha256", "case_records", "case_population_digest",
        "all_required_cases_supported",
    )
    try:
        payload = {key: doc[key] for key in keys}
    except KeyError as exc:
        raise FaultToleranceError("fault tolerance authority payload incomplete") from exc
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("authority_digest", doc.get("authority_digest")):
        raise FaultToleranceError("fault tolerance authority digest mismatch")
    records = doc.get("case_records")
    if not isinstance(records, list) or len(records) != 12:
        raise FaultToleranceError("fault tolerance authority must contain exact preregistered case population")
    if any(not isinstance(row, Mapping) or row.get("supported") is not True for row in records):
        raise FaultToleranceError("fault tolerance authority contains unsupported case")
    return doc
