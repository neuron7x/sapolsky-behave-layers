from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.generalization_anytime_authority import build_generalization_axis_anytime_authority


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
        description="Derive one G1-G5 exact-panel plus anytime-valid average-conditional-mean authority."
    )
    parser.add_argument("--bundle-root", required=True)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--registry", required=True)
    parser.add_argument("--trial-sizing-authority", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    authority = build_generalization_axis_anytime_authority(
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
    supported = authority.axis_supported_without_iid_assumption
    print(json.dumps({
        "status": "PASS" if supported else "FAIL_GENERALIZATION_AXIS_ANYTIME_GATE",
        "axis": authority.axis,
        "authority": str(output),
        "authority_digest": authority.authority_digest,
        "exact_panel_supported": authority.exact_panel_supported,
        "anytime_average_conditional_mean_supported": authority.anytime_average_conditional_mean_supported,
        "iid_assumption_required": False,
        "provider_request_independence_required": False,
        "legacy_micro_eb_supported_under_cross_pair_independence": (
            authority.legacy_micro_eb_supported_under_cross_pair_independence
        ),
        "axis_supported_without_iid_assumption": supported,
        "product_promotion_authorized": False,
    }, sort_keys=True))
    return 0 if supported else 30


if __name__ == "__main__":
    raise SystemExit(main())