from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.p19_external_verification_plan import CANONICAL_PLAN_PATH
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
        description="Build one canonical P19 verification report V3 under the frozen external verification plan."
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--p19", required=True)
    parser.add_argument("--verification-plan", default=CANONICAL_PLAN_PATH)
    parser.add_argument("--check-receipt", action="append", default=[], required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    root = args.root.resolve()
    p19_path = Path(args.p19)
    if not p19_path.is_absolute():
        p19_path = root / p19_path
    p19 = verify_family_p19_evidence_root_document(p19_path)
    report = build_p19_verification_report(
        repository_root=root,
        family_p19=p19,
        family_p19_path=p19_path,
        verification_plan_path=Path(args.verification_plan),
        check_receipt_paths=tuple(Path(value) for value in args.check_receipt),
    )
    output = Path(args.output)
    _write_immutable(output, report_bytes(report))
    print(json.dumps({
        "status": "PASS_REPORT_V3_BUILT_NOT_ATTESTED",
        "family_id": p19["family_id"],
        "p19_digest": p19["p19_digest"],
        "verification_plan_digest": report["verification_plan_digest"],
        "verifier_entrypoint_sha256": report["verifier_entrypoint_sha256"],
        "checks_digest": report["checks_digest"],
        "raw_transcript_manifest_digest": report["raw_transcript_manifest_digest"],
        "required_check_count": len(report["checks"]),
        "verification_report": str(output),
        "external_signature_verified": False,
        "product_qualification_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
