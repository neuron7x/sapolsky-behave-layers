from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.p19_verification_check_receipt import (
    REQUIRED_CHECKS,
    build_check_receipt_document,
    canonical_receipt_bytes,
)


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

    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    doc = build_check_receipt_document(
        repository_root=args.root.resolve(),
        check_id=args.check_id,
        command_argv=command,
        stdout_path=args.stdout_path,
        stderr_path=args.stderr_path,
        evidence_path=args.evidence_path,
        evidence_digest=args.evidence_digest,
    )
    output = Path(args.output)
    _write_immutable(output, canonical_receipt_bytes(doc))
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
