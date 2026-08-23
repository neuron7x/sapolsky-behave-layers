from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.generalization_dual_authority import build_generalization_axis_dual_authority


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
        description="Derive one G1-G5 dual exact-panel + conditional expected-effect authority."
    )
    parser.add_argument("--bundle-root", required=True)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--registry", required=True)
    parser.add_argument("--trial-sizing-authority", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    authority = build_generalization_axis_dual_authority(
        Path(args.bundle_root),
        repository_root=Path(args.repository_root),
        registry_path=Path(args.registry),
        trial_sizing_authority_path=Path(args.trial_sizing_authority),
    )
    output = Path(args.output)
    _write_immutable(
        output,
        json.dumps(authority.document, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )
    print(json.dumps({
        "status": "PASS" if authority.exact_panel_supported else "FAIL_EXACT_GENERALIZATION_AXIS",
        "axis": authority.axis,
        "authority": str(output),
        "authority_digest": authority.authority_digest,
        "exact_panel_supported": authority.exact_panel_supported,
        "expected_effect_supported_under_independence_assumption": (
            authority.expected_effect_supported_under_independence_assumption
        ),
        "randomness_assumption_verified": authority.randomness_assumption_verified,
        "product_promotion_authorized": False,
    }, sort_keys=True))
    return 0 if authority.exact_panel_supported else 30


if __name__ == "__main__":
    raise SystemExit(main())
