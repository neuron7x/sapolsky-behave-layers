from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.p19_verification_attestation import (
    ATTESTATION_SCHEMA,
    DECLARATION,
    NAMESPACE,
    REPORT_SCHEMA,
    REQUIRED_CHECKS,
    VERIFICATION_PROTOCOL,
    P19VerificationAttestationError,
    bind_attestation_to_p19,
    bind_report_to_p19,
    canonical_attestation_bytes,
    canonical_report_bytes,
    load_p19_verification_attestation,
    load_p19_verification_report,
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


def _digest(label: str) -> str:
    return sha256_bytes(label.encode("utf-8"))


def _report_doc(*, p19: dict[str, object] | None = None) -> dict[str, object]:
    family = dict(p19 or _p19())
    checks = [
        {
            "check_id": check_id,
            "status": "PASS",
            "command_sha256": _digest(f"{check_id}:command"),
            "stdout_sha256": _digest(f"{check_id}:stdout"),
            "stderr_sha256": _digest(f"{check_id}:stderr"),
            "evidence_digest": _digest(f"{check_id}:evidence"),
        }
        for check_id in sorted(REQUIRED_CHECKS)
    ]
    return {
        "schema": REPORT_SCHEMA,
        "verification_protocol": VERIFICATION_PROTOCOL,
        "family_id": family["family_id"],
        "p19_digest": family["p19_digest"],
        "repository_commit": family["repository_commit"],
        "repository_tree": family["repository_tree"],
        "statistical_plan_digest": family["statistical_plan_digest"],
        "theorem_identity_digest": family["theorem_identity_digest"],
        "methodology_anchor_digest": family["methodology_anchor_digest"],
        "stage_evidence_manifest_digest": family["stage_evidence_manifest_digest"],
        "subject_root_manifest_digest": family["subject_root_manifest_digest"],
        "checks": checks,
        "checks_digest": sha256_bytes(canonical_json_bytes(checks)),
        "all_required_checks_passed": True,
    }


def _write_report(path: Path, *, p19: dict[str, object] | None = None) -> dict[str, object]:
    doc = _report_doc(p19=p19)
    path.write_bytes(canonical_report_bytes(doc))
    return doc


def test_report_is_canonical_complete_and_bound_to_exact_p19(tmp_path: Path):
    path = tmp_path / "report.json"
    expected = _write_report(path)
    loaded = load_p19_verification_report(path)
    assert loaded == expected
    bind_report_to_p19(loaded, _p19())
    assert {row["check_id"] for row in loaded["checks"]} == REQUIRED_CHECKS
    assert loaded["all_required_checks_passed"] is True


def test_report_missing_required_check_fails_closed(tmp_path: Path):
    doc = _report_doc()
    doc["checks"] = list(doc["checks"][:-1])
    doc["checks_digest"] = sha256_bytes(canonical_json_bytes(doc["checks"]))
    path = tmp_path / "report.json"
    path.write_bytes(canonical_report_bytes(doc))
    with pytest.raises(P19VerificationAttestationError, match="population incomplete"):
        load_p19_verification_report(path)


def test_report_forged_checks_digest_fails_closed(tmp_path: Path):
    doc = _report_doc()
    doc["checks_digest"] = "f" * 64
    path = tmp_path / "report.json"
    path.write_bytes(canonical_report_bytes(doc))
    with pytest.raises(P19VerificationAttestationError, match="checks_digest mismatch"):
        load_p19_verification_report(path)


def test_report_wrong_p19_binding_fails_closed(tmp_path: Path):
    path = tmp_path / "report.json"
    loaded = _write_report(path)
    other = dict(_p19())
    other["p19_digest"] = "9" * 64
    with pytest.raises(P19VerificationAttestationError, match="p19_digest"):
        bind_report_to_p19(loaded, other)


def test_attestation_builder_is_canonical_and_bound_to_exact_p19(tmp_path: Path):
    report = tmp_path / "report.json"
    _write_report(report)
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
    _write_report(report)
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
    _write_report(report)
    doc = make_p19_verification_attestation(
        family_p19=_p19(), verifier_principal="verifier", verification_report_sha256=sha256_file(report)
    )
    path = tmp_path / "attestation.json"
    path.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")
    with pytest.raises(P19VerificationAttestationError, match="canonical JSON bytes"):
        load_p19_verification_attestation(path)


def test_signed_verifier_binds_report_and_namespace(tmp_path: Path):
    report = tmp_path / "report.json"
    _write_report(report)
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
    _write_report(report)
    doc = make_p19_verification_attestation(
        family_p19=_p19(), verifier_principal="verifier", verification_report_sha256=sha256_file(report)
    )
    attestation = tmp_path / "attestation.json"
    attestation.write_bytes(canonical_attestation_bytes(doc))
    mutated = _report_doc()
    mutated["checks"] = list(mutated["checks"])
    mutated["checks"][0] = dict(mutated["checks"][0])
    mutated["checks"][0]["evidence_digest"] = "a" * 64
    mutated["checks_digest"] = sha256_bytes(canonical_json_bytes(mutated["checks"]))
    report.write_bytes(canonical_report_bytes(mutated))
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
