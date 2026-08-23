from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.p9_scientific_authority_v3 import build_p9_scientific_authority_v3


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
        description="Compose anytime-valid P9 with CCF into scientific authority V3."
    )
    parser.add_argument("--anytime-p9-authority", required=True)
    parser.add_argument("--ccf-oracle-audit-authority", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    authority = build_p9_scientific_authority_v3(
        anytime_p9_authority_path=Path(args.anytime_p9_authority),
        ccf_oracle_audit_authority_path=Path(args.ccf_oracle_audit_authority),
    )
    output = Path(args.output)
    _write_immutable(
        output,
        json.dumps(authority.document, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )
    print(json.dumps({
        "status": "PASS" if authority.scientific_p9_supported else "FAIL_P9_SCIENTIFIC_V3",
        "authority": str(output),
        "authority_digest": authority.authority_digest,
        "exact_panel_supported": authority.exact_panel_supported,
        "anytime_average_conditional_mean_supported": authority.anytime_average_conditional_mean_supported,
        "ccf_headroom_audit_complete": authority.ccf_headroom_audit_complete,
        "iid_assumption_required": False,
        "provider_request_independence_required": False,
        "scientific_p9_supported": authority.scientific_p9_supported,
        "generalization_evaluation_authorized": authority.generalization_evaluation_authorized,
        "product_promotion_authorized": False,
    }, sort_keys=True))
    return 0 if authority.scientific_p9_supported else 21


if __name__ == "__main__":
    raise SystemExit(main())