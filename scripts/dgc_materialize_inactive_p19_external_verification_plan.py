from __future__ import annotations

import argparse
import os
from pathlib import Path

from cwc.governance.materialization_transaction import canonical_json_bytes
from cwc.governance.p19_external_verification_plan import (
    CANONICAL_PLAN_PATH,
    build_inactive_p19_external_verification_plan_document,
)
from cwc.governance.p19_verification_check_receipt import REQUIRED_CHECKS


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
            "Materialize the canonical content-addressed P19 external verification Plan V2 "
            "in an intentionally inactive state. This command cannot authorize activation."
        )
    )
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--output", default=CANONICAL_PLAN_PATH)
    args = parser.parse_args()

    root = Path(args.repository_root).resolve()
    output = Path(args.output)
    if not output.is_absolute():
        output = root / output
    resolved_parent = output.parent.resolve()
    try:
        resolved_parent.relative_to(root)
    except ValueError as exc:
        raise RuntimeError("inactive verification plan output escapes repository") from exc

    doc = build_inactive_p19_external_verification_plan_document(
        repository_root=root,
        implemented_check_ids=tuple(sorted(REQUIRED_CHECKS)),
    )
    if doc.get("activation_authorized") is not False:
        raise RuntimeError("inactive Plan V2 builder illegally authorized activation")
    if doc.get("product_qualification_authorized") is not False:
        raise RuntimeError("inactive Plan V2 builder illegally authorized product qualification")
    if doc.get("all_check_implementations_complete") is not True:
        raise RuntimeError("canonical eight-check implementation population is incomplete")

    _write_immutable(output, canonical_json_bytes(doc) + b"\n")
    print(f"DGC-P19-EXTERNAL-PLAN-V2: {output.relative_to(root).as_posix()}")
    print(f"DGC-P19-EXTERNAL-PLAN-V2-DIGEST: {doc['plan_digest']}")
    print("DGC-P19-EXTERNAL-PLAN-V2-IMPLEMENTATIONS-COMPLETE: true")
    print("DGC-P19-EXTERNAL-PLAN-V2-ACTIVATION-AUTHORIZED: false")
    print("DGC-P19-EXTERNAL-PLAN-V2-PRODUCT-QUALIFICATION-AUTHORIZED: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
