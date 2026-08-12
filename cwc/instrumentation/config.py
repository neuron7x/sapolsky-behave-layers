"""WP-1 instrumentation configuration: immutable, fail-closed on unknown fields.

InstrumentationMode.OFF is the default and must remain a true no-op everywhere
else in this package — see noop.py and the Act's Gate B (mathematical
neutrality). Unknown constructor fields raise TypeError for free because this
is a slotted dataclass, satisfying the Act 4.1 "unknown fields fail closed"
requirement without extra code.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class InstrumentationMode(str, Enum):
    OFF = "off"
    COUNTERS = "counters"
    TRACE = "trace"
    AUDIT = "audit"


def _cuda_available() -> bool:
    try:
        import torch
    except ImportError:
        return False
    return bool(torch.cuda.is_available())


@dataclass(frozen=True, slots=True)
class InstrumentationConfig:
    mode: InstrumentationMode = InstrumentationMode.OFF
    output_dir: Path | None = None
    run_id: str | None = None
    sample_rate_hz: float = 10.0
    trace_every_n_steps: int = 0
    trace_buffer_records: int = 4096
    event_pool_size: int = 256
    warmup_steps: int = 20
    measurement_steps: int = 100
    energy_min_window_sec: float = 5.0
    enable_cuda_events: bool = True
    enable_vram: bool = True
    enable_energy: bool = False
    enable_flops: bool = True
    # Energy on this programme's hardware is INSTRUMENT_INVALID (uncalibrated
    # consumer-GPU NVML power). Enabling energy therefore requires the caller to
    # explicitly affirm that the reading must never enter a claim aggregate. This
    # turns "operator discipline" into a fail-closed code gate (see __post_init__).
    energy_instrument_invalid_ack: bool = False

    def __post_init__(self) -> None:
        if self.sample_rate_hz <= 0:
            raise ValueError("sample_rate_hz must be > 0")
        if self.trace_buffer_records <= 0:
            raise ValueError("trace_buffer_records must be > 0")
        if self.event_pool_size <= 0:
            raise ValueError("event_pool_size must be > 0")
        if self.warmup_steps < 0:
            raise ValueError("warmup_steps cannot be negative")
        if self.measurement_steps <= 0:
            raise ValueError("measurement_steps must be > 0")
        if self.energy_min_window_sec <= 0:
            raise ValueError("energy_min_window_sec must be > 0")

        needs_output = self.mode in (
            InstrumentationMode.COUNTERS,
            InstrumentationMode.TRACE,
            InstrumentationMode.AUDIT,
        )
        if needs_output and self.output_dir is None:
            raise ValueError(f"mode={self.mode.value} requires a writable output_dir")
        if self.output_dir is not None and self.output_dir.exists() and not self.output_dir.is_dir():
            raise ValueError(f"output_dir exists and is not a directory: {self.output_dir}")

        if self.mode == InstrumentationMode.TRACE and self.trace_every_n_steps <= 0:
            raise ValueError("TRACE mode requires trace_every_n_steps > 0")

        if self.enable_energy and not _cuda_available():
            raise ValueError("energy cannot be enabled without CUDA available")
        if self.enable_energy and not self.energy_instrument_invalid_ack:
            raise ValueError(
                "energy is INSTRUMENT_INVALID on this programme's hardware "
                "(uncalibrated consumer-GPU NVML power); enabling it requires "
                "energy_instrument_invalid_ack=True to affirm the reading must "
                "never enter a claim aggregate"
            )

    @property
    def is_off(self) -> bool:
        return self.mode == InstrumentationMode.OFF
