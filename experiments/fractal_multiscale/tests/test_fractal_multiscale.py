import json
import sys
from pathlib import Path

import pytest

from cwc_fractal import (
    CausalWindow,
    FeatureMapping,
    FractalMultiscaleAnalyzer,
    FractalValidationError,
    Scale,
    ScaleObservation,
    compute_fractal_metrics,
    observations_from_cwc_record,
)
from cwc_fractal.cli import main


def _observations() -> tuple[ScaleObservation, ...]:
    observations: list[ScaleObservation] = []
    for ts in range(1, 10):
        observations.append(
            ScaleObservation(
                timestamp=ts,
                scale=Scale.MICRO,
                features={
                    "active_token_fraction": ts / 10,
                    "gpu_kernel_p95_ms": float(ts % 3 + 1),
                },
            )
        )
        observations.append(
            ScaleObservation(
                timestamp=ts,
                scale=Scale.MESO,
                features={
                    "route_expert_fraction": ts / 20,
                    "operational_intensity": float(ts * 2),
                    "memory_bytes": float(ts * 100),
                },
            )
        )
        observations.append(
            ScaleObservation(
                timestamp=ts,
                scale=Scale.MACRO,
                features={
                    "total_flops": float(ts * 1000),
                    "peak_vram_bytes": float(ts * 100),
                    "end_to_end_p95_ms": float(ts),
                },
            )
        )
    return tuple(observations)


def test_fractal_metrics_are_finite_for_nontrivial_series() -> None:
    metrics = compute_fractal_metrics([1, 2, 1, 3, 2, 5, 3, 8, 5, 13])

    assert metrics.box_dimension > 0.0
    assert 0.0 < metrics.hurst < 2.0
    assert metrics.roughness > 0.0
    assert set(metrics.multiscale_entropy) == {1, 2, 4}


def test_analyzer_requires_explicit_cross_scale_mappings() -> None:
    with pytest.raises(FractalValidationError):
        FractalMultiscaleAnalyzer(mappings=())


def test_analyzer_produces_micro_meso_macro_report_without_self_coherence() -> None:
    mappings = (
        FeatureMapping(
            Scale.MICRO,
            Scale.MESO,
            (
                ("active_token_fraction", "route_expert_fraction"),
                ("gpu_kernel_p95_ms", "operational_intensity"),
            ),
        ),
        FeatureMapping(
            Scale.MESO,
            Scale.MACRO,
            (
                ("operational_intensity", "total_flops"),
                ("memory_bytes", "peak_vram_bytes"),
            ),
        ),
    )
    report = FractalMultiscaleAnalyzer(mappings=mappings).analyze(
        CausalWindow(end_timestamp=9, observations=_observations())
    )

    payload = report.to_dict()
    assert payload["status"] == "ok"
    assert set(payload["scale_reports"]) == {"micro", "meso", "macro"}
    edges = {
        (item["source_scale"], item["target_scale"])
        for item in payload["cross_scale_reports"]
    }
    assert edges == {("micro", "meso"), ("meso", "macro")}
    assert ("macro", "macro") not in edges
    assert payload["interpretation"] == "multiscale_diagnostic_not_capability_claim"


def test_missing_semantic_mapping_field_is_rejected() -> None:
    mapping = FeatureMapping(Scale.MICRO, Scale.MESO, (("missing", "route_expert_fraction"),))
    analyzer = FractalMultiscaleAnalyzer(mappings=(mapping,))

    with pytest.raises(FractalValidationError):
        analyzer.analyze(CausalWindow(end_timestamp=9, observations=_observations()))


def test_causal_window_rejects_future_observations() -> None:
    with pytest.raises(FractalValidationError):
        CausalWindow(
            end_timestamp=1,
            observations=(
                ScaleObservation(
                    timestamp=2,
                    scale=Scale.MICRO,
                    features={"active_token_fraction": 1.0},
                ),
            ),
        )


def test_cwc_adapter_converts_instrumentation_json_without_main_package_import() -> None:
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
    observations = observations_from_cwc_record(record, timestamp=10)

    assert [item.scale for item in observations] == [Scale.MICRO, Scale.MESO, Scale.MACRO]
    assert observations[0].features["ttft_p50_ms"] == 1.0
    assert observations[1].features["operational_intensity"] == 8.0
    assert observations[2].features["total_flops"] == 1000.0


def test_analyzer_accepts_short_instrumentation_series_as_partial_diagnostic() -> None:
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
    observations = observations_from_cwc_record(record, timestamp=0)
    analyzer = FractalMultiscaleAnalyzer(
        mappings=(
            FeatureMapping(
                Scale.MICRO,
                Scale.MESO,
                (("active_token_fraction", "route_expert_fraction"),),
            ),
        )
    )
    report = analyzer.analyze(CausalWindow(end_timestamp=0, observations=observations))

    assert report.status == "ok"
    assert report.scale_reports[Scale.MICRO].aggregate_pressure == 0.0


def test_cli_analyzes_cwc_jsonl(tmp_path: Path) -> None:
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
    jsonl.write_text("\n".join(json.dumps(record) for _ in range(3)) + "\n", encoding="utf-8")
    output = tmp_path / "report.json"

    old_argv = sys.argv
    try:
        sys.argv = ["cwc-fractal", "analyze-cwc-jsonl", str(jsonl), "--output", str(output)]
        main()
    finally:
        sys.argv = old_argv

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "cwc_fractal_evidence.v1"
    assert payload["fractal_report"]["status"] == "ok"
    assert payload["fractal_report"]["cross_scale_reports"]
    assert payload["verdict"] == "INSUFFICIENT_SERIES_LENGTH"
