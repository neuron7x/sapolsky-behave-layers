"""Singleton no-op implementations used when InstrumentationMode.OFF.

None of these classes import NVML, create torch.cuda.Event objects, open
files, or start threads. Their overhead must be statistically indistinguishable
from calling the wrapped code directly (Act 4.3, Gate B).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .types import EnergyRecord, FlopRecord, RoutingAggregate, VRAMRecord


class NullRunMeter:
    """No-op stand-in for RunMeter. scope()/measure_step() run the wrapped code
    and nothing else: no CPU clock reads, no CUDA events, no record buffering.
    """

    __slots__ = ()

    @contextmanager
    def scope(self, name: str, *, step: int | None = None, tokens: int | None = None) -> Iterator[None]:
        yield

    def measure_step(self, fn: Callable[[], Any], *, step: int) -> Any:
        return fn()

    def resolve(self) -> None:
        return None

    def flush(self) -> None:
        return None

    def close(self) -> None:
        return None


class NullVRAMMeter:
    __slots__ = ()

    def reset_peak(self) -> None:
        return None

    def snapshot(self) -> VRAMRecord | None:
        return None


class NullEnergySampler:
    __slots__ = ()

    def start(self) -> None:
        return None

    def stop(self) -> EnergyRecord:
        return EnergyRecord(
            available=False,
            method="disabled",
            sample_count=0,
            duration_sec=0.0,
            joules=0.0,
            average_watts=0.0,
            confidence="unavailable",
        )


class NullFlopLedger:
    __slots__ = ()

    def add(self, *args: Any, **kwargs: Any) -> FlopRecord | None:
        return None

    @property
    def total_logical_flops(self) -> int:
        return 0

    @property
    def total_executed_estimate_flops(self) -> int:
        return 0

    def to_dict(self) -> dict[str, Any]:
        return {"enabled": False}


class NullRoutingCounters:
    __slots__ = ()

    def record(self, **kwargs: Any) -> None:
        return None

    def snapshot(self) -> RoutingAggregate:
        return RoutingAggregate(
            step_count=0,
            active_tokens_sum=0,
            active_tokens_min=0,
            active_tokens_max=0,
            active_blocks_sum=0,
            active_experts_sum=0,
            active_experts_min=0,
            active_experts_max=0,
            active_parameters_sum=0,
            dropped_tokens_sum=0,
            padded_tokens_sum=0,
            entropy_mean=None,
        )


class NullWriter:
    __slots__ = ()

    def write_metric(self, record: dict[str, Any]) -> None:
        return None

    def write_summary(self, summary: dict[str, Any]) -> None:
        return None

    def close(self) -> None:
        return None

    @property
    def output_dir(self) -> Path | None:
        return None
