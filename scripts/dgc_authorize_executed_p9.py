from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.executed_p9_authority import build_executed_p9_authority


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
        description="Derive executed P9 evidence from the complete frozen confirmatory result population."
    )
    parser.add_argument("--execution-authority", required=True)
    parser.add_argument("--execution-bundle-root", required=True)
    parser.add_argument("--confirmatory-root-authority", required=True)
    parser.add_argument("--harness-freeze", required=True)
    parser.add_argument("--execution-manifest-freeze", required=True)
    parser.add_argument("--materialization-reference", required=True)
    parser.add_argument("--source-registry", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    authority = build_executed_p9_authority(
        confirmatory_execution_authority_path=Path(args.execution_authority),
        execution_bundle_root=Path(args.execution_bundle_root),
        confirmatory_root_authority_path=Path(args.confirmatory_root_authority),
        harness_freeze_path=Path(args.harness_freeze),
        execution_manifest_freeze_path=Path(args.execution_manifest_freeze),
        materialization_reference_path=Path(args.materialization_reference),
        source_registry_path=Path(args.source_registry),
    )
    output = Path(args.output)
    _write_immutable(
        output,
        json.dumps(authority.document, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )
    print(json.dumps({
        "status": "PASS" if authority.p9_supported else "FAIL_P9",
        "authority": str(output),
        "authority_digest": authority.authority_digest,
        "p9_supported": authority.p9_supported,
        "generalization_authorized": authority.p9_supported,
        "product_promotion_authorized": False,
    }, sort_keys=True))
    return 0 if authority.p9_supported else 20


if __name__ == "__main__":
    raise SystemExit(main())
