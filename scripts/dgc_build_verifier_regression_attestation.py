from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_file
from cwc.governance.p19_external_verifier_activation import (
    canonical_regression_attestation_bytes,
    make_regression_attestation,
)
from cwc.governance.p19_external_verifier_regression import verify_p19_external_verifier_regression_receipt


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
        description=(
            "Build exact canonical bytes for one external verifier to sign after independently "
            "observing the frozen DGC P19 verifier regression. This command does not sign for the verifier."
        )
    )
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--regression-receipt", type=Path, required=True)
    parser.add_argument("--verifier-principal", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = args.repository_root.resolve()
    receipt_path = args.regression_receipt if args.regression_receipt.is_absolute() else root / args.regression_receipt
    receipt = verify_p19_external_verifier_regression_receipt(
        receipt_path,
        repository_root=root,
        allow_descendant_checkout=True,
    )
    attestation = make_regression_attestation(
        regression_receipt=receipt,
        regression_receipt_sha256=sha256_file(receipt_path),
        verifier_principal=args.verifier_principal,
    )
    output = args.output if args.output.is_absolute() else root / args.output
    try:
        output.resolve().parent.relative_to(root)
    except ValueError as exc:
        raise SystemExit("regression attestation output must remain inside repository") from exc
    _write_immutable(output, canonical_regression_attestation_bytes(attestation))
    print(json.dumps({
        "status": "ATTESTATION_BYTES_READY_FOR_EXTERNAL_SIGNATURE",
        "attestation": output.resolve().relative_to(root).as_posix(),
        "attestation_sha256": sha256_file(output),
        "verifier_principal": attestation["verifier_principal"],
        "namespace": attestation["namespace"],
        "signature_created": False,
        "product_qualification_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
