"""Shared record types. Every field name carries its unit suffix
(_ns, _ms, _sec, _bytes, _joules, _watts, _flops, _tokens) per Act 4.2 —
no bare `lat`, `mem`, `energy` fields.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class RunIdentity:
    run_id: str
    created_at_utc: str
    git_commit: str
    git_branch: str
    git_dirty: bool
    command_line: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DeviceManifest:
    cuda_available: bool
    device_name: str | None
    cuda_runtime_version: str | None
    driver_version: str | None
    total_vram_bytes: int


@dataclass(frozen=True, slots=True)
class EnvironmentManifest:
    python_version: str
    torch_version: str
    cuda_runtime_version: str | None
    os_name: str
    hostname_hash: str
    ddp_world_size: int
    ddp_rank: int
    compile_state: str
    attention_backend: str
    environment_match: bool
    expected_torch_version: str


@dataclass(frozen=True, slots=True)
class LatencyRecord:
    scope_name: str
    step: int
    status: str  # "ok" | "error"
    end_to_end_ms: float
    gpu_kernel_ms: float
    tokens: int | None = None
    error_type: str | None = None


@dataclass(frozen=True, slots=True)
class VRAMRecord:
    scope_name: str
    device: str
    start_allocated_bytes: int
    start_reserved_bytes: int
    peak_allocated_bytes: int
    peak_reserved_bytes: int
    end_allocated_bytes: int
    end_reserved_bytes: int

    @property
    def delta_allocated_bytes(self) -> int:
        return self.end_allocated_bytes - self.start_allocated_bytes


@dataclass(frozen=True, slots=True)
class EnergyRecord:
    available: bool
    method: str
    sample_count: int
    duration_sec: float
    joules: float
    average_watts: float
    confidence: str  # "high" | "low_confidence" | "unavailable"


@dataclass(frozen=True, slots=True)
class FlopRecord:
    name: str
    kind: str
    logical_flops: int
    executed_estimate_flops: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class RoutingAggregate:
    step_count: int
    active_tokens_sum: int
    active_tokens_min: int
    active_tokens_max: int
    active_blocks_sum: int
    active_experts_sum: int
    active_experts_min: int
    active_experts_max: int
    active_parameters_sum: int
    dropped_tokens_sum: int
    padded_tokens_sum: int
    entropy_mean: float | None
    dropped_trace_count: int = 0


@dataclass(frozen=True, slots=True)
class OverheadResult:
    off_p50_ms: float
    off_p95_ms: float
    off_p99_ms: float
    counters_p50_ms: float
    counters_p95_ms: float
    counters_p99_ms: float
    relative_overhead_fraction: float
    ci_lower_fraction: float
    ci_upper_fraction: float
    sample_count: int
    cycles: int
    gate_passed: bool
    max_overhead_fraction: float
    max_overhead_ci_fraction: float


@dataclass(frozen=True, slots=True)
class InstrumentationSummary:
    schema_version: str
    run: dict[str, Any]
    environment: dict[str, Any]
    model: dict[str, Any]
    workload: dict[str, Any]
    instrumentation: dict[str, Any]
    latency: dict[str, Any]
    throughput: dict[str, Any]
    vram: dict[str, Any]
    flops: dict[str, Any]
    energy: dict[str, Any]
    routing: dict[str, Any]
    validity: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run": self.run,
            "environment": self.environment,
            "model": self.model,
            "workload": self.workload,
            "instrumentation": self.instrumentation,
            "latency": self.latency,
            "throughput": self.throughput,
            "vram": self.vram,
            "flops": self.flops,
            "energy": self.energy,
            "routing": self.routing,
            "validity": self.validity,
        }
