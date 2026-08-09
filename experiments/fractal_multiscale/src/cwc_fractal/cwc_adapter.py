from __future__ import annotations

import math
from typing import Any

from .robust import normalized_entropy
from .types import Scale, ScaleObservation


def _float(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _routing_event(record: dict[str, Any]) -> dict[str, Any]:
    events = record.get("routing", {}).get("events", [])
    if not isinstance(events, list) or not events:
        return {}
    event = events[-1]
    return event if isinstance(event, dict) else {}


def _flop_entry(record: dict[str, Any], name: str) -> dict[str, Any]:
    entries = record.get("flops", {}).get("entries", [])
    if not isinstance(entries, list):
        return {}
    for entry in entries:
        if isinstance(entry, dict) and entry.get("name") == name:
            return entry
    return {}


def observations_from_cwc_record(
    record: dict[str, Any],
    *,
    timestamp: int,
) -> tuple[ScaleObservation, ...]:
    """Convert one CWC/CWK instrumentation row into explicit diagnostic levels.

    The adapter preserves run-shape metadata on every level. Robust v2 analysis uses this metadata
    for exact repeated-shape residualization rather than treating shared batch/sequence scaling as
    endogenous cross-level organization.

    Level labels here are *diagnostic subsystem levels*, not proof of a fractal hierarchy:

    - micro: controller/routing state local to a run;
    - meso: routed/execution-subsystem state;
    - macro: end-to-end resource/performance state.
    """

    latency = record.get("latency", {})
    routing = record.get("routing", {})
    flops = record.get("flops", {})
    vram = record.get("vram", {})
    energy = record.get("energy", {})
    config = record.get("config", {}) if isinstance(record.get("config", {}), dict) else {}

    end_to_end = latency.get("end_to_end_ms", {})
    gpu_kernel = latency.get("gpu_kernel_ms", {})
    inference = latency.get("inference", {})
    event = _routing_event(record)
    event_metadata = event.get("metadata", {}) if isinstance(event.get("metadata", {}), dict) else {}
    attention_entry = _flop_entry(record, "local-global-attention")
    attention_metadata = (
        attention_entry.get("metadata", {})
        if isinstance(attention_entry.get("metadata", {}), dict)
        else {}
    )

    batch_size = int(config.get("batch_size", 0) or 0)
    sequence_length = int(config.get("sequence_length", 0) or 0)
    shared_metadata = {
        "batch_size": batch_size,
        "sequence_length": sequence_length,
        "total_tokens": batch_size * sequence_length,
        "run_index": int(record.get("run_index", timestamp)),
        "schema_version": str(record.get("schema_version", "unknown")),
    }

    utilization = event_metadata.get("expert_utilization")
    if isinstance(utilization, list) and utilization:
        expert_utilization_entropy = normalized_entropy([_float(value) for value in utilization])
    else:
        # v1 traces did not preserve the vector. A scalar active-expert fraction is not a substitute.
        expert_utilization_entropy = 0.0

    micro = ScaleObservation(
        timestamp=timestamp,
        scale=Scale.MICRO,
        source="cwc.instrumentation",
        metadata=dict(shared_metadata),
        features={
            "gpu_kernel_p95_ms": _float(gpu_kernel.get("p95", 0.0)),
            "ttft_p50_ms": _float(inference.get("ttft_ms", {}).get("p50", 0.0)),
            "tpot_p50_ms": _float(inference.get("tpot_ms", {}).get("p50", 0.0)),
            "active_token_fraction": _float(routing.get("active_token_fraction_mean", 0.0)),
            "route_entropy_mean": _float(event_metadata.get("route_entropy_mean", 0.0)),
            "controller_depth_fraction": _float(
                event_metadata.get("controller_depth_fraction", 0.0)
            ),
        },
    )
    meso = ScaleObservation(
        timestamp=timestamp,
        scale=Scale.MESO,
        source="cwc.instrumentation",
        metadata=dict(shared_metadata),
        features={
            "route_expert_fraction": _float(routing.get("active_expert_fraction_mean", 0.0)),
            "expert_utilization_entropy": expert_utilization_entropy,
            "controller_memory_read_fraction": _float(
                event_metadata.get("controller_memory_read_fraction", 0.0)
            ),
            "attention_density": _float(attention_metadata.get("density", 0.0)),
            "operational_intensity": _float(
                flops.get("operational_intensity_flops_per_byte", 0.0)
            ),
            "communication_bytes": _float(flops.get("communication_bytes", 0.0)),
            "memory_bytes": _float(flops.get("memory_bytes", 0.0)),
        },
    )
    macro = ScaleObservation(
        timestamp=timestamp,
        scale=Scale.MACRO,
        source="cwc.instrumentation",
        metadata=dict(shared_metadata),
        features={
            "end_to_end_p95_ms": _float(end_to_end.get("p95", 0.0)),
            "total_flops": _float(flops.get("total_flops", 0.0)),
            "peak_vram_bytes": _float(vram.get("peak_allocated_bytes", 0.0)),
            "joules": _float(energy.get("joules", 0.0)),
        },
    )
    return micro, meso, macro
