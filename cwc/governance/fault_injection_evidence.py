from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file

SCHEMA = "DGC_FAULT_INJECTION_EVIDENCE_V2"


class FaultInjectionEvidenceError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise FaultInjectionEvidenceError(f"{name} must be lowercase SHA-256")
    return text


def _required_text(name: str, value: object) -> str:
    text = str(value).strip()
    if not text:
        raise FaultInjectionEvidenceError(f"{name} required")
    return text


def _finite(name: str, value: object, *, nonnegative: bool = False) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise FaultInjectionEvidenceError(f"{name} must be numeric") from exc
    if not math.isfinite(result) or (nonnegative and result < 0.0):
        raise FaultInjectionEvidenceError(f"{name} must be finite" + (" and >= 0" if nonnegative else ""))
    return result


def _safe_raw_artifact(root: Path, value: object) -> tuple[Path, str]:
    rel = Path(str(value))
    if not str(value) or rel.is_absolute() or ".." in rel.parts:
        raise FaultInjectionEvidenceError("raw_artifact_path must be relative and non-traversing")
    path = root / rel
    if path.is_symlink():
        raise FaultInjectionEvidenceError("raw fault artifact symlink rejected")
    resolved = path.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise FaultInjectionEvidenceError("raw fault artifact escapes evidence bundle") from exc
    if not resolved.is_file() or resolved.stat().st_size <= 0:
        raise FaultInjectionEvidenceError("raw fault artifact must be a non-empty regular file")
    return resolved, rel.as_posix()


def _verify_observations(fault_class: str, observations: Mapping[str, object]) -> None:
    if fault_class == "PROVIDER_TIMEOUT":
        _required_text("request_id", observations.get("request_id"))
        elapsed = _finite("elapsed_ms", observations.get("elapsed_ms"), nonnegative=True)
        budget = _finite("timeout_budget_ms", observations.get("timeout_budget_ms"), nonnegative=True)
        if budget <= 0.0 or elapsed + 1e-12 < budget or observations.get("outcome") != "TIMEOUT":
            raise FaultInjectionEvidenceError("provider timeout evidence does not cross frozen timeout boundary")
    elif fault_class == "PROVIDER_RATE_LIMIT":
        _required_text("request_id", observations.get("request_id"))
        if int(observations.get("http_status", 0)) != 429:
            raise FaultInjectionEvidenceError("provider rate-limit evidence requires HTTP 429")
    elif fault_class == "MALFORMED_MODEL_OUTPUT":
        _sha("payload_sha256", observations.get("payload_sha256"))
        if observations.get("parser_rejected") is not True:
            raise FaultInjectionEvidenceError("malformed output must be rejected by parser")
    elif fault_class == "TOOL_TIMEOUT":
        _required_text("process_id", observations.get("process_id"))
        timeout_ms = _finite("timeout_ms", observations.get("timeout_ms"), nonnegative=True)
        elapsed_ms = _finite("elapsed_ms", observations.get("elapsed_ms"), nonnegative=True)
        if timeout_ms <= 0.0 or elapsed_ms + 1e-12 < timeout_ms or observations.get("terminated") is not True:
            raise FaultInjectionEvidenceError("tool timeout evidence does not establish timeout termination")
    elif fault_class == "TOOL_NONZERO_EXIT":
        _required_text("process_id", observations.get("process_id"))
        if int(observations.get("exit_code", 0)) == 0:
            raise FaultInjectionEvidenceError("tool nonzero-exit evidence requires a nonzero exit code")
    elif fault_class == "SCORER_UNAVAILABLE":
        if observations.get("availability_probe_failed") is not True or observations.get("scoring_rejected") is not True:
            raise FaultInjectionEvidenceError("scorer-unavailable evidence requires failed probe and rejected scoring")
    elif fault_class == "BUDGET_EXHAUSTION":
        spent = _finite("spent_usd", observations.get("spent_usd"), nonnegative=True)
        limit = _finite("limit_usd", observations.get("limit_usd"), nonnegative=True)
        if spent + 1e-12 < limit or observations.get("new_admission_rejected") is not True:
            raise FaultInjectionEvidenceError("budget exhaustion evidence does not establish fail-closed admission")
    elif fault_class == "WORKER_CRASH_AFTER_LEASE":
        _required_text("lease_id", observations.get("lease_id"))
        if observations.get("worker_exit_observed") is not True or observations.get("lease_recovery_or_expiry_observed") is not True:
            raise FaultInjectionEvidenceError("worker-crash evidence requires observed exit and lease recovery/expiry")
    elif fault_class == "STALE_LEASE_REPLAY":
        _sha("lease_token_sha256", observations.get("lease_token_sha256"))
        if observations.get("stale_commit_rejected") is not True:
            raise FaultInjectionEvidenceError("stale-lease replay must be rejected")
    elif fault_class == "DUPLICATE_RESULT_COMMIT":
        _sha("result_digest", observations.get("result_digest"))
        if observations.get("first_commit_accepted") is not True or observations.get("duplicate_commit_rejected") is not True:
            raise FaultInjectionEvidenceError("duplicate-result evidence must establish accepted first commit and rejected duplicate")
    elif fault_class == "EVIDENCE_DIGEST_CORRUPTION":
        expected = _sha("expected_sha256", observations.get("expected_sha256"))
        observed = _sha("observed_sha256", observations.get("observed_sha256"))
        if expected == observed or observations.get("verification_rejected") is not True:
            raise FaultInjectionEvidenceError("digest-corruption evidence must show unequal digests and rejection")
    elif fault_class == "PARTIAL_EXECUTION_POPULATION":
        expected = int(observations.get("expected_units", -1))
        committed = int(observations.get("committed_units", -1))
        if expected <= 0 or committed < 0 or committed >= expected or observations.get("completion_rejected") is not True:
            raise FaultInjectionEvidenceError("partial-population evidence must show incomplete execution and rejected completion")
    else:
        raise FaultInjectionEvidenceError(f"unsupported fault class: {fault_class}")


