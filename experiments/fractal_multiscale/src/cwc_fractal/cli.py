from __future__ import annotations

import argparse
import json
from pathlib import Path

from .analyzer import FractalMultiscaleAnalyzer
from .cwc_adapter import observations_from_cwc_record
from .evaluation import evaluate_against_nulls
from .protocol import load_yaml, mappings_from_protocol, validate_protocol
from .types import CausalWindow, ScaleObservation

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROTOCOL = PACKAGE_ROOT / "experiments" / "cwc_fractal_protocol_v1.yaml"
DEFAULT_SCHEMA = PACKAGE_ROOT / "schemas" / "fractal_protocol.schema.json"


def main() -> None:
    parser = argparse.ArgumentParser(prog="cwc-fractal")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze-cwc-jsonl")
    analyze.add_argument("jsonl", type=Path)
    analyze.add_argument(
        "--protocol",
        type=Path,
        default=DEFAULT_PROTOCOL,
    )
    analyze.add_argument(
        "--schema",
        type=Path,
        default=DEFAULT_SCHEMA,
    )
    analyze.add_argument("--output", type=Path)
    analyze.add_argument("--end-timestamp", type=int)
    analyze.add_argument("--boundary-threshold", type=float, default=0.75)
    analyze.add_argument("--null-iterations", type=int, default=200)
    args = parser.parse_args()

    if args.command == "analyze-cwc-jsonl":
        protocol_errors = validate_protocol(args.protocol, args.schema)
        if protocol_errors:
            for error in protocol_errors:
                print(f"ERROR: {error}")
            raise SystemExit(1)
        protocol = load_yaml(args.protocol)
        mappings = mappings_from_protocol(protocol)
        observations: list[ScaleObservation] = []
        with args.jsonl.open(encoding="utf-8") as handle:
            for index, line in enumerate(handle):
                if not line.strip():
                    continue
                observations.extend(observations_from_cwc_record(json.loads(line), timestamp=index))
        end_timestamp = args.end_timestamp if args.end_timestamp is not None else len(observations)
        window = CausalWindow(end_timestamp=end_timestamp, observations=tuple(observations))
        report = FractalMultiscaleAnalyzer(
            mappings=mappings,
            boundary_threshold=args.boundary_threshold,
        ).analyze(window)
        counts_by_scale: dict[str, int] = {}
        for observation in observations:
            scale_key = observation.scale.value
            counts_by_scale[scale_key] = counts_by_scale.get(scale_key, 0) + 1
        sufficient_length = all(
            count >= int(protocol["minimum_series_length"]) for count in counts_by_scale.values()
        )
        null_evaluation = None
        if sufficient_length:
            gates = protocol["acceptance_gates"]
            null_evaluation = evaluate_against_nulls(
                window,
                mappings=mappings,
                iterations=args.null_iterations,
                min_delta=float(gates["min_coherence_delta_vs_null"]),
                max_p_value=float(gates["max_p_value"]),
            )
        if not sufficient_length:
            verdict = "INSUFFICIENT_SERIES_LENGTH"
        elif null_evaluation is not None and null_evaluation.passed:
            verdict = "PASS"
        else:
            verdict = "FAILED_NULL_GATE"

        payload_dict = {
            "schema_version": "cwc_fractal_evidence.v1",
            "protocol_id": protocol["protocol_id"],
            "input_jsonl": str(args.jsonl),
            "series_counts_by_scale": counts_by_scale,
            "minimum_series_length": protocol["minimum_series_length"],
            "sufficient_series_length": sufficient_length,
            "fractal_report": report.to_dict(),
            "null_evaluation": None if null_evaluation is None else null_evaluation.to_dict(),
            "verdict": verdict,
            "claim_boundary": protocol["claim_boundary"],
        }
        payload = json.dumps(payload_dict, ensure_ascii=False, indent=2) + "\n"
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(payload, encoding="utf-8")
        print(payload, end="")
        return


if __name__ == "__main__":
    main()
