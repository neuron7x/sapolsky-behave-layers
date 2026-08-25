from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.executed_p9_anytime_authority import build_anytime_p9_authority


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
        description=(
            "Derive P9 exact-panel facts plus anytime-valid average-conditional-mean "
            "evidence without an iid/provider-request-independence requirement."
        )
    )
    parser.add_argument("--execution-authority", required=True)
    parser.add_argument("--execution-bundle-root", required=True)
    parser.add_argument("--physical-cost-bundle-root", required=True)
    parser.add_argument("--confirmatory-root-authority", required=True)
    parser.add_argument("--harness-freeze", required=True)
    parser.add_argument("--execution-manifest-freeze", required=True)
    parser.add_argument("--materialization-reference", required=True)
    parser.add_argument("--source-registry", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    authority = build_anytime_p9_authority(
        confirmatory_execution_authority_path=Path(args.execution_authority),
        execution_bundle_root=Path(args.execution_bundle_root),
        physical_cost_bundle_root=Path(args.physical_cost_bundle_root),
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
    supported = authority.p9_supported_without_iid_assumption
    print(json.dumps({
        "status": "PASS" if supported else "FAIL_P9_ANYTIME_VALID_GATE",
        "authority": str(output),
        "authority_digest": authority.authority_digest,
        "exact_panel_supported": authority.exact_panel_supported,
        "anytime_average_conditional_mean_supported": authority.anytime_average_conditional_mean_supported,
        "iid_assumption_required": False,
        "provider_request_independence_required": False,
        "legacy_micro_eb_supported_under_cross_pair_independence": (
            authority.legacy_micro_eb_supported_under_cross_pair_independence
        ),
        "p9_supported_without_iid_assumption": supported,
        "generalization_evaluation_authorized": authority.generalization_evaluation_authorized,
        "product_promotion_authorized": False,
    }, sort_keys=True))
    return 0 if supported else 20


if __name__ == "__main__":
    raise SystemExit(main())