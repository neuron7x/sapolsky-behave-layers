from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.harness_freeze import build_harness_freeze


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
    parser = argparse.ArgumentParser(description="Freeze final B0-B3+DGC comparison harness after B2 fit.")
    parser.add_argument("--execution-manifest-freeze", required=True)
    parser.add_argument("--ccf-spec-authority", required=True)
    parser.add_argument("--b2-fit-authority", required=True)
    parser.add_argument("--baseline-panel-input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    authority = build_harness_freeze(
        execution_manifest_freeze_path=Path(args.execution_manifest_freeze),
        ccf_spec_authority_path=Path(args.ccf_spec_authority),
        b2_fit_authority_path=Path(args.b2_fit_authority),
        baseline_panel_input_path=Path(args.baseline_panel_input),
    )
    output = Path(args.output)
    _write_immutable(output, json.dumps(authority.document, indent=2, sort_keys=True).encode("utf-8") + b"\n")
    print(json.dumps({
        "status": "PASS",
        "harness": str(output),
        "harness_freeze_digest": authority.harness_freeze_digest,
        "comparison_frame_digest": authority.comparison_frame_digest,
        "ccf_spec_digest": authority.ccf_spec_digest,
        "policy_arms": len(authority.policy_harnesses),
        "confirmatory_execution_authorized": False,
        "product_promotion_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
