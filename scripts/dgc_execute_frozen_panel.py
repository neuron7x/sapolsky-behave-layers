from __future__ import annotations

import argparse
import json
from pathlib import Path

from cwc.governance.frozen_panel_executor import execute_frozen_panel

ROOT = Path(__file__).resolve().parents[1]
SOURCE_REGISTRY = ROOT / "artifacts/dgc-product-v1/external_source_authority.json"


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Execute the exact frozen DGC confirmatory task×policy×replicate population."
    )
    parser.add_argument("--execution-freeze", required=True)
    parser.add_argument("--harness-freeze", required=True)
    parser.add_argument("--confirmatory-root-authority", required=True)
    parser.add_argument("--materialization-generation-root", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--worker-id", default="dgc-local-executor")
    args = parser.parse_args()

    output = execute_frozen_panel(
        repository_root=ROOT,
        execution_manifest_freeze_path=_path(args.execution_freeze),
        harness_freeze_path=_path(args.harness_freeze),
        confirmatory_root_authority_path=_path(args.confirmatory_root_authority),
        materialization_generation_root=_path(args.materialization_generation_root),
        source_registry_path=SOURCE_REGISTRY,
        output_root=_path(args.output_root),
        worker_id=args.worker_id,
    )
    manifest = json.loads((output / "EXECUTION_BUNDLE.json").read_text(encoding="utf-8"))
    print(json.dumps({
        "status": "PASS",
        "output_root": str(output),
        "family_id": manifest["family_id"],
        "expected_units": manifest["expected_units"],
        "committed_units": manifest["committed_units"],
        "total_cost_usd": manifest["total_cost_usd"],
        "bundle_digest": manifest["bundle_digest"],
        "product_promotion_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
