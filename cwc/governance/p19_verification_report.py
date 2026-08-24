from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping, Sequence

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes
from cwc.governance.p19_verification_attestation import (
    REPORT_SCHEMA,
    REQUIRED_CHECKS,
    VERIFICATION_PROTOCOL,
    bind_report_to_p19,
    canonical_report_bytes,
)

CHECK_RECEIPT_SCHEMA = "DGC_P19_EXTERNAL_VERIFICATION_CHECK_RECEIPT_V1"


class P19VerificationReportError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise P19VerificationReportError(f"{name} must be lowercase SHA-256")
    return text


def _canonical_receipt_bytes(doc: Mapping[str, object]) -> bytes:
    return canonical_json_bytes(dict(doc)) + b"\n"


def load_check_receipt(path: Path) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise P19VerificationReportError("P19 verification check receipt must be a regular file")
    try:
        raw = candidate.read_bytes()
        doc = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise P19VerificationReportError("invalid P19 verification check receipt JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != CHECK_RECEIPT_SCHEMA:
        raise P19VerificationReportError("unexpected P19 verification check receipt schema")
    if raw != _canonical_receipt_bytes(doc):
        raise P19VerificationReportError("P19 verification check receipt must use canonical JSON bytes")
    check_id = str(doc.get("check_id", "")).strip()
    if check_id not in REQUIRED_CHECKS:
        raise P19VerificationReportError("unknown P19 verification check_id")
    if doc.get("status") != "PASS":
        raise P19VerificationReportError(f"P19 verification check did not PASS: {check_id}")
    argv = doc.get("command_argv")
    if not isinstance(argv, list) or not argv or any(not isinstance(x, str) or not x for x in argv):
        raise P19VerificationReportError("P19 verification check command_argv must be non-empty strings")
    return {
        "check_id": check_id,
        "status": "PASS",
        "command_sha256": sha256_bytes(canonical_json_bytes(argv)),
        "stdout_sha256": _sha("stdout_sha256", doc.get("stdout_sha256")),
        "stderr_sha256": _sha("stderr_sha256", doc.get("stderr_sha256")),
        "evidence_digest": _sha("evidence_digest", doc.get("evidence_digest")),
    }


def build_p19_verification_report(
    *,
    family_p19: Mapping[str, object],
    check_receipt_paths: Sequence[Path],
) -> dict[str, object]:
    rows = [load_check_receipt(Path(path)) for path in check_receipt_paths]
    if len(rows) != len(REQUIRED_CHECKS):
        raise P19VerificationReportError("P19 verification report requires exact receipt population")
    ids = [str(row["check_id"]) for row in rows]
    if set(ids) != REQUIRED_CHECKS or len(ids) != len(set(ids)):
        raise P19VerificationReportError("P19 verification receipt population is incomplete/duplicated")
    if family_p19.get("family_evidence_complete") is not True:
        raise P19VerificationReportError("cannot build verification report for incomplete P19")
    ordered = sorted(rows, key=lambda row: str(row["check_id"]))
    doc = {
        "schema": REPORT_SCHEMA,
        "verification_protocol": VERIFICATION_PROTOCOL,
        "family_id": str(family_p19.get("family_id", "")),
        "p19_digest": _sha("p19_digest", family_p19.get("p19_digest")),
        "repository_commit": str(family_p19.get("repository_commit", "")),
        "repository_tree": str(family_p19.get("repository_tree", "")),
        "statistical_plan_digest": _sha("statistical_plan_digest", family_p19.get("statistical_plan_digest")),
        "theorem_identity_digest": _sha("theorem_identity_digest", family_p19.get("theorem_identity_digest")),
        "methodology_anchor_digest": _sha("methodology_anchor_digest", family_p19.get("methodology_anchor_digest")),
        "stage_evidence_manifest_digest": _sha(
            "stage_evidence_manifest_digest", family_p19.get("stage_evidence_manifest_digest")
        ),
        "subject_root_manifest_digest": _sha(
            "subject_root_manifest_digest", family_p19.get("subject_root_manifest_digest")
        ),
        "checks": ordered,
        "checks_digest": sha256_bytes(canonical_json_bytes(ordered)),
        "all_required_checks_passed": True,
    }
    bind_report_to_p19(doc, family_p19)
    return doc


def report_bytes(report: Mapping[str, object]) -> bytes:
    return canonical_report_bytes(report)
