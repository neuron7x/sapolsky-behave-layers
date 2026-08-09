from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
PKG_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PKG_SRC) not in sys.path:
    sys.path.insert(0, str(PKG_SRC))

from cwc_fractal.cwc_adapter import observations_from_cwc_record  # noqa: E402
from cwc_fractal.robust import evaluate_robust_nulls, robust_coherence_report  # noqa: E402
from cwc_fractal.robust_protocol import (  # noqa: E402
    load_yaml,
    robust_mappings,
    validate_robust_protocol,
)
from cwc_fractal.types import CausalWindow, ScaleObservation  # noqa: E402

DEFAULT_PROTOCOL = Path(__file__).resolve().parents[1] / "experiments" / "cwc_fractal_protocol_v2.yaml"
DEFAULT_SCHEMA = Path(__file__).resolve().parents[1] / "schemas" / "fractal_protocol_v2.schema.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _load_jsonl(path: Path) -> tuple[list[dict[str, Any]], tuple[ScaleObservation, ...]]:
    records: list[dict[str, Any]] = []
    observations: list[ScaleObservation] = []
    with path.open(encoding="utf-8") as handle:
        for index, line in enumerate(handle):
            if not line.strip():
                continue
            record = json.loads(line)
            if not isinstance(record, dict):
                raise SystemExit(f"line {index + 1}: record must be an object")
            records.append(record)
            observations.extend(observations_from_cwc_record(record, timestamp=len(records) - 1))
    return records, tuple(observations)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("jsonl", type=Path)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260810)
    args = parser.parse_args()

    errors = validate_robust_protocol(args.protocol, args.schema)
    if errors:
        raise SystemExit("\n".join(f"PROTOCOL_ERROR: {error}" for error in errors))
    protocol = load_yaml(args.protocol)
    mappings = robust_mappings(protocol)
    records, observations = _load_jsonl(args.jsonl)
    if not records:
        raise SystemExit("input JSONL is empty")
    end_timestamp = len(records) - 1
    window = CausalWindow(end_timestamp=end_timestamp, observations=observations)
    counts: dict[str, int] = {}
    for observation in observations:
        counts[observation.scale.value] = counts.get(observation.scale.value, 0) + 1

    report = robust_coherence_report(
        window,
        mappings=mappings,
        confounder_strata=protocol["confounder_strata"],
    )
    gates = protocol["acceptance_gates"]
    enough_length = all(
        counts.get(scale, 0) >= int(protocol["minimum_series_length"])
        for scale in protocol["scales"]
    )
    enough_pairs = report.valid_pair_fraction >= float(gates["min_valid_pair_fraction"])
    enough_edges = set(report.required_edges).issubset(report.valid_edges)

    null_evaluation = None
    if enough_length and enough_pairs and enough_edges:
        null_evaluation = evaluate_robust_nulls(
            window,
            mappings=mappings,
            confounder_strata=protocol["confounder_strata"],
            null_models=protocol["null_models"],
            iterations=int(protocol["null_iterations"]),
            seed=args.seed,
            min_delta=float(gates["min_residual_delta_vs_max_null"]),
            max_p_value=float(gates["max_familywise_p_value"]),
        )

    if not enough_length:
        verdict = "INSUFFICIENT_SERIES_LENGTH"
    elif not enough_pairs or not enough_edges:
        verdict = "MULTISCALE_ORGANIZATION_NOT_IDENTIFIABLE_UNDER_CURRENT_INSTRUMENTATION"
    elif null_evaluation is None or not null_evaluation.passed:
        verdict = "RESIDUAL_MULTISCALE_ORGANIZATION_NOT_SUPPORTED"
    else:
        # Synthetic control calibration is evaluated by the orchestration experiment, not by a
        # single-trace CLI invocation. A single trace therefore cannot independently authorize PASS.
        verdict = "TRACE_STATISTICAL_GATE_PASS_PENDING_SYNTHETIC_CONTROL_CALIBRATION"

    payload = {
        "schema_version": "cwc_fractal_robust_evidence.v2",
        "protocol_id": protocol["protocol_id"],
        "input": str(args.jsonl),
        "input_sha256": sha256(args.jsonl),
        "record_count": len(records),
        "series_counts_by_scale": counts,
        "minimum_series_length": protocol["minimum_series_length"],
        "coherence": report.to_dict(),
        "null_evaluation": None if null_evaluation is None else null_evaluation.to_dict(),
        "gates": {
            "enough_series_length": enough_length,
            "valid_pair_fraction": report.valid_pair_fraction,
            "min_valid_pair_fraction": gates["min_valid_pair_fraction"],
            "all_required_edges_valid": enough_edges,
        },
        "verdict": verdict,
        "claim_boundary": protocol["claim_boundary"],
        "scientific_ascension_authority": False,
        "via_authority": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
