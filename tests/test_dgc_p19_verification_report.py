from __future__ import annotations

from pathlib import Path

import pytest

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes
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


def _receipt(path: Path, check_id: str, *, status: str = "PASS") -> Path:
    doc = {
        "schema": CHECK_RECEIPT_SCHEMA,
        "check_id": check_id,
        "status": status,
        "command_argv": ["python", "-m", "dgc.external_verifier", check_id],
        "stdout_sha256": _sha(check_id + ":stdout"),
        "stderr_sha256": _sha(check_id + ":stderr"),
        "evidence_digest": _sha(check_id + ":evidence"),
    }
    path.write_bytes(canonical_json_bytes(doc) + b"\n")
    return path


def _all_receipts(tmp_path: Path) -> tuple[Path, ...]:
    return tuple(_receipt(tmp_path / f"{check}.json", check) for check in sorted(REQUIRED_CHECKS))


def test_complete_receipt_population_builds_canonical_report(tmp_path: Path):
    report = build_p19_verification_report(
        family_p19=_p19(),
        check_receipt_paths=_all_receipts(tmp_path),
    )
    assert {row["check_id"] for row in report["checks"]} == REQUIRED_CHECKS
    assert report["all_required_checks_passed"] is True
    path = tmp_path / "report.json"
    path.write_bytes(report_bytes(report))
    loaded = load_p19_verification_report(path)
    assert loaded == report


def test_duplicate_receipt_cannot_substitute_for_missing_check(tmp_path: Path):
    receipts = list(_all_receipts(tmp_path))
    receipts[-1] = receipts[0]
    with pytest.raises(P19VerificationReportError, match="incomplete/duplicated"):
        build_p19_verification_report(family_p19=_p19(), check_receipt_paths=receipts)


def test_failed_check_prevents_report_construction(tmp_path: Path):
    receipts = list(_all_receipts(tmp_path))
    failed_id = sorted(REQUIRED_CHECKS)[0]
    receipts[0] = _receipt(tmp_path / "failed.json", failed_id, status="FAIL")
    with pytest.raises(P19VerificationReportError, match="did not PASS"):
        build_p19_verification_report(family_p19=_p19(), check_receipt_paths=receipts)


def test_noncanonical_check_receipt_fails_closed(tmp_path: Path):
    check_id = sorted(REQUIRED_CHECKS)[0]
    path = tmp_path / "pretty.json"
    path.write_text(
        '{\n  "schema": "DGC_P19_EXTERNAL_VERIFICATION_CHECK_RECEIPT_V1",\n  "check_id": "%s",\n  "status": "PASS",\n  "command_argv": ["x"],\n  "stdout_sha256": "%s",\n  "stderr_sha256": "%s",\n  "evidence_digest": "%s"\n}\n'
        % (check_id, "1" * 64, "2" * 64, "3" * 64),
        encoding="utf-8",
    )
    receipts = list(_all_receipts(tmp_path))
    receipts[0] = path
    with pytest.raises(P19VerificationReportError, match="canonical JSON bytes"):
        build_p19_verification_report(family_p19=_p19(), check_receipt_paths=receipts)


def test_incomplete_p19_cannot_receive_green_verification_report(tmp_path: Path):
    p19 = dict(_p19())
    p19["family_evidence_complete"] = False
    with pytest.raises(P19VerificationReportError, match="incomplete P19"):
        build_p19_verification_report(family_p19=p19, check_receipt_paths=_all_receipts(tmp_path))
