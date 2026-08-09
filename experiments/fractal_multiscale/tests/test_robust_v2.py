from __future__ import annotations

import json
from pathlib import Path

from cwc_fractal.cwc_adapter import observations_from_cwc_record
from cwc_fractal.robust import (
    evaluate_robust_nulls,
    normalized_entropy,
    robust_coherence_report,
    spearman,
)
from cwc_fractal.robust_protocol import load_yaml, robust_mappings, validate_robust_protocol
from cwc_fractal.synthetic_controls import build_control_window

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL = ROOT / "experiments" / "cwc_fractal_protocol_v2.yaml"
SCHEMA = ROOT / "schemas" / "fractal_protocol_v2.schema.json"


def test_spearman_ties_and_monotonicity() -> None:
    assert abs(spearman([1, 2, 2, 4], [10, 20, 20, 40]) - 1.0) < 1e-12
    assert abs(spearman([1, 2, 3, 4], [4, 3, 2, 1]) + 1.0) < 1e-12


def test_normalized_entropy_extremes() -> None:
    assert normalized_entropy([1, 0, 0, 0]) == 0.0
    assert abs(normalized_entropy([1, 1, 1, 1]) - 1.0) < 1e-12


def test_robust_protocol_v2_is_frozen_and_valid() -> None:
    assert validate_robust_protocol(PROTOCOL, SCHEMA) == []


def test_common_driver_is_removed_by_exact_shape_residualization() -> None:
    protocol = load_yaml(PROTOCOL)
    report = robust_coherence_report(
        build_control_window("common_driver", length=96, seed=3),
        mappings=robust_mappings(protocol),
        confounder_strata=protocol["confounder_strata"],
    )
    assert report.raw_mean_abs_coherence is not None
    assert report.residual_mean_abs_coherence is not None
    assert report.raw_mean_abs_coherence > report.residual_mean_abs_coherence


def test_endogenous_control_separates_from_robust_nulls() -> None:
    protocol = load_yaml(PROTOCOL)
    mappings = robust_mappings(protocol)
    result = evaluate_robust_nulls(
        build_control_window("endogenous", length=96, seed=11),
        mappings=mappings,
        confounder_strata=protocol["confounder_strata"],
        null_models=protocol["null_models"],
        iterations=300,
        seed=22,
        min_delta=0.10,
        max_p_value=0.05,
    )
    assert result.passed
    assert result.familywise_p_value is not None
    assert result.familywise_p_value <= 0.05


def test_independent_control_does_not_pass_robust_nulls() -> None:
    protocol = load_yaml(PROTOCOL)
    mappings = robust_mappings(protocol)
    result = evaluate_robust_nulls(
        build_control_window("independent", length=96, seed=19),
        mappings=mappings,
        confounder_strata=protocol["confounder_strata"],
        null_models=protocol["null_models"],
        iterations=300,
        seed=29,
        min_delta=0.10,
        max_p_value=0.05,
    )
    assert not result.passed


def test_adapter_preserves_shape_and_richer_routing_telemetry() -> None:
    record = {
        "run_index": 7,
        "config": {"batch_size": 3, "sequence_length": 12},
        "latency": {
            "end_to_end_ms": {"p95": 2.0},
            "gpu_kernel_ms": {"p95": 1.0},
            "inference": {"ttft_ms": {"p50": 2.0}, "tpot_ms": {"p50": 0.2}},
        },
        "routing": {
            "active_token_fraction_mean": 0.5,
            "active_expert_fraction_mean": 1.0,
            "events": [
                {
                    "metadata": {
                        "route_entropy_mean": 0.6,
                        "expert_utilization": [0.5, 0.25, 0.25, 0.0],
                        "controller_depth_fraction": 0.4,
                        "controller_memory_read_fraction": 0.1,
                    }
                }
            ],
        },
        "flops": {
            "total_flops": 1000,
            "memory_bytes": 100,
            "communication_bytes": 20,
            "operational_intensity_flops_per_byte": 8.0,
            "entries": [{"name": "local-global-attention", "metadata": {"density": 0.3}}],
        },
        "vram": {"peak_allocated_bytes": 64},
        "energy": {"joules": 0.1},
    }
    micro, meso, macro = observations_from_cwc_record(record, timestamp=7)
    assert micro.metadata["batch_size"] == 3
    assert micro.metadata["sequence_length"] == 12
    assert micro.features["route_entropy_mean"] == 0.6
    assert micro.features["controller_depth_fraction"] == 0.4
    assert 0.0 < meso.features["expert_utilization_entropy"] < 1.0
    assert meso.features["controller_memory_read_fraction"] == 0.1
    assert meso.features["attention_density"] == 0.3
    assert macro.features["total_flops"] == 1000.0


def test_cross_seed_pair_diagnostics_reports_sign_consistency() -> None:
    from cwc_fractal.replication import cross_seed_pair_diagnostics

    rows = {
        "1": [{"edge": "micro->meso", "source_feature": "x", "target_feature": "y", "n": 72, "residual_spearman": 0.2}],
        "2": [{"edge": "micro->meso", "source_feature": "x", "target_feature": "y", "n": 72, "residual_spearman": -0.1}],
        "3": [{"edge": "micro->meso", "source_feature": "x", "target_feature": "y", "n": 72, "residual_spearman": 0.3}],
    }
    out = cross_seed_pair_diagnostics(rows)
    assert len(out) == 1
    assert out[0]["valid_seed_count"] == 3
    assert out[0]["sign_consistency_fraction"] == 2 / 3
    assert out[0]["range"] == [-0.1, 0.3]
