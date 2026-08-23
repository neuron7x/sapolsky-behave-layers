from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.generalization_dual_authority import build_generalization_dual_authority
from cwc.governance.generalization_registry import GeneralizationAxis


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
        description="Compose exact and conditional G1-G5 authorities after primary scientific P9."
    )
    parser.add_argument("--registry", required=True)
    parser.add_argument("--p9-scientific-v2", required=True)
    parser.add_argument("--g1-authority", required=True)
    parser.add_argument("--g2-authority", required=True)
    parser.add_argument("--g3-authority", required=True)
    parser.add_argument("--g4-authority", required=True)
    parser.add_argument("--g5-authority", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    axis_paths = {
        GeneralizationAxis.UNSEEN_TASKS: Path(args.g1_authority),
        GeneralizationAxis.UNSEEN_DOMAIN: Path(args.g2_authority),
        GeneralizationAxis.UNSEEN_MODEL_PROVIDER: Path(args.g3_authority),
        GeneralizationAxis.CHANGED_ECONOMICS: Path(args.g4_authority),
        GeneralizationAxis.PERTURBATION_SHIFT: Path(args.g5_authority),
    }
    authority = build_generalization_dual_authority(
        registry_path=Path(args.registry),
        p9_scientific_v2_authority_path=Path(args.p9_scientific_v2),
        axis_authority_paths=axis_paths,
    )
    output = Path(args.output)
    _write_immutable(
        output,
        json.dumps(authority.document, indent=2, sort_keys=True).encode("utf-8") + b"\n",
    )
    supported = (
        authority.exact_g1_g5_supported
        and authority.expected_g1_g5_supported_under_independence_assumption
    )
    print(json.dumps({
        "status": "PASS" if supported else "FAIL_G1_G5_SCIENTIFIC_GATE",
        "authority": str(output),
        "authority_digest": authority.authority_digest,
        "exact_g1_g5_supported": authority.exact_g1_g5_supported,
        "expected_g1_g5_supported_under_independence_assumption": (
            authority.expected_g1_g5_supported_under_independence_assumption
        ),
        "generalization_supported_under_frozen_assumptions": supported,
        "independent_replication_evaluation_authorized": supported,
        "product_promotion_authorized": False,
    }, sort_keys=True))
    return 0 if supported else 31


if __name__ == "__main__":
    raise SystemExit(main())
