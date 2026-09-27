from __future__ import annotations

import argparse
import json
from pathlib import Path

from cwc.governance.openai_snapshot_panel import verify_openai_snapshot_panel

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOT = ROOT / "artifacts" / "dgc-product-v1" / "execution-candidates"


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the frozen OpenAI two-tier snapshot candidate panel.")
    parser.add_argument(
        "--root",
        default=str(DEFAULT_ROOT.relative_to(ROOT)),
        help="Repository-relative directory containing the candidate manifests.",
    )
    args = parser.parse_args()
    base = Path(args.root)
    if not base.is_absolute():
        base = ROOT / base
    authority = verify_openai_snapshot_panel(
        model_manifest_path=base / "openai_5_4_model_manifest_v1.json",
        action_catalog_path=base / "openai_5_4_action_catalog_v1.json",
        pricing_snapshot_path=base / "openai_5_4_pricing_snapshot_v1.json",
    )
    print(json.dumps({
        "status": "PASS",
        **authority.document,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
