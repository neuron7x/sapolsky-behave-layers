from __future__ import annotations

from typing import Any

from .types import Scale, ScaleObservation


def observations_from_cwc_record(
    record: dict[str, Any],
    *,
    timestamp: int,
) -> tuple[ScaleObservation, ...]:
    """Convert a CWC instrumentation JSON record into micro/meso/macro observations.

    This adapter intentionally accepts plain dictionaries so the fractal module stays separate from
    the main CWC package. The main project can feed `RunMeter` JSONL rows here without importing
    this package into its core runtime.
    """

    latency = record.get("latency", {})
    routing = record.get("routing", {})
    flops = record.get("flops", {})
    vram = record.get("vram", {})
    energy = record.get("energy", {})

    end_to_end = latency.get("end_to_end_ms", {})
    gpu_kernel = latency.get("gpu_kernel_ms", {})
    inference = latency.get("inference", {})

    micro = ScaleObservation(
        timestamp=timestamp,
        scale=Scale.MICRO,
        source="cwc.instrumentation",
        features={
            "gpu_kernel_p95_ms": float(gpu_kernel.get("p95", 0.0)),
            "ttft_p50_ms": float(inference.get("ttft_ms", {}).get("p50", 0.0)),
            "tpot_p50_ms": float(inference.get("tpot_ms", {}).get("p50", 0.0)),
            "active_token_fraction": float(routing.get("active_token_fraction_mean", 0.0)),
        },
    )
    meso = ScaleObservation(
        timestamp=timestamp,
        scale=Scale.MESO,
        source="cwc.instrumentation",
        features={
            "route_expert_fraction": float(routing.get("active_expert_fraction_mean", 0.0)),
            "operational_intensity": float(
                flops.get("operational_intensity_flops_per_byte", 0.0)
            ),
            "communication_bytes": float(flops.get("communication_bytes", 0.0)),
            "memory_bytes": float(flops.get("memory_bytes", 0.0)),
        },
    )
    macro = ScaleObservation(
        timestamp=timestamp,
        scale=Scale.MACRO,
        source="cwc.instrumentation",
        features={
            "end_to_end_p95_ms": float(end_to_end.get("p95", 0.0)),
            "total_flops": float(flops.get("total_flops", 0.0)),
            "peak_vram_bytes": float(vram.get("peak_allocated_bytes", 0.0)),
            "joules": float(energy.get("joules", 0.0)),
        },
    )
    return micro, meso, macro
