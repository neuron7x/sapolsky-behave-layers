from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.materialization_transaction import canonical_json_bytes
from cwc.governance.p19_external_replay import CHECK_HANDLERS
from cwc.governance.p19_external_verification_plan import (
    CANONICAL_PLAN_PATH,
    build_inactive_p19_external_verification_plan_document,
    load_p19_external_verification_plan,
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
            "Materialize canonical content-addressed P19 external verification Plan V4 "
            "in an intentionally inactive pre-outcome state. This command cannot authorize activation."
        )
    )
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--output", default=CANONICAL_PLAN_PATH)
    args = parser.parse_args()

    root = Path(args.repository_root).resolve()
    output = Path(args.output)
    if not output.is_absolute():
        output = root / output
    try:
        output.parent.resolve().relative_to(root)
    except ValueError as exc:
        raise RuntimeError("inactive verification plan output escapes repository") from exc

    doc = build_inactive_p19_external_verification_plan_document(
        repository_root=root,
        implemented_check_ids=tuple(sorted(CHECK_HANDLERS)),
    )
    _write_immutable(output, canonical_json_bytes(doc) + b"\n")
    verified = load_p19_external_verification_plan(output, repository_root=root, require_active=False)

    if verified.activation_authorized:
        raise RuntimeError("inactive Plan V4 materializer illegally authorized activation")
    if verified.product_qualification_authorized:
        raise RuntimeError("inactive Plan V4 materializer illegally authorized product qualification")
    if not verified.all_check_implementations_complete:
        raise RuntimeError("canonical eight-check implementation population is incomplete")
    forbidden = (
        verified.activation_authority_path,
        verified.activation_authority_sha256,
        verified.activation_authority_digest,
        verified.activation_trust_policy_path,
        verified.activation_trust_policy_digest,
        verified.activation_regression_receipt_path,
        verified.activation_regression_receipt_sha256,
        verified.activation_regression_receipt_digest,
        verified.activation_regression_source_commit,
        verified.activation_regression_source_tree,
        verified.activation_regression_test_manifest_digest,
    )
    if any(value is not None for value in forbidden):
        raise RuntimeError("inactive Plan V4 illegally carries activation evidence")
    if verified.activation_verifier_principals or verified.activation_signer_key_digests:
        raise RuntimeError("inactive Plan V4 illegally carries activation signer population")

    print(json.dumps({
        "status": "MATERIALIZED_INACTIVE",
        "plan_path": output.resolve().relative_to(root).as_posix(),
        "plan_digest": verified.plan_digest,
        "runtime_dependency_count": len(verified.verifier_dependencies),
        "all_check_implementations_complete": True,
        "activation_authorized": False,
        "product_qualification_authorized": False,
        "activation_requires_dual_signed_regression_authority": True,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
