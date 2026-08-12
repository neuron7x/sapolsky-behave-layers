from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parents[1]
SRC = PKG_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from cwc_fractal.robust_protocol import (  # noqa: E402
    load_yaml,
    robust_mappings,
    validate_robust_protocol,
)
from cwc_fractal.synthetic_controls import evaluate_control  # noqa: E402

DEFAULT_PROTOCOL = PKG_ROOT / "experiments" / "cwc_fractal_protocol_v2.yaml"
DEFAULT_SCHEMA = PKG_ROOT / "schemas" / "fractal_protocol_v2.schema.json"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=314159)
    args = parser.parse_args()
    errors = validate_robust_protocol(args.protocol, args.schema)
    if errors:
        raise SystemExit("\n".join(errors))
    protocol = load_yaml(args.protocol)
    mappings = robust_mappings(protocol)
    gates = protocol["acceptance_gates"]
    results = {}
    for offset, kind in enumerate(("endogenous", "common_driver", "independent")):
        result = evaluate_control(
            kind,
            mappings=mappings,
            confounder_strata=tuple(protocol["confounder_strata"]),
            null_models=tuple(protocol["null_models"]),
            iterations=int(protocol["null_iterations"]),
            seed=args.seed + offset * 1000,
            min_delta=float(gates["min_residual_delta_vs_max_null"]),
            max_p_value=float(gates["max_familywise_p_value"]),
            min_valid_pair_fraction=float(gates["min_valid_pair_fraction"]),
        )
        results[kind] = result.to_dict()
    calibration_pass = (
        results["endogenous"]["passed_primary_gate"] is True
        and results["common_driver"]["passed_primary_gate"] is False
        and results["independent"]["passed_primary_gate"] is False
    )
    payload = {
        "schema_version": "cwc.fractal.synthetic_controls.v2",
        "protocol_id": protocol["protocol_id"],
        "results": results,
        "calibration_pass": calibration_pass,
        "verdict": "SYNTHETIC_CONTROL_CALIBRATION_PASS"
        if calibration_pass
        else "SYNTHETIC_CONTROL_CALIBRATION_FAIL",
        "claim_boundary": "Synthetic controls validate the statistic/gate behavior only; they do not validate CWC runtime organization.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))
    if not calibration_pass:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
