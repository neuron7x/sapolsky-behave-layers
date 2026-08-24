from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_file
from cwc.governance.p19_verification_attestation import (
    ATTESTATION_SCHEMA,
    DECLARATION,
    NAMESPACE,
    P19VerificationAttestationError,
    bind_attestation_to_p19,
    canonical_attestation_bytes,
    load_p19_verification_attestation,
    make_p19_verification_attestation,
    verify_ssh_signed_p19_verification_attestation,
)


def _p19() -> dict[str, object]:
    return {
        "family_id": "SWE_BENCH_VERIFIED",
        "p19_digest": "1" * 64,
        "repository_commit": "2" * 40,
        "repository_tree": "3" * 40,
        "statistical_plan_digest": "4" * 64,
        "theorem_identity_digest": "5" * 64,
        "methodology_anchor_digest": "6" * 64,
        "stage_evidence_manifest_digest": "7" * 64,
        "subject_root_manifest_digest": "8" * 64,
        "family_evidence_complete": True,
    }


def test_attestation_builder_is_canonical_and_bound_to_exact_p19(tmp_path: Path):
    report = tmp_path / "report.json"
    report.write_text('{"status":"PASS"}\n', encoding="utf-8")
    doc = make_p19_verification_attestation(
        family_p19=_p19(),
        verifier_principal="independent-verifier@example.org",
        verification_report_sha256=sha256_file(report),
    )
    assert doc["schema"] == ATTESTATION_SCHEMA
    assert doc["declaration"] == DECLARATION
    assert doc["semantic_replay_passed"] is True
    assert doc["author_control_over_verification"] is False
    assert doc["social_independence_machine_proven"] is False
    path = tmp_path / "attestation.json"
    path.write_bytes(canonical_attestation_bytes(doc))
    loaded = load_p19_verification_attestation(path)
    bind_attestation_to_p19(loaded, _p19())


def test_attestation_rejects_wrong_family_root_binding(tmp_path: Path):
    report = tmp_path / "report.json"
    report.write_text("PASS\n", encoding="utf-8")
    doc = make_p19_verification_attestation(
        family_p19=_p19(),
        verifier_principal="verifier",
        verification_report_sha256=sha256_file(report),
    )
    other = dict(_p19())
    other["p19_digest"] = "9" * 64
    with pytest.raises(P19VerificationAttestationError, match="p19_digest"):
        bind_attestation_to_p19(doc, other)


def test_noncanonical_attestation_bytes_fail_closed(tmp_path: Path):
    report = tmp_path / "report.json"
    report.write_text("PASS\n", encoding="utf-8")
    doc = make_p19_verification_attestation(
        family_p19=_p19(), verifier_principal="verifier", verification_report_sha256=sha256_file(report)
    )
    path = tmp_path / "attestation.json"
    path.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")
    with pytest.raises(P19VerificationAttestationError, match="canonical JSON bytes"):
        load_p19_verification_attestation(path)


def test_signed_verifier_binds_report_and_namespace(tmp_path: Path):
    report = tmp_path / "report.json"
    report.write_text('{"semantic_replay":"PASS"}\n', encoding="utf-8")
    doc = make_p19_verification_attestation(
        family_p19=_p19(), verifier_principal="verifier", verification_report_sha256=sha256_file(report)
    )
    attestation = tmp_path / "attestation.json"
    attestation.write_bytes(canonical_attestation_bytes(doc))
    signature = tmp_path / "attestation.sig"
    signature.write_bytes(b"signature")
    allowed = tmp_path / "allowed_signers"
    allowed.write_text("verifier ssh-ed25519 AAAATEST\n", encoding="utf-8")
    fake_keygen = tmp_path / "ssh-keygen"
    fake_keygen.write_bytes(b"fake verifier executable")

    observed: dict[str, object] = {}

    def runner(argv, *, input, stdout, stderr, check):
        observed["argv"] = list(argv)
        observed["input"] = input
        return subprocess.CompletedProcess(argv, 0, stdout=b"Good signature", stderr=b"")

    loaded, receipt = verify_ssh_signed_p19_verification_attestation(
        attestation_path=attestation,
        verification_report_path=report,
        signature_path=signature,
        allowed_signers_path=allowed,
        runner=runner,
        executable=str(fake_keygen),
    )
    assert loaded == doc
    assert receipt.signature_verified is True
    assert receipt.namespace == NAMESPACE
    assert receipt.verification_report_sha256 == sha256_file(report)
    assert observed["input"] == canonical_attestation_bytes(doc)
    assert NAMESPACE in observed["argv"]


def test_report_substitution_fails_before_signature_acceptance(tmp_path: Path):
    report = tmp_path / "report.json"
    report.write_text("PASS\n", encoding="utf-8")
    doc = make_p19_verification_attestation(
        family_p19=_p19(), verifier_principal="verifier", verification_report_sha256=sha256_file(report)
    )
    attestation = tmp_path / "attestation.json"
    attestation.write_bytes(canonical_attestation_bytes(doc))
    report.write_text("FAIL\n", encoding="utf-8")
    signature = tmp_path / "attestation.sig"
    signature.write_bytes(b"signature")
    allowed = tmp_path / "allowed_signers"
    allowed.write_text("verifier ssh-ed25519 AAAATEST\n", encoding="utf-8")
    fake_keygen = tmp_path / "ssh-keygen"
    fake_keygen.write_bytes(b"fake")

    with pytest.raises(P19VerificationAttestationError, match="report differs"):
        verify_ssh_signed_p19_verification_attestation(
            attestation_path=attestation,
            verification_report_path=report,
            signature_path=signature,
            allowed_signers_path=allowed,
            executable=str(fake_keygen),
        )
