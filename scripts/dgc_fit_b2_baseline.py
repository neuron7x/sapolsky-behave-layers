from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from cwc.governance.b2_fit_receipt import fit_b2_with_receipt
from cwc.governance.learned_baseline import CalibrationExample, LearnedRouterConfig


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    if payload.get("schema") != "DGC_B2_FIT_INPUT_V1":
        raise ValueError("wrong B2 fit input schema")
    config = LearnedRouterConfig(**payload["config"])
    examples = [
        CalibrationExample(
            task_id=row["task_id"],
            action_id=row["action_id"],
            features=tuple(row["features"]),
            quality=float(row["quality"]),
            cost_usd=float(row["cost_usd"]),
            catastrophic_regret=float(row["catastrophic_regret"]),
        )
        for row in payload["examples"]
    ]
    receipt = fit_b2_with_receipt(
        config=config,
        examples=examples,
        forbidden_task_ids=payload["forbidden_task_ids"],
        expected_feature_schema_digest=payload["expected_feature_schema_digest"],
        expected_training_algorithm_digest=payload["expected_training_algorithm_digest"],
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(asdict(receipt), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "PASS",
                "receipt": str(output),
                "fitted_model_digest": receipt.fitted_model_digest,
                "receipt_digest": receipt.receipt_digest,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
