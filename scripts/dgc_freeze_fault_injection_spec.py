from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.fault_injection_spec import build_fault_injection_spec_authority


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
    parser = argparse.ArgumentParser(description="Freeze the pre-outcome DGC fault-injection matrix.")
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--fault-spec", required=True)
    parser.add_argument("--execution-manifest-freeze", required=True)
    parser.add_argument("--generalization-registry", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    authority = build_fault_injection_spec_authority(
        repository_root=Path(args.repository_root),
        fault_spec_path=Path(args.fault_spec),
        execution_manifest_freeze_path=Path(args.execution_manifest_freeze),
        generalization_registry_path=Path(args.generalization_registry),
    )
    output = Path(args.output)
    _write_immutable(output, json.dumps(authority.document, indent=2, sort_keys=True).encode("utf-8") + b"\n")
    print(json.dumps({
        "status": "PASS",
        "authority": str(output),
        "authority_digest": authority.authority_digest,
        "case_count": authority.case_count,
        "outcomes_observed": False,
        "fault_execution_authorized": True,
        "product_promotion_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())