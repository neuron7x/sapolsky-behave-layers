"""Measurement-ready routing counters (Act 4.10). WP-1 implements no router —
this module only defines the interface WP-3 will call into, exercised here
with synthetic values so the aggregation/trace logic is proven before any
real router exists.

COUNTERS mode: aggregate only (sum/count/min/max + bounded histogram), no
per-token records. TRACE mode: bounded ring buffer of sampled records, sampled
every `trace_every_n_steps`, with an explicit dropped-trace count when the
buffer is full — never an unbounded list.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any

from .config import InstrumentationMode
from .types import RoutingAggregate


@dataclass
class RoutingHistogram:
    """Bounded fixed-width histogram over active_tokens values."""

    num_bins: int = 20
    max_value: int = 1

    def __post_init__(self) -> None:
        if self.num_bins <= 0:
            raise ValueError("num_bins must be > 0")
        self._counts = [0] * self.num_bins

    def add(self, value: int) -> None:
        if self.max_value <= 0:
            bin_index = 0
        else:
            bin_index = min(self.num_bins - 1, int((value / self.max_value) * self.num_bins))
        bin_index = max(0, bin_index)
        self._counts[bin_index] += 1

    @property
    def counts(self) -> list[int]:
        return list(self._counts)


class RoutingCounters:
    def __init__(
        self,
        *,
        mode: InstrumentationMode = InstrumentationMode.COUNTERS,
        trace_every_n_steps: int = 0,
        trace_buffer_records: int = 4096,
        histogram_max_value: int = 1,
    ) -> None:
        self.mode = mode
        self.trace_every_n_steps = trace_every_n_steps
        self._step_count = 0
        self._active_tokens_sum = 0
        self._active_tokens_min: int | None = None
        self._active_tokens_max: int | None = None
        self._active_blocks_sum = 0
        self._active_experts_sum = 0
        self._active_experts_min: int | None = None
        self._active_experts_max: int | None = None
        self._active_parameters_sum = 0
        self._dropped_tokens_sum = 0
        self._padded_tokens_sum = 0
        self._entropy_values: list[float] = []
        self._histogram = RoutingHistogram(max_value=histogram_max_value)
        self._trace_buffer: deque[dict[str, Any]] = deque(maxlen=trace_buffer_records)
        self._dropped_trace_count = 0

    def record(
        self,
        *,
        step: int,
        active_tokens: int,
        active_blocks: int,
        active_experts: int,
        active_parameters: int,
        dropped_tokens: int = 0,
        padded_tokens: int = 0,
        entropy: float | None = None,
    ) -> None:
        if active_tokens < 0 or active_blocks < 0 or active_experts < 0 or active_parameters < 0:
            raise ValueError("routing counts cannot be negative")
        if dropped_tokens < 0 or padded_tokens < 0:
            raise ValueError("dropped/padded token counts cannot be negative")

        self._step_count += 1
        self._active_tokens_sum += active_tokens
        self._active_tokens_min = active_tokens if self._active_tokens_min is None else min(self._active_tokens_min, active_tokens)
        self._active_tokens_max = active_tokens if self._active_tokens_max is None else max(self._active_tokens_max, active_tokens)
        self._active_blocks_sum += active_blocks
        self._active_experts_sum += active_experts
        self._active_experts_min = active_experts if self._active_experts_min is None else min(self._active_experts_min, active_experts)
        self._active_experts_max = active_experts if self._active_experts_max is None else max(self._active_experts_max, active_experts)
        self._active_parameters_sum += active_parameters
        self._dropped_tokens_sum += dropped_tokens
        self._padded_tokens_sum += padded_tokens
        if entropy is not None:
            self._entropy_values.append(entropy)
        self._histogram.add(active_tokens)

        if self.mode == InstrumentationMode.TRACE and self.trace_every_n_steps > 0:
            if step % self.trace_every_n_steps == 0:
                if len(self._trace_buffer) == self._trace_buffer.maxlen:
                    self._dropped_trace_count += 1
                self._trace_buffer.append(
                    {
                        "step": step,
                        "active_tokens": active_tokens,
                        "active_blocks": active_blocks,
                        "active_experts": active_experts,
                        "active_parameters": active_parameters,
                        "dropped_tokens": dropped_tokens,
                        "padded_tokens": padded_tokens,
                        "entropy": entropy,
                    }
                )

    def snapshot(self) -> RoutingAggregate:
        entropy_mean = (
            sum(self._entropy_values) / len(self._entropy_values) if self._entropy_values else None
        )
        return RoutingAggregate(
            step_count=self._step_count,
            active_tokens_sum=self._active_tokens_sum,
            active_tokens_min=self._active_tokens_min or 0,
            active_tokens_max=self._active_tokens_max or 0,
            active_blocks_sum=self._active_blocks_sum,
            active_experts_sum=self._active_experts_sum,
            active_experts_min=self._active_experts_min or 0,
            active_experts_max=self._active_experts_max or 0,
            active_parameters_sum=self._active_parameters_sum,
            dropped_tokens_sum=self._dropped_tokens_sum,
            padded_tokens_sum=self._padded_tokens_sum,
            entropy_mean=entropy_mean,
            dropped_trace_count=self._dropped_trace_count,
        )

    def flush_trace(self) -> list[dict[str, Any]]:
        records = list(self._trace_buffer)
        self._trace_buffer.clear()
        return records

    @property
    def histogram_counts(self) -> list[int]:
        return self._histogram.counts

    @property
    def dropped_trace_count(self) -> int:
        return self._dropped_trace_count
