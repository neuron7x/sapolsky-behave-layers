from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping, Sequence

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file

SCHEMA = "DGC_P19_EXTERNAL_VERIFICATION_CHECK_RECEIPT_V2"
REQUIRED_CHECKS = frozenset({
    "REPOSITORY_IDENTITY",
    "THEOREM_AND_PLAN_IDENTITY",
    "SUBJECT_ROOT_REHASH",
    "P19_SEAL_REBUILD",
    "PRIMARY_P9_RAW_REPLAY",
    "GENERALIZATION_G1_G5_RAW_REPLAY",
    "FAULT_TOLERANCE_RAW_REPLAY",
    "INDEPENDENT_REPLICATION_RAW_REPLAY",
})


class P19VerificationCheckReceiptError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise P19VerificationCheckReceiptError(f"{name} must be lowercase SHA-256")
    return text


def _safe_rel(value: object, *, label: str) -> str:
    text = str(value)
    if not text or text != text.strip() or any(ch in text for ch in ("\x00", "\n", "\r", "\t", "\\")) or "//" in text:
        raise P19VerificationCheckReceiptError(f"{label} must be a canonical repository-relative POSIX path")
    rel = PurePosixPath(text)
    if rel.is_absolute() or any(part in ("", ".", "..") for part in rel.parts):
        raise P19VerificationCheckReceiptError(f"{label} must be a canonical repository-relative POSIX path")
    return rel.as_posix()


def _repo_file(root: Path, rel: str, *, label: str, allow_empty: bool) -> Path:
    source = root / rel
    if source.is_symlink():
        raise P19VerificationCheckReceiptError(f"{label} symlink rejected")
    resolved = source.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise P19VerificationCheckReceiptError(f"{label} escapes repository") from exc
    if not resolved.is_file():
        raise P19VerificationCheckReceiptError(f"{label} missing")
    if not allow_empty and resolved.stat().st_size <= 0:
        raise P19VerificationCheckReceiptError(f"{label} must be non-empty")
    return resolved


@dataclass(frozen=True, slots=True)
class VerifiedP19CheckReceipt:
    check_id: str
    status: str
    command_argv: tuple[str, ...]
    command_sha256: str
    receipt_path: str
    receipt_sha256: str
    receipt_bytes: int
    stdout_path: str
    stdout_sha256: str
    stdout_bytes: int
    stderr_path: str
    stderr_sha256: str
    stderr_bytes: int
    evidence_path: str
    evidence_sha256: str
    evidence_bytes: int
    evidence_digest: str

    @property
    def report_row(self) -> dict[str, object]:
        data = asdict(self)
        data["command_argv"] = list(self.command_argv)
        return data


def canonical_receipt_bytes(doc: Mapping[str, object]) -> bytes:
    return canonical_json_bytes(dict(doc)) + b"\n"


def build_check_receipt_document(
    *,
    repository_root: Path,
    check_id: str,
    command_argv: Sequence[str],
    stdout_path: str,
    stderr_path: str,
    evidence_path: str,
    evidence_digest: str,
) -> dict[str, object]:
    root = Path(repository_root).resolve()
    check = str(check_id).strip()
    if check not in REQUIRED_CHECKS:
        raise P19VerificationCheckReceiptError("unknown P19 verification check_id")
    argv = tuple(command_argv)
    if not argv or any(not isinstance(item, str) or not item for item in argv):
        raise P19VerificationCheckReceiptError("verification command argv must be non-empty strings")

    subjects: dict[str, tuple[str, Path]] = {}
    for role, value, allow_empty in (
        ("stdout", stdout_path, True),
        ("stderr", stderr_path, True),
        ("evidence", evidence_path, False),
    ):
        rel = _safe_rel(value, label=f"{check}.{role}_path")
        subjects[role] = (rel, _repo_file(root, rel, label=f"{check}.{role}", allow_empty=allow_empty))

    payload = {
        "check_id": check,
        "status": "PASS",
        "command_argv": list(argv),
        "stdout_path": subjects["stdout"][0],
        "stdout_sha256": sha256_file(subjects["stdout"][1]),
        "stdout_bytes": subjects["stdout"][1].stat().st_size,
        "stderr_path": subjects["stderr"][0],
        "stderr_sha256": sha256_file(subjects["stderr"][1]),
        "stderr_bytes": subjects["stderr"][1].stat().st_size,
        "evidence_path": subjects["evidence"][0],
        "evidence_sha256": sha256_file(subjects["evidence"][1]),
        "evidence_bytes": subjects["evidence"][1].stat().st_size,
        "evidence_digest": _sha("evidence_digest", evidence_digest),
    }
    return {"schema": SCHEMA, **payload, "receipt_digest": sha256_bytes(canonical_json_bytes(payload))}


