from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.materialization_transaction import canonical_json_bytes
from cwc.governance.p19_external_verifier_activation import (
    build_p19_external_verifier_activation_authority,
    verify_p19_external_verifier_activation_authority_document,
)


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
        description="Build and immediately raw-signature-replay the dual-external-verifier activation authority."
    )
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--regression-receipt", type=Path, required=True)
    parser.add_argument("--trust-policy", type=Path, required=True)
    parser.add_argument("--attestation", type=Path, action="append", required=True)
    parser.add_argument("--signature", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    root = args.repository_root.resolve()
    authority = build_p19_external_verifier_activation_authority(
        repository_root=root,
        regression_receipt_path=args.regression_receipt,
        trust_policy_path=args.trust_policy,
        attestation_paths=args.attestation,
        signature_paths=args.signature,
    )
    output = args.output if args.output.is_absolute() else root / args.output
    try:
        output.resolve().parent.relative_to(root)
    except ValueError as exc:
        raise SystemExit("activation authority output must remain inside repository") from exc
    _write_immutable(output, canonical_json_bytes(authority.document) + b"\n")
    verified = verify_p19_external_verifier_activation_authority_document(output, repository_root=root)
    if verified.get("activation_authorized") is not True:
        raise RuntimeError("written activation authority failed raw-signature replay")
    print(json.dumps({
        "status": "ACTIVATION_AUTHORITY_VERIFIED",
        "authority": output.resolve().relative_to(root).as_posix(),
        "authority_digest": authority.authority_digest,
        "source_commit": authority.source_commit,
        "source_tree": authority.source_tree,
        "verifier_principals": list(authority.verifier_principals),
        "distinct_signer_keys": len(set(authority.signer_key_digests)),
        "activation_authorized": True,
        "product_qualification_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
