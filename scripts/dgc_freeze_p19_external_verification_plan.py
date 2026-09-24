from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.materialization_transaction import canonical_json_bytes
from cwc.governance.p19_external_verification_plan_v5 import (
    CANONICAL_PLAN_PATH,
    build_inactive_p19_external_verification_plan_v5_document,
    load_p19_external_verification_plan_v5,
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
        description=(
            "Freeze canonical inactive P19 external verification Plan V5 from exact current verifier bytes. "
            "Portable dual-signed Activation V2 is required later and is materialized into a distinct active-plan path."
        )
    )
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path, default=Path(CANONICAL_PLAN_PATH))
    args = parser.parse_args()

    root = args.repository_root.resolve()
    output = args.output if args.output.is_absolute() else root / args.output
    try:
        output.parent.resolve().relative_to(root)
    except ValueError as exc:
        raise SystemExit("P19 Plan V5 output must remain inside repository") from exc

    document = build_inactive_p19_external_verification_plan_v5_document(repository_root=root)
    _write_immutable(output, canonical_json_bytes(document) + b"\n")
    verified = load_p19_external_verification_plan_v5(output, repository_root=root, require_active=False)
    if verified.activation_authorized:
        raise RuntimeError("inactive Plan V5 freezer produced an activated plan")
    forbidden = (
        verified.activation_authority_path,
        verified.activation_authority_sha256,
        verified.activation_authority_digest,
        verified.activation_trust_policy_path,
        verified.activation_trust_policy_digest,
        verified.activation_allowed_signers_sha256,
        verified.activation_regression_receipt_path,
        verified.activation_regression_receipt_sha256,
        verified.activation_regression_receipt_digest,
        verified.activation_regression_source_commit,
        verified.activation_regression_source_tree,
        verified.activation_regression_test_manifest_digest,
        verified.activation_signature_semantics,
    )
    if any(value is not None for value in forbidden):
        raise RuntimeError("inactive Plan V5 freezer illegally bound activation evidence")
    if verified.activation_verifier_principals or verified.activation_signer_key_digests:
        raise RuntimeError("inactive Plan V5 freezer illegally bound verifier signer population")
    if verified.activation_signature_tool_execution_provenance_authoritative:
        raise RuntimeError("inactive Plan V5 leaked machine-local signature-tool provenance into authority")

    print(json.dumps({
        "status": "FROZEN_INACTIVE_V5",
        "plan_path": output.resolve().relative_to(root).as_posix(),
        "plan_digest": verified.plan_digest,
        "all_check_implementations_complete": verified.all_check_implementations_complete,
        "activation_authorized": False,
        "activation_requires_portable_dual_signed_v2_authority": True,
        "product_qualification_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
