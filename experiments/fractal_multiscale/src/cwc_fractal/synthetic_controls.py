from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any

from .robust import evaluate_robust_nulls, robust_coherence_report
from .types import CausalWindow, FeatureMapping, Scale, ScaleObservation


@dataclass(frozen=True, slots=True)
class SyntheticControlResult:
    name: str
    report: dict[str, Any]
    null_evaluation: dict[str, Any]
    passed_primary_gate: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "report": self.report,
            "null_evaluation": self.null_evaluation,
            "passed_primary_gate": self.passed_primary_gate,
        }


def _shape(timestamp: int) -> tuple[int, int]:
    batch_size = 3 + timestamp % 3
    sequence_length = 12 + 4 * (timestamp % 4)
    return batch_size, sequence_length


def _latent(timestamp: int) -> float:
    return (
        math.sin(timestamp * 0.37)
        + 0.55 * math.sin(timestamp * 0.11 + 0.7)
        + 0.25 * math.cos(timestamp * 0.71)
    )


def build_control_window(
    kind: str,
    *,
    length: int = 96,
    seed: int = 17,
) -> CausalWindow:
    if kind not in {"endogenous", "common_driver", "independent"}:
        raise ValueError(f"unknown control kind: {kind}")
    rng = random.Random(seed)
    observations: list[ScaleObservation] = []
    for timestamp in range(length):
        batch_size, sequence_length = _shape(timestamp)
        shape_effect = 0.35 * batch_size + 0.04 * sequence_length
        latent = _latent(timestamp)
        metadata = {
            "batch_size": batch_size,
            "sequence_length": sequence_length,
            "total_tokens": batch_size * sequence_length,
            "run_index": timestamp,
            "schema_version": "synthetic.control.v1",
        }
        if kind == "endogenous":
            micro_route = shape_effect + latent + rng.gauss(0.0, 0.06)
            micro_depth = -0.5 * shape_effect + 0.7 * latent + rng.gauss(0.0, 0.06)
            meso_util = 0.9 * shape_effect + 0.82 * latent + rng.gauss(0.0, 0.06)
            meso_mem = -0.4 * shape_effect + 0.62 * latent + rng.gauss(0.0, 0.06)
            meso_opint = 1.3 * shape_effect - 0.73 * latent + rng.gauss(0.0, 0.06)
            macro_latency = 0.2 * shape_effect + 0.68 * latent + rng.gauss(0.0, 0.08)
            macro_flops = 1.8 * shape_effect - 0.66 * latent + rng.gauss(0.0, 0.08)
        elif kind == "common_driver":
            micro_route = shape_effect + rng.gauss(0.0, 0.06)
            micro_depth = -0.5 * shape_effect + rng.gauss(0.0, 0.06)
            meso_util = 0.9 * shape_effect + rng.gauss(0.0, 0.06)
            meso_mem = -0.4 * shape_effect + rng.gauss(0.0, 0.06)
            meso_opint = 1.3 * shape_effect + rng.gauss(0.0, 0.06)
            macro_latency = 0.2 * shape_effect + rng.gauss(0.0, 0.08)
            macro_flops = 1.8 * shape_effect + rng.gauss(0.0, 0.08)
        else:
            micro_route = shape_effect + rng.gauss(0.0, 1.0)
            micro_depth = -0.5 * shape_effect + rng.gauss(0.0, 1.0)
            meso_util = 0.9 * shape_effect + rng.gauss(0.0, 1.0)
            meso_mem = -0.4 * shape_effect + rng.gauss(0.0, 1.0)
            meso_opint = 1.3 * shape_effect + rng.gauss(0.0, 1.0)
            macro_latency = 0.2 * shape_effect + rng.gauss(0.0, 1.0)
            macro_flops = 1.8 * shape_effect + rng.gauss(0.0, 1.0)
        observations.extend(
            (
                ScaleObservation(
                    timestamp=timestamp,
                    scale=Scale.MICRO,
                    source=f"synthetic:{kind}",
                    metadata=dict(metadata),
                    features={
                        "route_entropy_mean": micro_route,
                        "controller_depth_fraction": micro_depth,
                    },
                ),
                ScaleObservation(
                    timestamp=timestamp,
                    scale=Scale.MESO,
                    source=f"synthetic:{kind}",
                    metadata=dict(metadata),
                    features={
                        "expert_utilization_entropy": meso_util,
                        "controller_memory_read_fraction": meso_mem,
                        "operational_intensity": meso_opint,
                    },
                ),
                ScaleObservation(
                    timestamp=timestamp,
                    scale=Scale.MACRO,
                    source=f"synthetic:{kind}",
                    metadata=dict(metadata),
                    features={
                        "end_to_end_p95_ms": macro_latency,
                        "total_flops": macro_flops,
                    },
                ),
            )
        )
    return CausalWindow(end_timestamp=length - 1, observations=tuple(observations))


def evaluate_control(
    kind: str,
    *,
    mappings: tuple[FeatureMapping, ...],
    confounder_strata: tuple[str, ...],
    null_models: tuple[str, ...],
    iterations: int,
    seed: int,
    min_delta: float,
    max_p_value: float,
    min_valid_pair_fraction: float,
) -> SyntheticControlResult:
    window = build_control_window(kind, length=96, seed=seed)
    report = robust_coherence_report(
        window,
        mappings=mappings,
        confounder_strata=confounder_strata,
    )
    null_eval = evaluate_robust_nulls(
        window,
        mappings=mappings,
        confounder_strata=confounder_strata,
        null_models=null_models,
        iterations=iterations,
        seed=seed + 101,
        min_delta=min_delta,
        max_p_value=max_p_value,
    )
    enough_edges = set(report.required_edges).issubset(report.valid_edges)
    passed = (
        report.valid_pair_fraction >= min_valid_pair_fraction and enough_edges and null_eval.passed
    )
    return SyntheticControlResult(
        name=kind,
        report=report.to_dict(),
        null_evaluation=null_eval.to_dict(),
        passed_primary_gate=passed,
    )
