from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from cwc.governance.materialization_transaction import canonical_json_bytes
from cwc.governance.p19_external_replay import CHECK_HANDLERS, run_external_p19_check


def _write_immutable(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Execute one frozen canonical DGC external P19 semantic replay check."
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--check-id", choices=sorted(CHECK_HANDLERS), required=True)
    parser.add_argument("--p19", type=Path, required=True)
    parser.add_argument("--evidence-output", type=Path, required=True)
    args = parser.parse_args()

    root = args.root.resolve()
    output = args.evidence_output if args.evidence_output.is_absolute() else root / args.evidence_output
    try:
        evidence = run_external_p19_check(
            repository_root=root,
            p19_path=args.p19,
            check_id=args.check_id,
        )
        _write_immutable(output, canonical_json_bytes(evidence) + b"\n")
    except (RuntimeError, OSError, ValueError) as exc:
        print(json.dumps({
            "status": "FAIL_CLOSED",
            "check_id": args.check_id,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "product_qualification_authorized": False,
        }, sort_keys=True), file=sys.stderr)
        return 2

    try:
        shown = output.resolve().relative_to(root).as_posix()
    except ValueError:
        shown = str(output.resolve())
    print(json.dumps({
        "status": "PASS_EXTERNAL_P19_CHECK",
        "check_id": args.check_id,
        "evidence_output": shown,
        "evidence_digest": evidence["evidence_digest"],
        "product_qualification_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
