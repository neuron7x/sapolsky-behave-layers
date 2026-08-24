from __future__ import annotations

import argparse
import json


CHECK_IDS = (
    "REPOSITORY_IDENTITY",
    "THEOREM_AND_PLAN_IDENTITY",
    "SUBJECT_ROOT_REHASH",
    "P19_SEAL_REBUILD",
    "PRIMARY_P9_RAW_REPLAY",
    "GENERALIZATION_G1_G5_RAW_REPLAY",
    "FAULT_TOLERANCE_RAW_REPLAY",
    "INDEPENDENT_REPLICATION_RAW_REPLAY",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Canonical external DGC P19 semantic verifier entry point.")
    parser.add_argument("--check-id", choices=CHECK_IDS, required=True)
    parser.add_argument("--p19", required=True)
    parser.add_argument("--evidence-output", required=True)
    args = parser.parse_args()
    print(json.dumps({
        "schema": "DGC_P19_EXTERNAL_VERIFIER_RESULT_V1",
        "check_id": args.check_id,
        "status": "FAIL_CLOSED_NOT_IMPLEMENTED",
        "p19": args.p19,
        "evidence_output": args.evidence_output,
        "product_qualification_authorized": False,
    }, sort_keys=True))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
