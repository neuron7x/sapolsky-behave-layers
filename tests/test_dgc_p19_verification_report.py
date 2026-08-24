from __future__ import annotations

from pathlib import Path

import pytest

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
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


def _receipt(root: Path, check_id: str, *, status: str = "PASS") -> Path:
    base = root / "artifacts/dgc-product-v1/generated/verifier" / check_id.lower()
    base.mkdir(parents=True, exist_ok=True)
    stdout = base / "stdout.bin"
    stderr = base / "stderr.bin"
    evidence = base / "evidence.json"
    stdout.write_bytes((check_id + ":stdout\n").encode())
    stderr.write_bytes(b"")
    evidence.write_bytes(("{\"check\":\"" + check_id + "\"}\n").encode())
    payload = {
        "check_id": check_id,
        "status": status,
        "command_argv": ["python", "-m", "dgc.external_verifier", check_id],
        "stdout_path": stdout.relative_to(root).as_posix(),
        "stdout_sha256": sha256_file(stdout),
        "stdout_bytes": stdout.stat().st_size,
        "stderr_path": stderr.relative_to(root).as_posix(),
        "stderr_sha256": sha256_file(stderr),
        "stderr_bytes": stderr.stat().st_size,
        "evidence_path": evidence.relative_to(root).as_posix(),
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


def _all_receipts(root: Path) -> tuple[Path, ...]:
    return tuple(_receipt(root, check) for check in sorted(REQUIRED_CHECKS))


def test_complete_receipt_population_builds_canonical_report(tmp_path: Path):
    report = build_p19_verification_report(
        repository_root=tmp_path,
        family_p19=_p19(),
        check_receipt_paths=_all_receipts(tmp_path),
    )
    assert {row["check_id"] for row in report["checks"]} == REQUIRED_CHECKS
    assert report["raw_verification_transcript_disclosed"] is True
    assert report["receipt_semantics_replayed"] is True
    assert report["all_required_checks_passed"] is True
    path = tmp_path / "report.json"
    path.write_bytes(report_bytes(report))
    loaded = load_p19_verification_report(path, repository_root=tmp_path)
    assert loaded == report


def test_duplicate_receipt_cannot_substitute_for_missing_check(tmp_path: Path):
    receipts = list(_all_receipts(tmp_path))
    receipts[-1] = receipts[0]
    with pytest.raises(P19VerificationReportError, match="incomplete/duplicated"):
        build_p19_verification_report(repository_root=tmp_path, family_p19=_p19(), check_receipt_paths=receipts)


def test_failed_check_prevents_report_construction(tmp_path: Path):
    receipts = list(_all_receipts(tmp_path))
    failed_id = sorted(REQUIRED_CHECKS)[0]
    receipts[0] = _receipt(tmp_path, failed_id, status="FAIL")
    with pytest.raises(P19VerificationReportError, match="did not PASS"):
        build_p19_verification_report(repository_root=tmp_path, family_p19=_p19(), check_receipt_paths=receipts)


def test_noncanonical_check_receipt_fails_closed(tmp_path: Path):
    receipts = list(_all_receipts(tmp_path))
    path = receipts[0]
    doc = __import__("json").loads(path.read_text(encoding="utf-8"))
    path.write_text(__import__("json").dumps(doc, indent=2, sort_keys=True), encoding="utf-8")
    with pytest.raises(P19VerificationReportError, match="canonical JSON bytes"):
        build_p19_verification_report(repository_root=tmp_path, family_p19=_p19(), check_receipt_paths=receipts)


def test_raw_transcript_mutation_fails_report_rehash(tmp_path: Path):
    report = build_p19_verification_report(
        repository_root=tmp_path,
        family_p19=_p19(),
        check_receipt_paths=_all_receipts(tmp_path),
    )
    path = tmp_path / "report.json"
    path.write_bytes(report_bytes(report))
    evidence_rel = str(report["checks"][0]["evidence_path"])
    (tmp_path / evidence_rel).write_bytes(b"mutated\n")
    with pytest.raises(Exception, match="bytes differ"):
        load_p19_verification_report(path, repository_root=tmp_path)


def test_self_consistent_report_cannot_contradict_bound_receipt_semantics(tmp_path: Path):
    report = build_p19_verification_report(
        repository_root=tmp_path,
        family_p19=_p19(),
        check_receipt_paths=_all_receipts(tmp_path),
    )
    row = report["checks"][0]
    row["command_argv"] = ["python", "forged_verifier.py", str(row["check_id"])]
    row["command_sha256"] = sha256_bytes(canonical_json_bytes(row["command_argv"]))
    report["checks_digest"] = sha256_bytes(canonical_json_bytes(report["checks"]))
    path = tmp_path / "forged-report.json"
    path.write_bytes(report_bytes(report))
    with pytest.raises(Exception, match="report/receipt semantic mismatch"):
        load_p19_verification_report(path, repository_root=tmp_path)


def test_incomplete_p19_cannot_receive_green_verification_report(tmp_path: Path):
    p19 = dict(_p19())
    p19["family_evidence_complete"] = False
    with pytest.raises(P19VerificationReportError, match="incomplete P19"):
        build_p19_verification_report(
            repository_root=tmp_path,
            family_p19=p19,
            check_receipt_paths=_all_receipts(tmp_path),
        )
