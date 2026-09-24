from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.fault_tolerance_authority import build_fault_tolerance_authority


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
    parser = argparse.ArgumentParser(description="Replay the complete frozen DGC fault matrix and derive fault-tolerance authority.")
    parser.add_argument("--bundle-root", required=True)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--fault-spec-authority", required=True)
    parser.add_argument("--execution-manifest-freeze", required=True)
    parser.add_argument("--harness-freeze", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    authority = build_fault_tolerance_authority(
        Path(args.bundle_root),
        repository_root=Path(args.repository_root),
        fault_spec_authority_path=Path(args.fault_spec_authority),
        execution_manifest_freeze_path=Path(args.execution_manifest_freeze),
        harness_freeze_path=Path(args.harness_freeze),
    )
    output = Path(args.output)
    _write_immutable(output, json.dumps(authority.document, indent=2, sort_keys=True).encode("utf-8") + b"\n")
    supported = authority.all_required_cases_supported
    print(json.dumps({
        "status": "PASS" if supported else "FAIL_FAULT_TOLERANCE",
        "authority": str(output),
        "authority_digest": authority.authority_digest,
        "case_population_digest": authority.case_population_digest,
        "case_count": len(authority.case_records),
        "fault_tolerance_supported": supported,
        "production_fault_tolerance_claim": False,
        "product_promotion_authorized": False,
    }, sort_keys=True))
    return 0 if supported else 50


if __name__ == "__main__":
    raise SystemExit(main())