from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.ccf_spec_authority import build_ccf_spec_authority

ROOT = Path(__file__).resolve().parents[1]


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
    parser = argparse.ArgumentParser(description="Freeze counterfactual-oracle semantics before B2 outcomes.")
    parser.add_argument("--execution-manifest-freeze", required=True)
    parser.add_argument("--ccf-spec", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    authority = build_ccf_spec_authority(
        repository_root=ROOT,
        execution_manifest_freeze_path=Path(args.execution_manifest_freeze),
        ccf_spec_path=Path(args.ccf_spec),
    )
    output = Path(args.output)
    _write_immutable(output, json.dumps(authority.document, indent=2, sort_keys=True).encode("utf-8") + b"\n")
    print(json.dumps({
        "status": "PASS",
        "authority": str(output),
        "authority_digest": authority.authority_digest,
        "ccf_spec_digest": authority.ccf_spec_digest,
        "frozen_pre_outcome": True,
        "product_promotion_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