def load_check_receipt(path: Path, *, repository_root: Path) -> VerifiedP19CheckReceipt:
    root = Path(repository_root).resolve()
    source = Path(path)
    if not source.is_absolute():
        source = root / source
    if source.is_symlink() or not source.is_file():
        raise P19VerificationCheckReceiptError("P19 verification check receipt must be a regular non-symlink file")
    candidate = source.resolve()
    try:
        receipt_rel = candidate.relative_to(root).as_posix()
    except ValueError as exc:
        raise P19VerificationCheckReceiptError("P19 verification check receipt must be inside repository") from exc
    try:
        raw = candidate.read_bytes()
        doc = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise P19VerificationCheckReceiptError("invalid P19 verification check receipt JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise P19VerificationCheckReceiptError("unexpected P19 verification check receipt schema")
    if raw != canonical_receipt_bytes(doc):
        raise P19VerificationCheckReceiptError("P19 verification check receipt must use canonical JSON bytes")

    check = str(doc.get("check_id", "")).strip()
    if check not in REQUIRED_CHECKS:
        raise P19VerificationCheckReceiptError("unknown P19 verification check_id")
    if doc.get("status") != "PASS":
        raise P19VerificationCheckReceiptError(f"P19 verification check did not PASS: {check}")
    argv_obj = doc.get("command_argv")
    if not isinstance(argv_obj, list) or not argv_obj or any(not isinstance(item, str) or not item for item in argv_obj):
        raise P19VerificationCheckReceiptError("P19 verification check command_argv must be non-empty strings")
    argv = tuple(argv_obj)

    payload_keys = (
        "check_id", "status", "command_argv",
        "stdout_path", "stdout_sha256", "stdout_bytes",
        "stderr_path", "stderr_sha256", "stderr_bytes",
        "evidence_path", "evidence_sha256", "evidence_bytes", "evidence_digest",
    )
    try:
        payload = {key: doc[key] for key in payload_keys}
    except KeyError as exc:
        raise P19VerificationCheckReceiptError("P19 verification check receipt payload incomplete") from exc
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("receipt_digest", doc.get("receipt_digest")):
        raise P19VerificationCheckReceiptError("P19 verification check receipt digest mismatch")

    verified: dict[str, tuple[str, str, int]] = {}
    for role, allow_empty in (("stdout", True), ("stderr", True), ("evidence", False)):
        rel = _safe_rel(doc.get(f"{role}_path"), label=f"{check}.{role}_path")
        subject = _repo_file(root, rel, label=f"{check}.{role}", allow_empty=allow_empty)
        digest = _sha(f"{check}.{role}_sha256", doc.get(f"{role}_sha256"))
        size = int(doc.get(f"{role}_bytes", -1))
        if size < 0 or subject.stat().st_size != size:
            raise P19VerificationCheckReceiptError(f"{check}.{role} byte count mismatch")
        if sha256_file(subject) != digest:
            raise P19VerificationCheckReceiptError(f"{check}.{role} bytes differ from receipt")
        verified[role] = (rel, digest, size)

    return VerifiedP19CheckReceipt(
        check_id=check,
        status="PASS",
        command_argv=argv,
        command_sha256=sha256_bytes(canonical_json_bytes(list(argv))),
        receipt_path=_safe_rel(receipt_rel, label=f"{check}.receipt_path"),
        receipt_sha256=sha256_file(candidate),
        receipt_bytes=candidate.stat().st_size,
        stdout_path=verified["stdout"][0],
        stdout_sha256=verified["stdout"][1],
        stdout_bytes=verified["stdout"][2],
        stderr_path=verified["stderr"][0],
        stderr_sha256=verified["stderr"][1],
        stderr_bytes=verified["stderr"][2],
        evidence_path=verified["evidence"][0],
        evidence_sha256=verified["evidence"][1],
        evidence_bytes=verified["evidence"][2],
        evidence_digest=_sha("evidence_digest", doc.get("evidence_digest")),
    )
