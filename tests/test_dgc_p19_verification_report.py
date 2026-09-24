from __future__ import annotations

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
    build_inactive_p19_external_verification_plan_document,
)
from cwc.governance.p19_external_verifier_regression import current_runtime_digest, current_test_manifest_digest
from cwc.governance.p19_verification_attestation import REQUIRED_CHECKS, load_p19_verification_report
from cwc.governance.p19_verification_report import (
    CHECK_RECEIPT_SCHEMA,
    P19VerificationReportError,
    build_p19_verification_report,
    report_bytes,
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


def _sha(label: str) -> str:
    return sha256_bytes(label.encode("utf-8"))


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


def _write(path: Path, doc: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(doc) + b"\n")


def _fake_activation_authority(root: Path, authority_path: Path) -> dict[str, object]:
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
    authority = _fake_activation_authority(root, authority_path)
    monkeypatch.setattr(
        plan_mod,
        "verify_p19_external_verifier_activation_authority_document",
        lambda *args, **kwargs: authority,
    )
    plan_doc = build_activated_p19_external_verification_plan_document(
        repository_root=root,
        activation_authority_path=authority_path.relative_to(root),
    )
    path = root / CANONICAL_PLAN_PATH
    _write(path, plan_doc)
    return path


def _inactive_plan(root: Path) -> Path:
    _runtime_and_tests(root)
    doc = build_inactive_p19_external_verification_plan_document(
        repository_root=root,
        implemented_check_ids=tuple(sorted(REQUIRED_CHECKS)),
    )
    path = root / CANONICAL_PLAN_PATH
    _write(path, doc)
    return path


def _p19_file(root: Path) -> Path:
    path = root / "artifacts/dgc-product-v1/generated/swe/p19.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(_p19()) + b"\n")
    return path


def _receipt(root: Path, p19_rel: str, check_id: str, *, status: str = "PASS", forged_command: bool = False) -> Path:
    base = root / "artifacts/dgc-product-v1/generated/verifier" / check_id.lower()
    base.mkdir(parents=True, exist_ok=True)
    stdout = base / "stdout.bin"
    stderr = base / "stderr.bin"
    evidence = base / "evidence.json"
    stdout.write_bytes((check_id + ":stdout\n").encode())
    stderr.write_bytes(b"")
    evidence.write_bytes(("{\"check\":\"" + check_id + "\"}\n").encode())
    evidence_rel = evidence.relative_to(root).as_posix()
    command = (
        ["echo", "PASS"]
        if forged_command
        else [
            "python", VERIFIER_ENTRYPOINT, "--check-id", check_id,
            "--p19", p19_rel, "--evidence-output", evidence_rel,
        ]
    )
    payload = {
        "check_id": check_id,
        "status": status,
        "command_argv": command,
        "stdout_path": stdout.relative_to(root).as_posix(),
        "stdout_sha256": sha256_file(stdout),
        "stdout_bytes": stdout.stat().st_size,
        "stderr_path": stderr.relative_to(root).as_posix(),
        "stderr_sha256": sha256_file(stderr),
        "stderr_bytes": stderr.stat().st_size,
        "evidence_path": evidence_rel,
        "evidence_sha256": sha256_file(evidence),
        "evidence_bytes": evidence.stat().st_size,
        "evidence_digest": _sha(check_id + ":semantic-evidence"),
    }
    doc = {
        "schema": CHECK_RECEIPT_SCHEMA,
        **payload,
        "receipt_digest": sha256_bytes(canonical_json_bytes(payload)),
    }
    path = base / "receipt.json"
    path.write_bytes(canonical_json_bytes(doc) + b"\n")
    return path


def _fixture(root: Path, monkeypatch):
    plan = _active_plan(root, monkeypatch)
    p19_path = _p19_file(root)
    p19_rel = p19_path.relative_to(root).as_posix()
    receipts = tuple(_receipt(root, p19_rel, check) for check in sorted(REQUIRED_CHECKS))
    return plan, p19_path, receipts


def _build(root: Path, monkeypatch) -> dict[str, object]:
    plan, p19_path, receipts = _fixture(root, monkeypatch)
    return build_p19_verification_report(
        repository_root=root,
        family_p19=_p19(),
        family_p19_path=p19_path,
        verification_plan_path=plan,
        check_receipt_paths=receipts,
    )


def test_complete_receipt_population_builds_plan_v4_dual_activation_report(tmp_path: Path, monkeypatch):
    report = _build(tmp_path, monkeypatch)
    assert {row["check_id"] for row in report["checks"]} == REQUIRED_CHECKS
    assert report["raw_verification_transcript_disclosed"] is True
    assert report["receipt_semantics_replayed"] is True
    assert report["frozen_verification_plan_replayed"] is True
    assert report["dual_signed_activation_authority_replayed"] is True
    assert report["verification_plan_activation_authority_digest"] == "a" * 64
    assert report["verification_plan_activation_verifier_principals"] == ["verifier-a", "verifier-b"]
    assert report["all_required_checks_passed"] is True
    path = tmp_path / "report.json"
    path.write_bytes(report_bytes(report))
    assert load_p19_verification_report(path, repository_root=tmp_path) == report


def test_echo_pass_command_cannot_satisfy_named_check(tmp_path: Path, monkeypatch):
    plan = _active_plan(tmp_path, monkeypatch)
    p19_path = _p19_file(tmp_path)
    p19_rel = p19_path.relative_to(tmp_path).as_posix()
    receipts = list(_receipt(tmp_path, p19_rel, check) for check in sorted(REQUIRED_CHECKS))
    forged_id = sorted(REQUIRED_CHECKS)[0]
    receipts[0] = _receipt(tmp_path, p19_rel, forged_id, forged_command=True)
    with pytest.raises(P19VerificationReportError, match="differs from frozen plan"):
        build_p19_verification_report(
            repository_root=tmp_path,
            family_p19=_p19(),
            family_p19_path=p19_path,
            verification_plan_path=plan,
            check_receipt_paths=receipts,
        )


def test_inactive_plan_prevents_report_authority(tmp_path: Path):
    plan = _inactive_plan(tmp_path)
    p19_path = _p19_file(tmp_path)
    p19_rel = p19_path.relative_to(tmp_path).as_posix()
    receipts = tuple(_receipt(tmp_path, p19_rel, check) for check in sorted(REQUIRED_CHECKS))
    with pytest.raises(P19VerificationReportError, match="not execution-ready"):
        build_p19_verification_report(
            repository_root=tmp_path,
            family_p19=_p19(),
            family_p19_path=p19_path,
            verification_plan_path=plan,
            check_receipt_paths=receipts,
        )


def test_raw_transcript_mutation_fails_report_rehash(tmp_path: Path, monkeypatch):
    report = _build(tmp_path, monkeypatch)
    path = tmp_path / "report.json"
    path.write_bytes(report_bytes(report))
    evidence_rel = str(report["checks"][0]["evidence_path"])
    (tmp_path / evidence_rel).write_bytes(b"mutated\n")
    with pytest.raises(Exception, match="bytes differ"):
        load_p19_verification_report(path, repository_root=tmp_path)


def test_verifier_dependency_mutation_fails_report_replay(tmp_path: Path, monkeypatch):
    report = _build(tmp_path, monkeypatch)
    path = tmp_path / "report.json"
    path.write_bytes(report_bytes(report))
    dependency = tmp_path / VERIFIER_RUNTIME_DEPENDENCIES[0]
    dependency.write_text("# mutated verifier dependency\n", encoding="utf-8")
    with pytest.raises(Exception, match="dependency bytes differ"):
        load_p19_verification_report(path, repository_root=tmp_path)


def test_activation_authority_mutation_fails_report_replay(tmp_path: Path, monkeypatch):
    report = _build(tmp_path, monkeypatch)
    path = tmp_path / "report.json"
    path.write_bytes(report_bytes(report))
    authority = tmp_path / str(report["verification_plan_activation_authority_path"])
    authority.write_bytes(b"mutated-activation-authority\n")
    with pytest.raises(Exception, match="plan replay failed"):
        load_p19_verification_report(path, repository_root=tmp_path)


def test_self_consistent_report_cannot_contradict_bound_receipt_semantics(tmp_path: Path, monkeypatch):
    report = _build(tmp_path, monkeypatch)
    row = report["checks"][0]
    row["command_argv"] = ["python", VERIFIER_ENTRYPOINT, "--check-id", str(row["check_id"]), "--p19", str(report["p19_path"]), "--evidence-output", "artifacts/dgc-product-v1/generated/forged.json"]
    row["command_sha256"] = sha256_bytes(canonical_json_bytes(row["command_argv"]))
    report["checks_digest"] = sha256_bytes(canonical_json_bytes(report["checks"]))
    path = tmp_path / "forged-report.json"
    path.write_bytes(report_bytes(report))
    with pytest.raises(Exception, match="report/receipt semantic mismatch"):
        load_p19_verification_report(path, repository_root=tmp_path)


def test_incomplete_p19_cannot_receive_green_verification_report(tmp_path: Path, monkeypatch):
    plan, p19_path, receipts = _fixture(tmp_path, monkeypatch)
    p19 = dict(_p19())
    p19["family_evidence_complete"] = False
    with pytest.raises(P19VerificationReportError, match="incomplete P19"):
        build_p19_verification_report(
            repository_root=tmp_path,
            family_p19=p19,
            family_p19_path=p19_path,
            verification_plan_path=plan,
            check_receipt_paths=receipts,
        )