@dataclass(frozen=True, slots=True)
class VerifiedFaultInjectionEvidence:
    case_id: str
    fault_class: str
    injection_point: str
    evidence_kind: str
    target_subject_digest: str
    pre_state_digest: str
    post_state_digest: str
    raw_artifact_path: str
    raw_artifact_sha256: str
    observations_digest: str
    evidence_digest: str


def verify_fault_injection_evidence(
    path: Path,
    *,
    bundle_root: Path,
    expected_case_id: str,
    expected_fault_class: str,
    expected_injection_point: str,
) -> VerifiedFaultInjectionEvidence:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise FaultInjectionEvidenceError("fault injection evidence must be a regular file")
    try:
        raw = candidate.read_bytes()
        doc = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FaultInjectionEvidenceError("invalid fault injection evidence JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise FaultInjectionEvidenceError("unexpected fault injection evidence schema")
    if doc.get("case_id") != expected_case_id or doc.get("fault_class") != expected_fault_class:
        raise FaultInjectionEvidenceError("fault injection evidence case/class mismatch")
    if doc.get("injection_point") != expected_injection_point:
        raise FaultInjectionEvidenceError("fault injection evidence point differs from preregistration")
    if doc.get("trigger_observed") is not True or doc.get("fault_injected") is not True:
        raise FaultInjectionEvidenceError("fault injection evidence does not establish observed trigger")
    if doc.get("product_promotion_authorized") is not False:
        raise FaultInjectionEvidenceError("fault injection receipt cannot authorize product promotion")

    evidence_kind = _required_text("evidence_kind", doc.get("evidence_kind"))
    target_subject_digest = _sha("target_subject_digest", doc.get("target_subject_digest"))
    pre_state_digest = _sha("pre_state_digest", doc.get("pre_state_digest"))
    post_state_digest = _sha("post_state_digest", doc.get("post_state_digest"))
    if pre_state_digest == post_state_digest:
        raise FaultInjectionEvidenceError("fault injection evidence requires an observed state transition")
    observations = doc.get("observations")
    if not isinstance(observations, Mapping):
        raise FaultInjectionEvidenceError("fault injection observations required")
    _verify_observations(expected_fault_class, observations)

    raw_path, raw_rel = _safe_raw_artifact(Path(bundle_root).resolve(), doc.get("raw_artifact_path"))
    raw_sha = sha256_file(raw_path)
    if doc.get("raw_artifact_sha256") != raw_sha:
        raise FaultInjectionEvidenceError("raw fault artifact digest mismatch")
    observations_digest = sha256_bytes(canonical_json_bytes(dict(observations)))
    if doc.get("observations_digest") != observations_digest:
        raise FaultInjectionEvidenceError("fault observation digest mismatch")

    payload = {
        "case_id": expected_case_id,
        "fault_class": expected_fault_class,
        "injection_point": expected_injection_point,
        "evidence_kind": evidence_kind,
        "target_subject_digest": target_subject_digest,
        "pre_state_digest": pre_state_digest,
        "post_state_digest": post_state_digest,
        "trigger_observed": True,
        "fault_injected": True,
        "raw_artifact_path": raw_rel,
        "raw_artifact_sha256": raw_sha,
        "observations": dict(observations),
        "observations_digest": observations_digest,
        "product_promotion_authorized": False,
    }
    evidence_digest = sha256_bytes(canonical_json_bytes(payload))
    if doc.get("evidence_digest") != evidence_digest:
        raise FaultInjectionEvidenceError("fault injection evidence digest mismatch")
    return VerifiedFaultInjectionEvidence(
        case_id=expected_case_id,
        fault_class=expected_fault_class,
        injection_point=expected_injection_point,
        evidence_kind=evidence_kind,
        target_subject_digest=target_subject_digest,
        pre_state_digest=pre_state_digest,
        post_state_digest=post_state_digest,
        raw_artifact_path=raw_rel,
        raw_artifact_sha256=raw_sha,
        observations_digest=observations_digest,
        evidence_digest=evidence_digest,
    )
