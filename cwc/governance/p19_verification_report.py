from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import Mapping, Sequence

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes
from cwc.governance.p19_external_verification_plan import (
    CANONICAL_PLAN_PATH,
    P19ExternalVerificationPlanError,
    load_p19_external_verification_plan,
    verify_command_against_plan,
)
from cwc.governance.p19_verification_attestation import (
    REPORT_SCHEMA,
    VERIFICATION_PROTOCOL,
    bind_report_to_p19,
    canonical_report_bytes,
)
from cwc.governance.p19_verification_check_receipt import (
    REQUIRED_CHECKS,
    SCHEMA as CHECK_RECEIPT_SCHEMA,
    P19VerificationCheckReceiptError,
    load_check_receipt as load_verified_check_receipt,
)


class P19VerificationReportError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise P19VerificationReportError(f"{name} must be lowercase SHA-256")
    return text


def _repo_rel(root: Path, path: Path, *, label: str) -> str:
    source = Path(path)
    if not source.is_absolute():
        source = root / source
    if source.is_symlink() or not source.is_file() or source.stat().st_size <= 0:
        raise P19VerificationReportError(f"{label} must be a non-empty regular file")
    resolved = source.resolve()
    try:
        text = resolved.relative_to(root).as_posix()
    except ValueError as exc:
        raise P19VerificationReportError(f"{label} must be inside repository") from exc
    rel = PurePosixPath(text)
    if any(part in ("", ".", "..") for part in rel.parts):
        raise P19VerificationReportError(f"{label} path is not canonical")
    return rel.as_posix()


def load_check_receipt(path: Path, *, repository_root: Path) -> dict[str, object]:
    try:
        return load_verified_check_receipt(path, repository_root=repository_root).report_row
    except P19VerificationCheckReceiptError as exc:
        raise P19VerificationReportError(str(exc)) from exc


def build_p19_verification_report(
    *,
    repository_root: Path,
    family_p19: Mapping[str, object],
    family_p19_path: Path,
    check_receipt_paths: Sequence[Path],
    verification_plan_path: Path = Path(CANONICAL_PLAN_PATH),
) -> dict[str, object]:
    root = Path(repository_root).resolve()
    p19_rel = _repo_rel(root, family_p19_path, label="family P19")
    plan_rel = _repo_rel(root, verification_plan_path, label="external verification plan")
    try:
        plan = load_p19_external_verification_plan(
            root / plan_rel,
            repository_root=root,
            require_active=True,
        )
    except P19ExternalVerificationPlanError as exc:
        raise P19VerificationReportError("frozen external verification plan is not execution-ready") from exc

    rows = [load_check_receipt(Path(path), repository_root=root) for path in check_receipt_paths]
    if len(rows) != len(REQUIRED_CHECKS):
        raise P19VerificationReportError("P19 verification report requires exact receipt population")
    ids = [str(row["check_id"]) for row in rows]
    if set(ids) != REQUIRED_CHECKS or len(ids) != len(set(ids)):
        raise P19VerificationReportError("P19 verification receipt population is incomplete/duplicated")
    if family_p19.get("family_evidence_complete") is not True:
        raise P19VerificationReportError("cannot build verification report for incomplete P19")

    ordered = sorted(rows, key=lambda row: str(row["check_id"]))
    for row in ordered:
        try:
            verify_command_against_plan(
                plan,
                check_id=str(row["check_id"]),
                command_argv=row["command_argv"],
                p19_path=p19_rel,
                evidence_path=str(row["evidence_path"]),
            )
        except P19ExternalVerificationPlanError as exc:
            raise P19VerificationReportError(
                f"verification command differs from frozen plan: {row['check_id']}"
            ) from exc

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
        "verification_plan_path": plan_rel,
        "verification_plan_digest": plan.plan_digest,
        "verifier_entrypoint_path": plan.verifier_entrypoint_path,
        "verifier_entrypoint_sha256": plan.verifier_entrypoint_sha256,
        "p19_path": p19_rel,
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
        "receipt_semantics_replayed": True,
        "frozen_verification_plan_replayed": True,
        "all_required_checks_passed": True,
    }
    bind_report_to_p19(doc, family_p19)
    return doc


def report_bytes(report: Mapping[str, object]) -> bytes:
    return canonical_report_bytes(report)
