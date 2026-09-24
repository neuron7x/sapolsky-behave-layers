from __future__ import annotations

import json
from pathlib import Path

import pytest

from cwc.governance.fault_injection_evidence import (
    SCHEMA,
    FaultInjectionEvidenceError,
    verify_fault_injection_evidence,
)
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file


CASES = {
    "PROVIDER_TIMEOUT": {"request_id": "req-1", "elapsed_ms": 1001, "timeout_budget_ms": 1000, "outcome": "TIMEOUT"},
    "PROVIDER_RATE_LIMIT": {"request_id": "req-1", "http_status": 429},
    "MALFORMED_MODEL_OUTPUT": {"payload_sha256": "1" * 64, "parser_rejected": True},
    "TOOL_TIMEOUT": {"process_id": "p1", "timeout_ms": 500, "elapsed_ms": 501, "terminated": True},
    "TOOL_NONZERO_EXIT": {"process_id": "p1", "exit_code": 17},
    "SCORER_UNAVAILABLE": {"availability_probe_failed": True, "scoring_rejected": True},
    "BUDGET_EXHAUSTION": {"spent_usd": 1.0, "limit_usd": 1.0, "new_admission_rejected": True},
    "WORKER_CRASH_AFTER_LEASE": {"lease_id": "lease-1", "worker_exit_observed": True, "lease_recovery_or_expiry_observed": True},
    "STALE_LEASE_REPLAY": {"lease_token_sha256": "2" * 64, "stale_commit_rejected": True},
    "DUPLICATE_RESULT_COMMIT": {"result_digest": "3" * 64, "first_commit_accepted": True, "duplicate_commit_rejected": True},
    "EVIDENCE_DIGEST_CORRUPTION": {"expected_sha256": "4" * 64, "observed_sha256": "5" * 64, "verification_rejected": True},
    "PARTIAL_EXECUTION_POPULATION": {"expected_units": 10, "committed_units": 9, "completion_rejected": True},
}


def _write_subject(tmp_path: Path, fault_class: str, observations: dict[str, object]) -> Path:
    raw = tmp_path / "raw.bin"
    raw.write_bytes(b"physical/raw fault transcript\n")
    obs_digest = sha256_bytes(canonical_json_bytes(observations))
    payload = {
        "case_id": "case-1",
        "fault_class": fault_class,
        "injection_point": "POINT",
        "evidence_kind": "RAW_TRANSCRIPT",
        "target_subject_digest": "a" * 64,
        "pre_state_digest": "b" * 64,
        "post_state_digest": "c" * 64,
        "trigger_observed": True,
        "fault_injected": True,
        "raw_artifact_path": "raw.bin",
        "raw_artifact_sha256": sha256_file(raw),
        "observations": observations,
        "observations_digest": obs_digest,
        "product_promotion_authorized": False,
    }
    payload["evidence_digest"] = sha256_bytes(canonical_json_bytes(payload))
    doc = {"schema": SCHEMA, **payload}
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(doc, sort_keys=True), encoding="utf-8")
    return path


@pytest.mark.parametrize("fault_class", sorted(CASES))
def test_all_preregistered_fault_classes_have_machine_verifiable_positive_subjects(tmp_path: Path, fault_class: str):
    path = _write_subject(tmp_path, fault_class, dict(CASES[fault_class]))
    verified = verify_fault_injection_evidence(
        path,
        bundle_root=tmp_path,
        expected_case_id="case-1",
        expected_fault_class=fault_class,
        expected_injection_point="POINT",
    )
    assert verified.fault_class == fault_class
    assert verified.pre_state_digest != verified.post_state_digest
    assert verified.raw_artifact_sha256 == sha256_file(tmp_path / "raw.bin")


def test_provider_timeout_below_boundary_is_rejected(tmp_path: Path):
    observations = dict(CASES["PROVIDER_TIMEOUT"])
    observations["elapsed_ms"] = 999
    path = _write_subject(tmp_path, "PROVIDER_TIMEOUT", observations)
    with pytest.raises(FaultInjectionEvidenceError, match="timeout boundary"):
        verify_fault_injection_evidence(
            path, bundle_root=tmp_path, expected_case_id="case-1",
            expected_fault_class="PROVIDER_TIMEOUT", expected_injection_point="POINT"
        )


def test_digest_corruption_requires_actual_digest_difference(tmp_path: Path):
    observations = dict(CASES["EVIDENCE_DIGEST_CORRUPTION"])
    observations["observed_sha256"] = observations["expected_sha256"]
    path = _write_subject(tmp_path, "EVIDENCE_DIGEST_CORRUPTION", observations)
    with pytest.raises(FaultInjectionEvidenceError, match="unequal digests"):
        verify_fault_injection_evidence(
            path, bundle_root=tmp_path, expected_case_id="case-1",
            expected_fault_class="EVIDENCE_DIGEST_CORRUPTION", expected_injection_point="POINT"
        )


def test_partial_population_requires_rejected_incomplete_completion(tmp_path: Path):
    observations = dict(CASES["PARTIAL_EXECUTION_POPULATION"])
    observations["committed_units"] = observations["expected_units"]
    path = _write_subject(tmp_path, "PARTIAL_EXECUTION_POPULATION", observations)
    with pytest.raises(FaultInjectionEvidenceError, match="incomplete execution"):
        verify_fault_injection_evidence(
            path, bundle_root=tmp_path, expected_case_id="case-1",
            expected_fault_class="PARTIAL_EXECUTION_POPULATION", expected_injection_point="POINT"
        )


def test_state_transition_and_raw_artifact_are_not_decorative(tmp_path: Path):
    path = _write_subject(tmp_path, "PROVIDER_RATE_LIMIT", dict(CASES["PROVIDER_RATE_LIMIT"]))
    doc = json.loads(path.read_text())
    doc["post_state_digest"] = doc["pre_state_digest"]
    payload = dict(doc)
    payload.pop("schema")
    payload.pop("evidence_digest")
    payload["evidence_digest"] = sha256_bytes(canonical_json_bytes(payload))
    path.write_text(json.dumps({"schema": SCHEMA, **payload}, sort_keys=True))
    with pytest.raises(FaultInjectionEvidenceError, match="state transition"):
        verify_fault_injection_evidence(
            path, bundle_root=tmp_path, expected_case_id="case-1",
            expected_fault_class="PROVIDER_RATE_LIMIT", expected_injection_point="POINT"
        )

    path = _write_subject(tmp_path, "PROVIDER_RATE_LIMIT", dict(CASES["PROVIDER_RATE_LIMIT"]))
    (tmp_path / "raw.bin").write_bytes(b"tampered")
    with pytest.raises(FaultInjectionEvidenceError, match="raw fault artifact digest mismatch"):
        verify_fault_injection_evidence(
            path, bundle_root=tmp_path, expected_case_id="case-1",
            expected_fault_class="PROVIDER_RATE_LIMIT", expected_injection_point="POINT"
        )
