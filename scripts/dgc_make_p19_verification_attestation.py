from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.p19_evidence_root import verify_family_p19_evidence_root_document
from cwc.governance.p19_verification_attestation import (
    bind_report_to_p19,
    canonical_attestation_bytes,
    load_p19_verification_report,
    make_p19_verification_attestation,
)
from cwc.governance.materialization_transaction import sha256_file


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
        description="Create a canonical P19 external-verification attestation from an already completed verification report."
    )
    parser.add_argument("--p19", required=True)
    parser.add_argument("--verification-report", required=True)
    parser.add_argument("--verifier-principal", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    p19 = verify_family_p19_evidence_root_document(Path(args.p19))
    report_path = Path(args.verification_report)
    report = load_p19_verification_report(report_path)
    bind_report_to_p19(report, p19)
    attestation = make_p19_verification_attestation(
        family_p19=p19,
        verifier_principal=args.verifier_principal,
        verification_report_sha256=sha256_file(report_path),
    )
    output = Path(args.output)
    _write_immutable(output, canonical_attestation_bytes(attestation))
    print(json.dumps({
        "status": "PASS_ATTESTATION_CREATED_NOT_SIGNED",
        "family_id": p19["family_id"],
        "p19_digest": p19["p19_digest"],
        "verification_report_sha256": sha256_file(report_path),
        "attestation": str(output),
        "signature_verified": False,
        "product_qualification_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
