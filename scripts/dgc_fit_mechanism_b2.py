from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from cwc.governance.mechanism_b2_fit_receipt import fit_mechanism_b2_with_receipt
from cwc.governance.mechanism_learned_baseline import MechanismCalibrationExample, MechanismLearnedRouterConfig


def main() -> int:
    parser = argparse.ArgumentParser(description="Fit risk-free mechanism B2 on calibration tasks only.")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if payload.get("schema") != "DGC_MECHANISM_B2_FIT_INPUT_V1":
        raise ValueError("wrong mechanism B2 fit input schema")
    forbidden = {"catastrophic_regret", "risk", "risk_score", "risk_endpoint"}
    if forbidden.intersection(payload):
        raise ValueError("mechanism B2 input contains forbidden risk field")
    config = MechanismLearnedRouterConfig(**payload["config"])
    examples = []
    for row in payload["examples"]:
        if forbidden.intersection(row):
            raise ValueError("mechanism B2 example contains forbidden risk field")
        examples.append(MechanismCalibrationExample(
            task_id=row["task_id"],
            action_id=row["action_id"],
            features=tuple(row["features"]),
            quality=float(row["quality"]),
            cost_usd=float(row["cost_usd"]),
        ))
    receipt = fit_mechanism_b2_with_receipt(
        config=config,
        examples=examples,
        forbidden_task_ids=payload["forbidden_task_ids"],
        expected_feature_schema_digest=payload["expected_feature_schema_digest"],
        expected_training_algorithm_digest=payload["expected_training_algorithm_digest"],
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": "PASS",
        "receipt": str(output),
        "fitted_model_digest": receipt.fitted_model_digest,
        "receipt_digest": receipt.receipt_digest,
        "risk_fields_consumed": False,
        "product_promotion_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
