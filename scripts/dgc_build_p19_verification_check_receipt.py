from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.p19_verification_attestation import REQUIRED_CHECKS
from cwc.governance.p19_verification_report import CHECK_RECEIPT_SCHEMA


def _safe_subject(root: Path, value: str, *, label: str, allow_empty: bool) -> tuple[str, Path]:
    raw = str(value)
    if not raw or raw != raw.strip() or any(ch in raw for ch in ("\x00", "\n", "\r", "\t", "\\")) or "//" in raw:
        raise ValueError(f"{label} must be a canonical repository-relative POSIX path")
    rel = PurePosixPath(raw)
    if rel.is_absolute() or any(part in ("", ".", "..") for part in rel.parts):
        raise ValueError(f"{label} must be a canonical repository-relative POSIX path")
    path = (root / rel.as_posix()).resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} escapes repository") from exc
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{label} must be a regular file")
    if not allow_empty and path.stat().st_size <= 0:
        raise ValueError(f"{label} must be non-empty")
    return rel.as_posix(), path


def _sha(value: str) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise ValueError("evidence-digest must be lowercase SHA-256")
    return text


def _write_immutable(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Build one canonical P19 external verification check receipt V2.")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check-id", choices=sorted(REQUIRED_CHECKS), required=True)
    parser.add_argument("--stdout-path", required=True)
    parser.add_argument("--stderr-path", required=True)
    parser.add_argument("--evidence-path", required=True)
    parser.add_argument("--evidence-digest", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    root = args.root.resolve()
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command or any(not item for item in command):
        raise ValueError("verification command argv is required after --")

    stdout_rel, stdout = _safe_subject(root, args.stdout_path, label="stdout-path", allow_empty=True)
    stderr_rel, stderr = _safe_subject(root, args.stderr_path, label="stderr-path", allow_empty=True)
    evidence_rel, evidence = _safe_subject(root, args.evidence_path, label="evidence-path", allow_empty=False)
    payload = {
        "check_id": args.check_id,
        "status": "PASS",
        "command_argv": command,
        "stdout_path": stdout_rel,
        "stdout_sha256": sha256_file(stdout),
        "stdout_bytes": stdout.stat().st_size,
        "stderr_path": stderr_rel,
        "stderr_sha256": sha256_file(stderr),
        "stderr_bytes": stderr.stat().st_size,
        "evidence_path": evidence_rel,
        "evidence_sha256": sha256_file(evidence),
        "evidence_bytes": evidence.stat().st_size,
        "evidence_digest": _sha(args.evidence_digest),
    }
    doc = {
        "schema": CHECK_RECEIPT_SCHEMA,
        **payload,
        "receipt_digest": sha256_bytes(canonical_json_bytes(payload)),
    }
    output = Path(args.output)
    _write_immutable(output, canonical_json_bytes(doc) + b"\n")
    print(json.dumps({
        "status": "PASS_RECEIPT_V2_BUILT",
        "check_id": args.check_id,
        "receipt_digest": doc["receipt_digest"],
        "receipt": str(output),
        "product_qualification_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
