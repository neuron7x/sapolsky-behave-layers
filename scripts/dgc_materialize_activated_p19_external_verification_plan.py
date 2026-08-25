from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.materialization_transaction import canonical_json_bytes
from cwc.governance.p19_external_verification_plan import (
    CANONICAL_PLAN_PATH,
    build_activated_p19_external_verification_plan_document,
    load_p19_external_verification_plan,
)
from cwc.governance.p19_external_verification_transition import (
    ACTIVATED_PLAN_DEFAULT_PATH,
    verify_inactive_to_activated_transition,
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


def _inside(root: Path, value: Path, *, label: str) -> Path:
    candidate = value if value.is_absolute() else root / value
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise RuntimeError(f"{label} escapes repository") from exc
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Materialize an immutable activated P19 external verification Plan V4 as an activation-only "
            "composition of the already-frozen inactive canonical contract."
        )
    )
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--activation-authority", type=Path, required=True)
    parser.add_argument("--inactive-contract", type=Path, default=Path(CANONICAL_PLAN_PATH))
    parser.add_argument("--output", type=Path, default=Path(ACTIVATED_PLAN_DEFAULT_PATH))
    args = parser.parse_args()

    root = args.repository_root.resolve()
    inactive_path = _inside(root, args.inactive_contract, label="inactive verifier contract")
    output = _inside(root, args.output, label="activated verifier plan output")
    activation_authority = _inside(root, args.activation_authority, label="activation authority")

    if inactive_path == output:
        raise RuntimeError("activated verifier plan cannot overwrite immutable inactive contract")
    inactive = load_p19_external_verification_plan(
        inactive_path,
        repository_root=root,
        require_active=False,
    )
    if inactive.activation_authorized:
        raise RuntimeError("inactive verifier contract is already activated")

    document = build_activated_p19_external_verification_plan_document(
        repository_root=root,
        activation_authority_path=activation_authority,
    )
    _write_immutable(output, canonical_json_bytes(document) + b"\n")
    activated = load_p19_external_verification_plan(
        output,
        repository_root=root,
        require_active=True,
    )
    transition = verify_inactive_to_activated_transition(
        inactive=inactive,
        activated=activated,
        inactive_contract_path=inactive_path.relative_to(root).as_posix(),
        activated_plan_path=output.relative_to(root).as_posix(),
    )
    print(json.dumps({
        "status": "MATERIALIZED_ACTIVATED",
        "inactive_contract": inactive_path.relative_to(root).as_posix(),
        "inactive_contract_plan_digest": inactive.plan_digest,
        "activated_plan": output.relative_to(root).as_posix(),
        "activated_plan_digest": activated.plan_digest,
        "activation_authority": activation_authority.relative_to(root).as_posix(),
        "same_entrypoint_identity": transition.same_entrypoint_identity,
        "same_runtime_dependency_identity": transition.same_runtime_dependency_identity,
        "same_check_contract_identity": transition.same_check_contract_identity,
        "activation_authorized": True,
        "product_qualification_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
