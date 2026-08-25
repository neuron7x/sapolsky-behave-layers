from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

import cwc.governance.p19_external_verification_plan as plan_mod
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.p19_external_verification_contract import (
    REGRESSION_TEST_FILES,
    VERIFIER_ENTRYPOINT,
    VERIFIER_RUNTIME_DEPENDENCIES,
)
from cwc.governance.p19_external_verification_plan import (
    CANONICAL_PLAN_PATH,
    build_activated_p19_external_verification_plan_document,
)
from cwc.governance.p19_external_verifier_regression import current_runtime_digest, current_test_manifest_digest
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


def _write(path: Path, doc: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(doc) + b"\n")


def _runtime_and_tests(root: Path) -> None:
    entry = root / VERIFIER_ENTRYPOINT
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text("print('test verifier')\n", encoding="utf-8")
    for rel in VERIFIER_RUNTIME_DEPENDENCIES:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# frozen verifier dependency: {rel}\n", encoding="utf-8")
    for rel in REGRESSION_TEST_FILES:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# frozen regression test: {rel}\n", encoding="utf-8")


def _fake_activation_authority(root: Path) -> dict[str, object]:
    return {
        "schema": "DGC_P19_EXTERNAL_VERIFIER_ACTIVATION_AUTHORITY_V1",
        "activation_authorized": True,
        "all_signatures_verified": True,
        "authority_digest": "a" * 64,
        "trust_policy_path": "artifacts/dgc-product-v1/P19_VERIFIER_TRUST_POLICY_V2.json",
        "trust_policy_digest": "b" * 64,
        "verifier_principals": ["verifier-a", "verifier-b"],
        "signer_key_digests": ["c" * 64, "d" * 64],
        "regression_receipt_path": "artifacts/dgc-product-v1/generated/regression/receipt.json",
        "regression_receipt_sha256": "e" * 64,
        "regression_receipt_digest": "f" * 64,
        "source_commit": "1" * 40,
        "source_tree": "2" * 40,
        "runtime_manifest_digest": current_runtime_digest(root),
        "test_manifest_digest": current_test_manifest_digest(root),
        "method_map_digest": "3" * 64,
    }


def _active_plan(root: Path, monkeypatch) -> Path:
    _runtime_and_tests(root)
    authority_path = root / "artifacts/dgc-product-v1/generated/regression/activation-authority.json"
    authority_path.parent.mkdir(parents=True, exist_ok=True)
    authority_path.write_bytes(b"activation-authority\n")
    authority = _fake_activation_authority(root)
    monkeypatch.setattr(
        plan_mod,
        "verify_p19_external_verifier_activation_authority_document",
        lambda *args, **kwargs: authority,
    )
    plan = build_activated_p19_external_verification_plan_document(
        repository_root=root,
        activation_authority_path=authority_path.relative_to(root),
    )
    path = root / CANONICAL_PLAN_PATH
    _write(path, plan)
    return path


def _p19_file(root: Path) -> Path:
    path = root / "artifacts/dgc-product-v1/generated/swe/p19.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(_p19()) + b"\n")
    return path


