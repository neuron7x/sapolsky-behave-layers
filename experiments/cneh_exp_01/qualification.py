"""Separate engineering evidence integrity from permanently blocked science authority."""
from __future__ import annotations

import argparse
import hashlib
import math
from pathlib import Path
from typing import Any

if __package__:
    from . import run
    from .replication import canonical, read_json
else:
    import run
    from replication import canonical, read_json

HERE = Path(__file__).resolve().parent


def assess(bundle: Path) -> dict[str, Any]:
    """Require valid internal evidence; never accept user-authored authority flags."""
    run.verify_bundle(bundle, require_valid=True)
    protocol = read_json(HERE / "protocol.json")
    if (protocol["primary_comparator"] != "CENTRAL_EMULATOR"
            or "CENTRAL_EMULATOR" not in protocol["primary_contrasts"]
            or protocol["claim_promotion_allowed"] is not False
            or protocol["material_effect"] <= 0):
        raise ValueError("frozen lineage authority boundary changed")
    count = protocol["cohorts"]["primary"]["n_world_seeds"]
    central_lcb = -math.sqrt(2 * math.log(protocol["number_family_tests"] / protocol["alpha_fwer"]) / count)
    source_names = ("protocol.json", "PREREGISTRATION.md", "run.py", "qualification.py", "replication.py")
    return {
        "schema": "cneh-qualification-v1", "experiment": "CNEH-EXP-01",
        "hypothesis_status": "FORMALIZED / EMPIRICAL VALIDATION PENDING",
        "engineering_validation": "PASS", "integration_smoke": "NOT_RUN_BY_THIS_GATE",
        "scientific_readiness": "BLOCKED", "scientific_promotion_authorized": False,
        "same_lineage_supported_narrow_reachable": False,
        "gates": {
            "current_lineage": "STRUCTURALLY_UNTESTABLE_UNDER_SIMULATION_DOMINANCE",
            "cost": "COST_INSTRUMENT_INVALID", "replication": "REPLICATION_NOT_TESTED",
            "substrate": "SUBSTRATE_TOO_SIMPLE", "estimators": "ESTIMATORS_UNQUALIFIED",
            "restricted_comparator": "SEPARATE_PROSPECTIVE_LINEAGE_REQUIRED",
        },
        "structural_falsifier": "Exact emulator trace parity implies D=0 for every paired seed; LCB<0<material_effect.",
        "central_emulator_lcb_at_frozen_primary_n": central_lcb,
        "frozen_primary_n": count, "material_effect": protocol["material_effect"],
        "bundle_manifest_sha256": hashlib.sha256((bundle / "SHA256SUMS").read_bytes()).hexdigest(),
        "source_sha256": {name: hashlib.sha256((HERE / name).read_bytes()).hexdigest() for name in source_names},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--require-scientific-readiness", action="store_true")
    args = parser.parse_args()
    try:
        report = assess(args.bundle)
    except (ValueError, OSError) as error:
        print(canonical({"engineering_validation": "FAIL", "scientific_readiness": "BLOCKED",
                         "scientific_promotion_authorized": False, "error": str(error)}).decode(), end="")
        return 1
    print(canonical(report).decode(), end="")
    return 2 if args.require_scientific_readiness else 0


if __name__ == "__main__":
    raise SystemExit(main())
