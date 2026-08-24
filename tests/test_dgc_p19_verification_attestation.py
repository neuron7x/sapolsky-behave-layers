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
    REQUIRED_CHECKS,
    VERIFICATION_PROTOCOL,
    P19VerificationAttestationError,
    bind_attestation_to_p19,
    bind_report_to_p19,
    canonical_attestation_bytes,
    load_p19_verification_attestation,
    load_p19_verification_report,
    make_p19_verification_attestation,
    verify_ssh_signed_p19_verification_attestation,
)
from cwc.governance.p19_verification_report import CHECK_RECEIPT_SCHEMA, build_p19_verification_report, report_bytes


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


def _receipt(root: Path, check_id: str) -> Path:
    base = root / "artifacts/dgc-product-v1/generated/verify" / check_id.lower()
    base.mkdir(parents=True, exist_ok=True)
    stdout = base / "stdout.bin"
    stderr = base / "stderr.bin"
    evidence = base / "evidence.json"
    stdout.write_bytes((check_id + " ok\n").encode())
    stderr.write_bytes(b"")
    evidence.write_bytes(("{\"check\":\"" + check_id + "\"}\n").encode())
    payload = {
        "check_id": check_id,
        "status": "PASS",
        "command_argv": ["python", "verify.py", check_id],
        "stdout_path": stdout.relative_to(root).as_posix(),
        "stdout_sha256": sha256_file(stdout),
        "stdout_bytes": stdout.stat().st_size,
        "stderr_path": stderr.relative_to(root).as_posix(),
        "stderr_sha256": sha256_file(stderr),
        "stderr_bytes": stderr.stat().st_size,
        "evidence_path": evidence.relative_to(root).as_posix(),
        "evidence_sha256": sha256_file(evidence),
        "evidence_bytes": evidence.stat().st_size,
        "evidence_digest": sha256_bytes((check_id + ":semantic").encode()),
    }
    doc = {
        "schema": CHECK_RECEIPT_SCHEMA,
        **payload,
        "receipt_digest": sha256_bytes(canonical_json_bytes(payload)),
    }
    path = base / "receipt.json"
    path.write_bytes(canonical_json_bytes(doc) + b"\n")
    return path


def _write_report(root: Path, path: Path, *, p19: dict[str, object] | None = None) -> dict[str, object]:
    family = dict(p19 or _p19())
    report = build_p19_verification_report(
        repository_root=root,
        family_p19=family,
        check_receipt_paths=tuple(_receipt(root, check) for check in sorted(REQUIRED_CHECKS)),
    )
    path.write_bytes(report_bytes(report))
    return report


def test_report_is_canonical_complete_and_bound_to_exact_p19(tmp_path: Path):
    path = tmp_path / "report.json"
    expected = _write_report(tmp_path, path)
    loaded = load_p19_verification_report(path, repository_root=tmp_path)
    assert loaded == expected
    bind_report_to_p19(loaded, _p19())
    assert {row["check_id"] for row in loaded["checks"]} == REQUIRED_CHECKS
    assert loaded["raw_verification_transcript_disclosed"] is True


def test_report_wrong_p19_binding_fails_closed(tmp_path: Path):
    path = tmp_path / "report.json"
    loaded = _write_report(tmp_path, path)
    other = dict(_p19())
    other["p19_digest"] = "9" * 64
    with pytest.raises(P19VerificationAttestationError, match="p19_digest"):
        bind_report_to_p19(loaded, other)


def test_attestation_builder_is_canonical_and_bound_to_exact_p19(tmp_path: Path):
    report = tmp_path / "report.json"
    _write_report(tmp_path, report)
    doc = make_p19_verification_attestation(
        family_p19=_p19(),
        verifier_principal="independent-verifier@example.org",
        verification_report_sha256=sha256_file(report),
    )
    assert doc["schema"] == ATTESTATION_SCHEMA
    assert doc["declaration"] == DECLARATION
    assert doc["raw_verification_transcript_disclosed"] is True
    assert doc["author_control_over_verification"] is False
    assert doc["social_independence_machine_proven"] is False
    path = tmp_path / "attestation.json"
    path.write_bytes(canonical_attestation_bytes(doc))
    loaded = load_p19_verification_attestation(path)
    bind_attestation_to_p19(loaded, _p19())


def test_noncanonical_attestation_bytes_fail_closed(tmp_path: Path):
    report = tmp_path / "report.json"
    _write_report(tmp_path, report)
    doc = make_p19_verification_attestation(
        family_p19=_p19(), verifier_principal="verifier", verification_report_sha256=sha256_file(report)
    )
    path = tmp_path / "attestation.json"
    path.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")
    with pytest.raises(P19VerificationAttestationError, match="canonical JSON bytes"):
        load_p19_verification_attestation(path)


def _signature_fixture(tmp_path: Path):
    report = tmp_path / "report.json"
    report_doc = _write_report(tmp_path, report)
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
    return report, report_doc, doc, attestation, signature, allowed, fake_keygen


def test_signed_verifier_binds_report_transcript_and_namespace(tmp_path: Path):
    report, _, doc, attestation, signature, allowed, fake_keygen = _signature_fixture(tmp_path)
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
        repository_root=tmp_path,
        runner=runner,
        executable=str(fake_keygen),
    )
    assert loaded == doc
    assert receipt.signature_verified is True
    assert receipt.namespace == NAMESPACE
    assert receipt.verification_report_sha256 == sha256_file(report)
    assert observed["input"] == canonical_attestation_bytes(doc)
    assert NAMESPACE in observed["argv"]
    assert VERIFICATION_PROTOCOL.startswith("DGC_P19_CANONICAL_EXTERNAL_REPLAY_V2")


def test_raw_transcript_substitution_fails_before_signature_acceptance(tmp_path: Path):
    report, report_doc, _, attestation, signature, allowed, fake_keygen = _signature_fixture(tmp_path)
    evidence_path = tmp_path / str(report_doc["checks"][0]["evidence_path"])
    evidence_path.write_bytes(b"tampered-after-report-signing\n")

    called = False

    def runner(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("SSH verifier must not run after transcript tamper")

    with pytest.raises(P19VerificationAttestationError, match="bytes differ"):
        verify_ssh_signed_p19_verification_attestation(
            attestation_path=attestation,
            verification_report_path=report,
            signature_path=signature,
            allowed_signers_path=allowed,
            repository_root=tmp_path,
            runner=runner,
            executable=str(fake_keygen),
        )
    assert called is False
