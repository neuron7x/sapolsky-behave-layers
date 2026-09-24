from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from cwc.governance.calibration_variance import CalibrationObservation
from cwc.governance.product_statistical_plan import ProductStatisticalPlan
from cwc.governance.trial_sizing_receipt import freeze_cluster_aware_trial_sizing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if payload.get("schema") != "DGC_CLUSTER_AWARE_TRIAL_SIZING_INPUT_V1":
        raise ValueError("wrong trial-sizing input schema")
    plan = ProductStatisticalPlan(**payload.get("plan", {}))
    observations = [
        CalibrationObservation(
            comparison_id=row["comparison_id"],
            task_id=row["task_id"],
            replicate=int(row["replicate"]),
            value=float(row["value"]),
        )
        for row in payload["observations"]
    ]
    receipt = freeze_cluster_aware_trial_sizing(
        observations=observations,
        effects_of_interest=payload["effects_of_interest"],
        confirmatory_task_count=int(payload["confirmatory_task_count"]),
        plan=plan,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "PASS",
                "receipt": str(output),
                "required_trials_per_task": receipt.required_trials_per_task,
                "receipt_digest": receipt.receipt_digest,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
