from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Mapping, Sequence

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.p19_verification_attestation import (
    REPORT_SCHEMA,
    REQUIRED_CHECKS,
    VERIFICATION_PROTOCOL,
    bind_report_to_p19,
    canonical_report_bytes,
)

CHECK_RECEIPT_SCHEMA = "DGC_P19_EXTERNAL_VERIFICATION_CHECK_RECEIPT_V2"


class P19VerificationReportError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise P19VerificationReportError(f"{name} must be lowercase SHA-256")
    return text


def _safe_rel(value: object, *, label: str) -> str:
    text = str(value)
    if not text or text != text.strip() or any(ch in text for ch in ("\x00", "\n", "\r", "\t", "\\")) or "//" in text:
        raise P19VerificationReportError(f"{label} must be a canonical repository-relative POSIX path")
    rel = PurePosixPath(text)
    if rel.is_absolute() or any(part in ("", ".", "..") for part in rel.parts):
        raise P19VerificationReportError(f"{label} must be a canonical repository-relative POSIX path")
    return rel.as_posix()


def _repo_file(root: Path, rel: str, *, label: str, allow_empty: bool) -> Path:
    path = root / rel
    if path.is_symlink():
        raise P19VerificationReportError(f"{label} symlink rejected")
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise P19VerificationReportError(f"{label} escapes repository") from exc
    if not resolved.is_file():
        raise P19VerificationReportError(f"{label} missing")
    if not allow_empty and resolved.stat().st_size <= 0:
        raise P19VerificationReportError(f"{label} must be non-empty")
    return resolved


def _canonical_receipt_bytes(doc: Mapping[str, object]) -> bytes:
    return canonical_json_bytes(dict(doc)) + b"\n"


def load_check_receipt(path: Path, *, repository_root: Path) -> dict[str, object]:
    root = Path(repository_root).resolve()
    candidate = Path(path).resolve()
    try:
        receipt_rel = candidate.relative_to(root).as_posix()
    except ValueError as exc:
        raise P19VerificationReportError("P19 verification check receipt must be inside repository") from exc
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

    payload_keys = (
        "check_id", "status", "command_argv",
        "stdout_path", "stdout_sha256", "stdout_bytes",
        "stderr_path", "stderr_sha256", "stderr_bytes",
        "evidence_path", "evidence_sha256", "evidence_bytes", "evidence_digest",
    )
    try:
        receipt_payload = {key: doc[key] for key in payload_keys}
    except KeyError as exc:
        raise P19VerificationReportError("P19 verification check receipt payload incomplete") from exc
    if sha256_bytes(canonical_json_bytes(receipt_payload)) != _sha("receipt_digest", doc.get("receipt_digest")):
        raise P19VerificationReportError("P19 verification check receipt digest mismatch")

    subjects: dict[str, tuple[str, str, int]] = {}
    for role, allow_empty in (("stdout", True), ("stderr", True), ("evidence", False)):
        rel = _safe_rel(doc.get(f"{role}_path"), label=f"{check_id}.{role}_path")
        subject = _repo_file(root, rel, label=f"{check_id}.{role}", allow_empty=allow_empty)
        digest = _sha(f"{check_id}.{role}_sha256", doc.get(f"{role}_sha256"))
        size = int(doc.get(f"{role}_bytes", -1))
        if size < 0 or subject.stat().st_size != size:
            raise P19VerificationReportError(f"{check_id}.{role} byte count mismatch")
        if sha256_file(subject) != digest:
            raise P19VerificationReportError(f"{check_id}.{role} bytes differ from receipt")
        subjects[role] = (rel, digest, size)

    stdout_rel, stdout_sha, stdout_bytes = subjects["stdout"]
    stderr_rel, stderr_sha, stderr_bytes = subjects["stderr"]
    evidence_rel, evidence_sha, evidence_bytes = subjects["evidence"]
    return {
        "check_id": check_id,
        "status": "PASS",
        "command_argv": list(argv),
        "command_sha256": sha256_bytes(canonical_json_bytes(argv)),
        "receipt_path": _safe_rel(receipt_rel, label=f"{check_id}.receipt_path"),
        "receipt_sha256": sha256_file(candidate),
        "receipt_bytes": candidate.stat().st_size,
        "stdout_path": stdout_rel,
        "stdout_sha256": stdout_sha,
        "stdout_bytes": stdout_bytes,
        "stderr_path": stderr_rel,
        "stderr_sha256": stderr_sha,
        "stderr_bytes": stderr_bytes,
        "evidence_path": evidence_rel,
        "evidence_sha256": evidence_sha,
        "evidence_bytes": evidence_bytes,
        "evidence_digest": _sha("evidence_digest", doc.get("evidence_digest")),
    }


def build_p19_verification_report(
    *,
    repository_root: Path,
    family_p19: Mapping[str, object],
    check_receipt_paths: Sequence[Path],
) -> dict[str, object]:
    root = Path(repository_root).resolve()
    rows = [load_check_receipt(Path(path), repository_root=root) for path in check_receipt_paths]
    if len(rows) != len(REQUIRED_CHECKS):
        raise P19VerificationReportError("P19 verification report requires exact receipt population")
    ids = [str(row["check_id"]) for row in rows]
    if set(ids) != REQUIRED_CHECKS or len(ids) != len(set(ids)):
        raise P19VerificationReportError("P19 verification receipt population is incomplete/duplicated")
    if family_p19.get("family_evidence_complete") is not True:
        raise P19VerificationReportError("cannot build verification report for incomplete P19")
    ordered = sorted(rows, key=lambda row: str(row["check_id"]))
    transcript_rows = [
        {
            "check_id": row["check_id"],
            "receipt_path": row["receipt_path"],
            "receipt_sha256": row["receipt_sha256"],
            "receipt_bytes": row["receipt_bytes"],
            "stdout_path": row["stdout_path"],
            "stdout_sha256": row["stdout_sha256"],
            "stdout_bytes": row["stdout_bytes"],
            "stderr_path": row["stderr_path"],
            "stderr_sha256": row["stderr_sha256"],
            "stderr_bytes": row["stderr_bytes"],
            "evidence_path": row["evidence_path"],
            "evidence_sha256": row["evidence_sha256"],
            "evidence_bytes": row["evidence_bytes"],
        }
        for row in ordered
    ]
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
        "raw_transcript_manifest": transcript_rows,
        "raw_transcript_manifest_digest": sha256_bytes(canonical_json_bytes(transcript_rows)),
        "raw_verification_transcript_disclosed": True,
        "all_required_checks_passed": True,
    }
    bind_report_to_p19(doc, family_p19)
    return doc


def report_bytes(report: Mapping[str, object]) -> bytes:
    return canonical_report_bytes(report)
