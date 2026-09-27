from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.calibration_variance import CalibrationObservation
from cwc.governance.materialization_transaction import sha256_file
from cwc.governance.mechanism_evidence_plan import MechanismStatisticalPlan
from cwc.governance.mechanism_trial_sizing import freeze_mechanism_trial_sizing

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOT = ROOT / "eval_bundle"
INPUT_SCHEMA = "DGC_MECHANISM_CALIBRATION_SUMMARY_V1"


def _path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def _output(value: str) -> Path:
    resolved = _path(value).resolve()
    try:
        resolved.relative_to(RUNTIME_ROOT.resolve())
    except ValueError as exc:
        raise ValueError("output must be inside ignored eval_bundle runtime root") from exc
    if resolved.exists():
        raise FileExistsError("mechanism sizing output is immutable")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Freeze calibration-only cluster-aware sizing for the two-endpoint DGC mechanism lane."
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    input_path = _path(args.input)
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema") != INPUT_SCHEMA:
        raise ValueError("wrong mechanism calibration summary schema")
    raw_rows = payload.get("observations")
    raw_effects = payload.get("effects_of_interest")
    if not isinstance(raw_rows, list) or not isinstance(raw_effects, dict):
        raise ValueError("mechanism calibration observations/effects missing")
    observations = tuple(
        CalibrationObservation(
            comparison_id=str(row["comparison_id"]),
            task_id=str(row["task_id"]),
            replicate=int(row["replicate"]),
            value=float(row["value"]),
        )
        for row in raw_rows
        if isinstance(row, dict)
    )
    if len(observations) != len(raw_rows):
        raise ValueError("invalid mechanism calibration observation row")

    receipt = freeze_mechanism_trial_sizing(
        observations=observations,
        effects_of_interest={str(k): float(v) for k, v in raw_effects.items()},
        confirmatory_task_count=int(payload["confirmatory_task_count"]),
        calibration_evidence_digest=sha256_file(input_path),
        plan=MechanismStatisticalPlan(),
    )
    output = _output(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(receipt.document, indent=2, sort_keys=True).encode("utf-8") + b"\n"
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    print(json.dumps({
        "status": "PASS",
        "output": str(output.relative_to(ROOT)),
        "plan_digest": receipt.plan_digest,
        "calibration_evidence_digest": receipt.calibration_evidence_digest,
        "required_trials_per_task": receipt.required_trials_per_task,
        "risk_qualification_authorized": False,
        "product_promotion_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
