from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.confirmatory_execution_authority import build_confirmatory_execution_authority


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
        description="Replay a complete frozen confirmatory execution bundle and mint EXECUTED source authority."
    )
    parser.add_argument("--execution-bundle-root", required=True)
    parser.add_argument("--confirmatory-root-authority", required=True)
    parser.add_argument("--materialization-reference", required=True)
    parser.add_argument("--source-registry", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    authority = build_confirmatory_execution_authority(
        execution_bundle_root=Path(args.execution_bundle_root),
        confirmatory_root_authority_path=Path(args.confirmatory_root_authority),
        materialization_reference_path=Path(args.materialization_reference),
        source_registry_path=Path(args.source_registry),
    )
    output = Path(args.output)
    data = json.dumps(authority.document, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    _write_immutable(output, data)
    print(json.dumps({
        "status": "PASS",
        "authority": str(output),
        "authority_digest": authority.authority_digest,
        "executed_source_authority_digest": authority.executed_source_authority_digest,
        "execution_population_digest": authority.execution_population_digest,
        "p9_evaluation_authorized": True,
        "product_promotion_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
