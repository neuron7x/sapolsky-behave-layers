from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.ccf_oracle_audit_authority import build_ccf_oracle_audit_authority

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
    parser = argparse.ArgumentParser(description="Replay execution-bound CCF options and measure oracle headroom.")
    parser.add_argument("--ccf-spec-authority", required=True)
    parser.add_argument("--ccf-evidence-bundle-root", required=True)
    parser.add_argument("--execution-authority", required=True)
    parser.add_argument("--execution-bundle-root", required=True)
    parser.add_argument("--physical-cost-bundle-root", required=True)
    parser.add_argument("--confirmatory-root-authority", required=True)
    parser.add_argument("--harness-freeze", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    authority = build_ccf_oracle_audit_authority(
        repository_root=ROOT,
        ccf_spec_authority_path=Path(args.ccf_spec_authority),
        ccf_evidence_bundle_root=Path(args.ccf_evidence_bundle_root),
        confirmatory_execution_authority_path=Path(args.execution_authority),
        execution_bundle_root=Path(args.execution_bundle_root),
        physical_cost_bundle_root=Path(args.physical_cost_bundle_root),
        confirmatory_root_authority_path=Path(args.confirmatory_root_authority),
        harness_freeze_path=Path(args.harness_freeze),
    )
    output = Path(args.output)
    _write_immutable(output, json.dumps(authority.document, indent=2, sort_keys=True).encode("utf-8") + b"\n")
    print(json.dumps({
        "status": "PASS",
        "authority": str(output),
        "authority_digest": authority.authority_digest,
        "headroom_audit_complete": authority.headroom_audit_complete,
        "total_value_regret_units": authority.total_value_regret_units,
        "total_avoidable_cost_units": authority.total_avoidable_cost_units,
        "product_promotion_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
