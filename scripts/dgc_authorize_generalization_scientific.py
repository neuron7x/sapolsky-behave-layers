from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.generalization_scientific_authority_v3 import (
    build_generalization_scientific_authority_v3,
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
        description="Promote exact+conditional G1-G5 evidence into scientific generalization authority."
    )
    parser.add_argument("--generalization-dual-authority", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    authority = build_generalization_scientific_authority_v3(
        Path(args.generalization_dual_authority)
    )
    output = Path(args.output)
    _write_immutable(
        output,
        json.dumps(authority.document, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )
    supported = authority.generalization_supported_under_frozen_assumptions
    print(json.dumps({
        "status": "PASS" if supported else "FAIL_GENERALIZATION_SCIENTIFIC_GATE",
        "authority": str(output),
        "authority_digest": authority.authority_digest,
        "exact_g1_g5_supported": authority.exact_g1_g5_supported,
        "expected_g1_g5_supported_under_independence_assumption": (
            authority.expected_g1_g5_supported_under_independence_assumption
        ),
        "generalization_supported_under_frozen_assumptions": supported,
        "independent_replication_evaluation_authorized": (
            authority.independent_replication_evaluation_authorized
        ),
        "product_promotion_authorized": False,
    }, sort_keys=True))
    return 0 if supported else 32


if __name__ == "__main__":
    raise SystemExit(main())
