import json
import sys
from pathlib import Path

import yaml

from cwc_fractal.cli import main
from cwc_fractal.evaluation import evaluate_against_nulls
from cwc_fractal.protocol import mappings_from_protocol, validate_protocol
from cwc_fractal.types import CausalWindow, Scale, ScaleObservation

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "experiments" / "cwc_fractal_protocol_v1.yaml"
SCHEMA = ROOT / "schemas" / "fractal_protocol.schema.json"


def test_frozen_protocol_passes_semantic_validation() -> None:
    assert validate_protocol(PROTOCOL, SCHEMA) == []


def test_protocol_rejects_self_scale_mapping(tmp_path: Path) -> None:
    payload = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    payload["feature_mappings"][0]["target_scale"] = "micro"
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(payload), encoding="utf-8")

    errors = validate_protocol(path, SCHEMA)
    assert any("self-scale mapping" in error for error in errors)


def test_null_evaluation_detects_strong_cross_scale_signal() -> None:
    observations: list[ScaleObservation] = []
    for ts in range(32):
        base = float(ts)
        observations.append(
            ScaleObservation(
                timestamp=ts,
                scale=Scale.MICRO,
                features={"active_token_fraction": base, "gpu_kernel_p95_ms": base * 2},
            )
        )
        observations.append(
            ScaleObservation(
                timestamp=ts,
                scale=Scale.MESO,
                features={
                    "route_expert_fraction": base,
                    "operational_intensity": base * 2,
                    "memory_bytes": base * 3,
                },
            )
        )
        observations.append(
            ScaleObservation(
                timestamp=ts,
                scale=Scale.MACRO,
                features={"total_flops": base * 2, "peak_vram_bytes": base * 3},
            )
        )
    protocol = yaml.safe_load(PROTOCOL.read_text(encoding="utf-8"))
    result = evaluate_against_nulls(
        CausalWindow(end_timestamp=31, observations=tuple(observations)),
        mappings=mappings_from_protocol(protocol),
        iterations=50,
        seed=3,
        min_delta=0.01,
        max_p_value=0.10,
    )

    assert result.delta > 0.0
    assert result.empirical_p_value <= 1.0


def test_cli_short_series_is_insufficient_evidence(tmp_path: Path) -> None:
    record = {
        "latency": {
            "end_to_end_ms": {"p95": 7.0},
            "gpu_kernel_ms": {"p95": 3.0},
            "inference": {"ttft_ms": {"p50": 1.0}, "tpot_ms": {"p50": 2.0}},
        },
        "routing": {"active_token_fraction_mean": 0.5, "active_expert_fraction_mean": 0.25},
        "flops": {
            "total_flops": 1000,
            "memory_bytes": 100,
            "communication_bytes": 20,
            "operational_intensity_flops_per_byte": 8.0,
        },
        "vram": {"peak_allocated_bytes": 64},
        "energy": {"joules": 0.1},
    }
    jsonl = tmp_path / "metrics.jsonl"
    jsonl.write_text(json.dumps(record) + "\n", encoding="utf-8")
    output = tmp_path / "evidence.json"

    old_argv = sys.argv
    try:
        sys.argv = [
            "cwc-fractal",
            "analyze-cwc-jsonl",
            str(jsonl),
            "--protocol",
            str(PROTOCOL),
            "--schema",
            str(SCHEMA),
            "--output",
            str(output),
        ]
        main()
    finally:
        sys.argv = old_argv

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["verdict"] == "INSUFFICIENT_SERIES_LENGTH"
    assert payload["sufficient_series_length"] is False
    assert payload["null_evaluation"] is None
