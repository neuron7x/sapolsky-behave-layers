from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Mapping, Sequence

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.p19_verification_check_receipt import (
    REQUIRED_CHECKS,
    P19VerificationCheckReceiptError,
    load_check_receipt,
)

ATTESTATION_SCHEMA = "DGC_P19_EXTERNAL_VERIFICATION_ATTESTATION_V2"
REPORT_SCHEMA = "DGC_P19_EXTERNAL_VERIFICATION_REPORT_V2"
NAMESPACE = "dgc-p19-external-verification-v2"
VERIFICATION_PROTOCOL = "DGC_P19_CANONICAL_EXTERNAL_REPLAY_V2_SELF_CONTAINED_TRANSCRIPT"
DECLARATION = (
    "I independently executed every required check in the disclosed canonical DGC P19 "
    "verification report and obtained PASS. The report identifies the raw receipt, stdout, "
    "stderr and evidence subjects for every check. This signature attests that verification "
    "execution; it does not replace the raw evidence or machine-prove the social fact of "
    "verifier independence."
)


class P19VerificationAttestationError(RuntimeError):
    pass


Runner = Callable[..., subprocess.CompletedProcess[bytes]]


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise P19VerificationAttestationError(f"{name} must be lowercase SHA-256")
    return text


def _oid(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 40 or any(ch not in "0123456789abcdef" for ch in text):
        raise P19VerificationAttestationError(f"{name} must be lowercase 40-hex Git object id")
    return text


def _safe_rel(value: object, *, label: str) -> str:
    text = str(value)
    if not text or text != text.strip() or any(ch in text for ch in ("\x00", "\n", "\r", "\t", "\\")) or "//" in text:
        raise P19VerificationAttestationError(f"{label} must be a canonical repository-relative POSIX path")
    rel = PurePosixPath(text)
    if rel.is_absolute() or any(part in ("", ".", "..") for part in rel.parts):
        raise P19VerificationAttestationError(f"{label} must be a canonical repository-relative POSIX path")
    return rel.as_posix()


def _discover_repository_root(path: Path) -> Path:
    candidate = Path(path).resolve().parent
    for root in (candidate, *candidate.parents):
        if (root / ".git").exists():
            return root.resolve()
    raise P19VerificationAttestationError("repository root required to replay P19 verification transcript")


def canonical_attestation_bytes(doc: Mapping[str, object]) -> bytes:
    return canonical_json_bytes(dict(doc)) + b"\n"


def canonical_report_bytes(doc: Mapping[str, object]) -> bytes:
    return canonical_json_bytes(dict(doc)) + b"\n"


@dataclass(frozen=True, slots=True)
class P19VerificationSignatureReceipt:
    attestation_sha256: str
    verification_report_sha256: str
    signature_sha256: str
    allowed_signers_sha256: str
    principal: str
    namespace: str
    ssh_keygen_path: str
    ssh_keygen_sha256: str
    stdout_sha256: str
    stderr_sha256: str
    signature_verified: bool

    @property
    def digest(self) -> str:
        return sha256_bytes(canonical_json_bytes(asdict(self)))


def _structural_report_row(raw_row: Mapping[str, object]) -> tuple[dict[str, object], dict[str, object]]:
    check_id = str(raw_row.get("check_id", "")).strip()
    if check_id not in REQUIRED_CHECKS:
        raise P19VerificationAttestationError("P19 verification report has unknown check")
    if raw_row.get("status") != "PASS":
        raise P19VerificationAttestationError(f"P19 external verification check did not PASS: {check_id}")
    argv = raw_row.get("command_argv")
    if not isinstance(argv, list) or not argv or any(not isinstance(item, str) or not item for item in argv):
        raise P19VerificationAttestationError(f"{check_id}.command_argv malformed")
    command_sha = _sha(f"{check_id}.command_sha256", raw_row.get("command_sha256"))
    if command_sha != sha256_bytes(canonical_json_bytes(argv)):
        raise P19VerificationAttestationError(f"{check_id}.command digest mismatch")

    row: dict[str, object] = {
        "check_id": check_id,
        "status": "PASS",
        "command_argv": list(argv),
        "command_sha256": command_sha,
    }
    transcript: dict[str, object] = {"check_id": check_id}
    for role, allow_empty in (("receipt", False), ("stdout", True), ("stderr", True), ("evidence", False)):
        rel = _safe_rel(raw_row.get(f"{role}_path"), label=f"{check_id}.{role}_path")
        digest = _sha(f"{check_id}.{role}_sha256", raw_row.get(f"{role}_sha256"))
        size = int(raw_row.get(f"{role}_bytes", -1))
        if size < 0 or (not allow_empty and size == 0):
            raise P19VerificationAttestationError(f"{check_id}.{role}_bytes invalid")
        row[f"{role}_path"] = rel
        row[f"{role}_sha256"] = digest
        row[f"{role}_bytes"] = size
        transcript[f"{role}_path"] = rel
        transcript[f"{role}_sha256"] = digest
        transcript[f"{role}_bytes"] = size
    row["evidence_digest"] = _sha(f"{check_id}.evidence_digest", raw_row.get("evidence_digest"))
    return row, transcript


def load_p19_verification_report(path: Path, *, repository_root: Path | None = None) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise P19VerificationAttestationError("P19 verification report must be a regular file")
    try:
        raw = candidate.read_bytes()
        doc = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise P19VerificationAttestationError("invalid P19 verification report JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != REPORT_SCHEMA:
        raise P19VerificationAttestationError("unexpected P19 verification report schema")
    if raw != canonical_report_bytes(doc):
        raise P19VerificationAttestationError("P19 verification report must use canonical JSON bytes")
    if doc.get("verification_protocol") != VERIFICATION_PROTOCOL:
        raise P19VerificationAttestationError("P19 verification report protocol mismatch")
    if doc.get("all_required_checks_passed") is not True:
        raise P19VerificationAttestationError("P19 verification report does not attest all required checks PASS")
    if doc.get("raw_verification_transcript_disclosed") is not True:
        raise P19VerificationAttestationError("P19 verification report omitted raw transcript disclosure")
    if doc.get("receipt_semantics_replayed") is not True:
        raise P19VerificationAttestationError("P19 verification report omitted receipt semantic replay")
    family = str(doc.get("family_id", "")).strip()
    if not family:
        raise P19VerificationAttestationError("P19 verification report family_id required")
    for field in (
        "p19_digest", "statistical_plan_digest", "theorem_identity_digest", "methodology_anchor_digest",
        "stage_evidence_manifest_digest", "subject_root_manifest_digest", "checks_digest",
        "raw_transcript_manifest_digest",
    ):
        _sha(field, doc.get(field))
    _oid("repository_commit", doc.get("repository_commit"))
    _oid("repository_tree", doc.get("repository_tree"))

    checks = doc.get("checks")
    if not isinstance(checks, list) or len(checks) != len(REQUIRED_CHECKS):
        raise P19VerificationAttestationError("P19 verification report check population incomplete")
    root = Path(repository_root).resolve() if repository_root is not None else None
    seen: set[str] = set()
    normalized: list[dict[str, object]] = []
    transcript_rows: list[dict[str, object]] = []
    for raw_row in checks:
        if not isinstance(raw_row, Mapping):
            raise P19VerificationAttestationError("P19 verification report check row malformed")
        row, transcript = _structural_report_row(raw_row)
        check_id = str(row["check_id"])
        if check_id in seen:
            raise P19VerificationAttestationError("P19 verification report has duplicate check")
        seen.add(check_id)

        if root is not None:
            receipt_rel = str(row["receipt_path"])
            try:
                verified_receipt = load_check_receipt(root / receipt_rel, repository_root=root)
            except P19VerificationCheckReceiptError as exc:
                raise P19VerificationAttestationError(
                    f"P19 verification receipt semantic replay failed: {check_id}: {exc}"
                ) from exc
            if verified_receipt.report_row != row:
                raise P19VerificationAttestationError(
                    f"P19 verification report/receipt semantic mismatch: {check_id}"
                )

        normalized.append(row)
        transcript_rows.append(transcript)
    if seen != REQUIRED_CHECKS:
        raise P19VerificationAttestationError("P19 verification report missing required check")

    normalized.sort(key=lambda row: str(row["check_id"]))
    transcript_rows.sort(key=lambda row: str(row["check_id"]))
    if doc.get("checks") != normalized:
        raise P19VerificationAttestationError("P19 verification report check ordering/content is not canonical")
    if doc.get("checks_digest") != sha256_bytes(canonical_json_bytes(normalized)):
        raise P19VerificationAttestationError("P19 verification report checks_digest mismatch")
    if doc.get("raw_transcript_manifest") != transcript_rows:
        raise P19VerificationAttestationError("P19 verification report raw transcript manifest mismatch")
    if doc.get("raw_transcript_manifest_digest") != sha256_bytes(canonical_json_bytes(transcript_rows)):
        raise P19VerificationAttestationError("P19 verification report raw transcript digest mismatch")
    return doc


def bind_report_to_p19(report: Mapping[str, object], p19: Mapping[str, object]) -> None:
    pairs = {
        "family_id": str(p19.get("family_id", "")),
        "p19_digest": str(p19.get("p19_digest", "")),
        "repository_commit": str(p19.get("repository_commit", "")),
        "repository_tree": str(p19.get("repository_tree", "")),
        "statistical_plan_digest": str(p19.get("statistical_plan_digest", "")),
        "theorem_identity_digest": str(p19.get("theorem_identity_digest", "")),
        "methodology_anchor_digest": str(p19.get("methodology_anchor_digest", "")),
        "stage_evidence_manifest_digest": str(p19.get("stage_evidence_manifest_digest", "")),
        "subject_root_manifest_digest": str(p19.get("subject_root_manifest_digest", "")),
    }
    for field, expected in pairs.items():
        if str(report.get(field, "")) != expected:
            raise P19VerificationAttestationError(f"P19 verification report mismatch: {field}")


def make_p19_verification_attestation(
    *,
    family_p19: Mapping[str, object],
    verifier_principal: str,
    verification_report_sha256: str,
) -> dict[str, object]:
    principal = str(verifier_principal).strip()
    if not principal or "\n" in principal or "\r" in principal:
        raise P19VerificationAttestationError("verifier_principal required")
    if family_p19.get("family_evidence_complete") is not True:
        raise P19VerificationAttestationError("cannot attest an incomplete family P19")
    return {
        "schema": ATTESTATION_SCHEMA,
        "verification_protocol": VERIFICATION_PROTOCOL,
        "family_id": str(family_p19.get("family_id", "")),
        "p19_digest": _sha("p19_digest", family_p19.get("p19_digest")),
        "repository_commit": _oid("repository_commit", family_p19.get("repository_commit")),
        "repository_tree": _oid("repository_tree", family_p19.get("repository_tree")),
        "statistical_plan_digest": _sha("statistical_plan_digest", family_p19.get("statistical_plan_digest")),
        "theorem_identity_digest": _sha("theorem_identity_digest", family_p19.get("theorem_identity_digest")),
        "methodology_anchor_digest": _sha("methodology_anchor_digest", family_p19.get("methodology_anchor_digest")),
        "stage_evidence_manifest_digest": _sha(
            "stage_evidence_manifest_digest", family_p19.get("stage_evidence_manifest_digest")
        ),
        "subject_root_manifest_digest": _sha(
            "subject_root_manifest_digest", family_p19.get("subject_root_manifest_digest")
        ),
        "verification_report_sha256": _sha("verification_report_sha256", verification_report_sha256),
        "semantic_replay_passed": True,
        "raw_evidence_disclosed": True,
        "raw_verification_transcript_disclosed": True,
        "receipt_semantics_replayed": True,
        "author_control_over_verification": False,
        "social_independence_machine_proven": False,
        "verifier_principal": principal,
        "declaration": DECLARATION,
    }


def load_p19_verification_attestation(path: Path) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise P19VerificationAttestationError("P19 verification attestation must be a regular file")
    try:
        raw = candidate.read_bytes()
        doc = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise P19VerificationAttestationError("invalid P19 verification attestation JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != ATTESTATION_SCHEMA:
        raise P19VerificationAttestationError("unexpected P19 verification attestation schema")
    if raw != canonical_attestation_bytes(doc):
        raise P19VerificationAttestationError("P19 verification attestation must use canonical JSON bytes")
    if doc.get("verification_protocol") != VERIFICATION_PROTOCOL or doc.get("declaration") != DECLARATION:
        raise P19VerificationAttestationError("P19 verification protocol/declaration mismatch")
    if (
        doc.get("semantic_replay_passed") is not True
        or doc.get("raw_evidence_disclosed") is not True
        or doc.get("raw_verification_transcript_disclosed") is not True
        or doc.get("receipt_semantics_replayed") is not True
    ):
        raise P19VerificationAttestationError("P19 verifier did not attest full semantic replay/raw transcript disclosure")
    if doc.get("author_control_over_verification") is not False:
        raise P19VerificationAttestationError("P19 verifier did not attest execution independence")
    if doc.get("social_independence_machine_proven") is not False:
        raise P19VerificationAttestationError("P19 attestation cannot claim machine-proven social independence")
    principal = str(doc.get("verifier_principal", "")).strip()
    family = str(doc.get("family_id", "")).strip()
    if not principal or "\n" in principal or "\r" in principal or not family:
        raise P19VerificationAttestationError("P19 verifier/family identity required")
    for field in (
        "p19_digest", "statistical_plan_digest", "theorem_identity_digest", "methodology_anchor_digest",
        "stage_evidence_manifest_digest", "subject_root_manifest_digest", "verification_report_sha256",
    ):
        _sha(field, doc.get(field))
    _oid("repository_commit", doc.get("repository_commit"))
    _oid("repository_tree", doc.get("repository_tree"))
    return doc


def _bind_report_to_attestation(report: Mapping[str, object], attestation: Mapping[str, object]) -> None:
    for field in (
        "family_id", "p19_digest", "repository_commit", "repository_tree", "statistical_plan_digest",
        "theorem_identity_digest", "methodology_anchor_digest", "stage_evidence_manifest_digest",
        "subject_root_manifest_digest", "verification_protocol", "receipt_semantics_replayed",
    ):
        if str(report.get(field, "")) != str(attestation.get(field, "")):
            raise P19VerificationAttestationError(f"verification report/attestation mismatch: {field}")


def verify_ssh_signed_p19_verification_attestation(
    *,
    attestation_path: Path,
    verification_report_path: Path,
    signature_path: Path,
    allowed_signers_path: Path,
    repository_root: Path | None = None,
    runner: Runner = subprocess.run,
    executable: str | None = None,
) -> tuple[dict[str, object], P19VerificationSignatureReceipt]:
    doc = load_p19_verification_attestation(Path(attestation_path))
    root = Path(repository_root).resolve() if repository_root is not None else _discover_repository_root(Path(verification_report_path))
    report_doc = load_p19_verification_report(Path(verification_report_path), repository_root=root)
    _bind_report_to_attestation(report_doc, doc)
    report = Path(verification_report_path)
    signature = Path(signature_path)
    allowed = Path(allowed_signers_path)
    for name, path in (("verification report", report), ("signature", signature), ("allowed signers", allowed)):
        if path.is_symlink() or not path.is_file() or path.stat().st_size <= 0:
            raise P19VerificationAttestationError(f"{name} must be a non-empty regular file")
    report_sha = sha256_file(report)
    if report_sha != doc.get("verification_report_sha256"):
        raise P19VerificationAttestationError("P19 verification report differs from signed attestation")

    ssh_keygen = executable or shutil.which("ssh-keygen")
    if not ssh_keygen:
        raise P19VerificationAttestationError("ssh-keygen unavailable for P19 signature verification")
    exe_path = Path(ssh_keygen).resolve()
    if not exe_path.is_file():
        raise P19VerificationAttestationError("ssh-keygen executable path invalid")
    principal = str(doc["verifier_principal"])
    argv: Sequence[str] = (
        str(exe_path), "-Y", "verify", "-f", str(allowed.resolve()),
        "-I", principal, "-n", NAMESPACE, "-s", str(signature.resolve()),
    )
    try:
        result = runner(
            list(argv),
            input=Path(attestation_path).read_bytes(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except (OSError, TypeError) as exc:
        raise P19VerificationAttestationError("P19 SSH signature verifier execution failed") from exc
    stdout = bytes(result.stdout or b"")
    stderr = bytes(result.stderr or b"")
    verified = int(result.returncode) == 0
    receipt = P19VerificationSignatureReceipt(
        attestation_sha256=sha256_file(Path(attestation_path)),
        verification_report_sha256=report_sha,
        signature_sha256=sha256_file(signature),
        allowed_signers_sha256=sha256_file(allowed),
        principal=principal,
        namespace=NAMESPACE,
        ssh_keygen_path=str(exe_path),
        ssh_keygen_sha256=sha256_file(exe_path),
        stdout_sha256=hashlib.sha256(stdout).hexdigest(),
        stderr_sha256=hashlib.sha256(stderr).hexdigest(),
        signature_verified=verified,
    )
    if not verified:
        raise P19VerificationAttestationError("P19 external verification SSH signature failed")
    return doc, receipt


def bind_attestation_to_p19(attestation: Mapping[str, object], p19: Mapping[str, object]) -> None:
    pairs = {
        "family_id": str(p19.get("family_id", "")),
        "p19_digest": str(p19.get("p19_digest", "")),
        "repository_commit": str(p19.get("repository_commit", "")),
        "repository_tree": str(p19.get("repository_tree", "")),
        "statistical_plan_digest": str(p19.get("statistical_plan_digest", "")),
        "theorem_identity_digest": str(p19.get("theorem_identity_digest", "")),
        "methodology_anchor_digest": str(p19.get("methodology_anchor_digest", "")),
        "stage_evidence_manifest_digest": str(p19.get("stage_evidence_manifest_digest", "")),
        "subject_root_manifest_digest": str(p19.get("subject_root_manifest_digest", "")),
    }
    for field, expected in pairs.items():
        if str(attestation.get(field, "")) != expected:
            raise P19VerificationAttestationError(f"P19 external verification attestation mismatch: {field}")