def _receipt(root: Path, p19_rel: str, check_id: str) -> Path:
    base = root / "artifacts/dgc-product-v1/generated/verify" / check_id.lower()
    base.mkdir(parents=True, exist_ok=True)
    stdout = base / "stdout.bin"
    stderr = base / "stderr.bin"
    evidence = base / "evidence.json"
    stdout.write_bytes((check_id + " ok\n").encode())
    stderr.write_bytes(b"")
    evidence.write_bytes(("{\"check\":\"" + check_id + "\"}\n").encode())
    evidence_rel = evidence.relative_to(root).as_posix()
    payload = {
        "check_id": check_id,
        "status": "PASS",
        "command_argv": [
            "python", VERIFIER_ENTRYPOINT, "--check-id", check_id,
            "--p19", p19_rel, "--evidence-output", evidence_rel,
        ],
        "stdout_path": stdout.relative_to(root).as_posix(),
        "stdout_sha256": sha256_file(stdout),
        "stdout_bytes": stdout.stat().st_size,
        "stderr_path": stderr.relative_to(root).as_posix(),
        "stderr_sha256": sha256_file(stderr),
        "stderr_bytes": stderr.stat().st_size,
        "evidence_path": evidence_rel,
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


def _write_report(root: Path, path: Path, monkeypatch, *, p19: dict[str, object] | None = None) -> dict[str, object]:
    family = dict(p19 or _p19())
    plan = _active_plan(root, monkeypatch)
    p19_path = _p19_file(root)
    p19_rel = p19_path.relative_to(root).as_posix()
    report = build_p19_verification_report(
        repository_root=root,
        family_p19=family,
        family_p19_path=p19_path,
        verification_plan_path=plan,
        check_receipt_paths=tuple(_receipt(root, p19_rel, check) for check in sorted(REQUIRED_CHECKS)),
    )
    path.write_bytes(report_bytes(report))
    return report


def test_report_is_canonical_complete_planned_and_bound_to_exact_p19(tmp_path: Path, monkeypatch):
    path = tmp_path / "report.json"
    expected = _write_report(tmp_path, path, monkeypatch)
    loaded = load_p19_verification_report(path, repository_root=tmp_path)
    assert loaded == expected
    bind_report_to_p19(loaded, _p19())
    assert {row["check_id"] for row in loaded["checks"]} == REQUIRED_CHECKS
    assert loaded["raw_verification_transcript_disclosed"] is True
    assert loaded["receipt_semantics_replayed"] is True
    assert loaded["frozen_verification_plan_replayed"] is True
    assert loaded["dual_signed_activation_authority_replayed"] is True
    assert loaded["verification_plan_activation_authority_digest"] == "a" * 64


def test_report_wrong_p19_binding_fails_closed(tmp_path: Path, monkeypatch):
    path = tmp_path / "report.json"
    loaded = _write_report(tmp_path, path, monkeypatch)
    other = dict(_p19())
    other["p19_digest"] = "9" * 64
    with pytest.raises(P19VerificationAttestationError, match="p19_digest"):
        bind_report_to_p19(loaded, other)


def test_attestation_builder_remains_bound_to_exact_plan_v4_report(tmp_path: Path, monkeypatch):
    report = tmp_path / "report.json"
    _write_report(tmp_path, report, monkeypatch)
    doc = make_p19_verification_attestation(
        family_p19=_p19(),
        verifier_principal="independent-verifier@example.org",
        verification_report_sha256=sha256_file(report),
    )
    assert doc["schema"] == ATTESTATION_SCHEMA
    assert doc["declaration"] == DECLARATION
    assert doc["raw_verification_transcript_disclosed"] is True
    assert doc["receipt_semantics_replayed"] is True
    assert doc["frozen_verification_plan_executed"] is True
    assert doc["author_control_over_verification"] is False
    assert doc["social_independence_machine_proven"] is False
    path = tmp_path / "attestation.json"
    path.write_bytes(canonical_attestation_bytes(doc))
    loaded = load_p19_verification_attestation(path)
    bind_attestation_to_p19(loaded, _p19())


def test_noncanonical_attestation_bytes_fail_closed(tmp_path: Path, monkeypatch):
    report = tmp_path / "report.json"
    _write_report(tmp_path, report, monkeypatch)
    doc = make_p19_verification_attestation(
        family_p19=_p19(), verifier_principal="verifier", verification_report_sha256=sha256_file(report)
    )
    path = tmp_path / "attestation.json"
    path.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")
    with pytest.raises(P19VerificationAttestationError, match="canonical JSON bytes"):
        load_p19_verification_attestation(path)


def _signature_fixture(tmp_path: Path, monkeypatch):
    report = tmp_path / "report.json"
    report_doc = _write_report(tmp_path, report, monkeypatch)
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


def test_signed_verifier_binds_plan_v4_report_transcript_and_namespace(tmp_path: Path, monkeypatch):
    report, _, doc, attestation, signature, allowed, fake_keygen = _signature_fixture(tmp_path, monkeypatch)
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
    assert "FROZEN_CHECK_PLAN" in VERIFICATION_PROTOCOL


def test_raw_transcript_substitution_fails_before_signature_acceptance(tmp_path: Path, monkeypatch):
    report, report_doc, _, attestation, signature, allowed, fake_keygen = _signature_fixture(tmp_path, monkeypatch)
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


def test_frozen_plan_mutation_fails_before_signature_acceptance(tmp_path: Path, monkeypatch):
    report, report_doc, _, attestation, signature, allowed, fake_keygen = _signature_fixture(tmp_path, monkeypatch)
    plan_path = tmp_path / str(report_doc["verification_plan_path"])
    plan_path.write_bytes(plan_path.read_bytes() + b" ")
    called = False

    def runner(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("SSH verifier must not run after verification-plan tamper")

    with pytest.raises(P19VerificationAttestationError, match="plan replay failed"):
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


def test_verifier_dependency_mutation_fails_before_signature_acceptance(tmp_path: Path, monkeypatch):
    report, _, _, attestation, signature, allowed, fake_keygen = _signature_fixture(tmp_path, monkeypatch)
    dependency = tmp_path / VERIFIER_RUNTIME_DEPENDENCIES[0]
    dependency.write_text("# mutated verifier dependency\n", encoding="utf-8")
    called = False

    def runner(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("SSH verifier must not run after verifier-dependency tamper")

    with pytest.raises(P19VerificationAttestationError, match="plan replay failed"):
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


def test_activation_authority_mutation_fails_before_signature_acceptance(tmp_path: Path, monkeypatch):
    report, report_doc, _, attestation, signature, allowed, fake_keygen = _signature_fixture(tmp_path, monkeypatch)
    authority = tmp_path / str(report_doc["verification_plan_activation_authority_path"])
    authority.write_bytes(b"tampered activation authority\n")
    called = False

    def runner(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("P19 SSH verifier must not run after activation-authority tamper")

    with pytest.raises(P19VerificationAttestationError, match="plan replay failed"):
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
