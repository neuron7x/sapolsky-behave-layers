from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.p19_evidence_root import verify_family_p19_evidence_root_document
from cwc.governance.p19_verification_report import build_p19_verification_report, report_bytes


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
    parser = argparse.ArgumentParser(
        description="Build one canonical external P19 verification report from exactly eight canonical check receipts."
    )
    parser.add_argument("--p19", required=True)
    parser.add_argument("--check-receipt", action="append", default=[], required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    p19 = verify_family_p19_evidence_root_document(Path(args.p19))
    report = build_p19_verification_report(
        family_p19=p19,
        check_receipt_paths=tuple(Path(value) for value in args.check_receipt),
    )
    output = Path(args.output)
    _write_immutable(output, report_bytes(report))
    print(json.dumps({
        "status": "PASS_REPORT_BUILT_NOT_ATTESTED",
        "family_id": p19["family_id"],
        "p19_digest": p19["p19_digest"],
        "checks_digest": report["checks_digest"],
        "required_check_count": len(report["checks"]),
        "verification_report": str(output),
        "external_signature_verified": False,
        "product_qualification_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
