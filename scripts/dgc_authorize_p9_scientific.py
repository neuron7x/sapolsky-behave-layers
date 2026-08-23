from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.p9_scientific_authority_v2 import build_p9_scientific_authority_v2


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
        description="Compose dual exact/conditional P9 with CCF into scientific authority V2."
    )
    parser.add_argument("--dual-p9-authority", required=True)
    parser.add_argument("--ccf-oracle-audit-authority", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    authority = build_p9_scientific_authority_v2(
        dual_p9_authority_path=Path(args.dual_p9_authority),
        ccf_oracle_audit_authority_path=Path(args.ccf_oracle_audit_authority),
    )
    output = Path(args.output)
    _write_immutable(
        output,
        json.dumps(authority.document, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )
    print(json.dumps({
        "status": "PASS" if authority.generalization_evaluation_authorized else "FAIL_P9_SCIENTIFIC_V2",
        "authority": str(output),
        "authority_digest": authority.authority_digest,
        "exact_panel_supported": authority.exact_panel_supported,
        "expected_effect_supported_under_independence_assumption": (
            authority.expected_effect_supported_under_independence_assumption
        ),
        "randomness_assumption_verified": authority.randomness_assumption_verified,
        "ccf_headroom_audit_complete": authority.ccf_headroom_audit_complete,
        "generalization_evaluation_authorized": authority.generalization_evaluation_authorized,
        "product_promotion_authorized": False,
    }, sort_keys=True))
    return 0 if authority.generalization_evaluation_authorized else 21


if __name__ == "__main__":
    raise SystemExit(main())
