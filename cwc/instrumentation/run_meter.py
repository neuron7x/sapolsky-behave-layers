"""Coarse-scope timing meter (Act 4.6). Never used per-token/per-layer/per-head
(Act 2.3) — only whole training steps, eval windows, inference requests,
prefill/decode phases, or benchmark intervals.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator

from .clock import CudaWindow, cpu_elapsed_ms, cpu_start_ns, open_window, resolve_windows
from .event_buffer import EventPool
from .types import LatencyRecord


@dataclass
class _PendingScope:
    name: str
    step: int
    tokens: int | None
    cpu_start_ns: int
    cuda_window: CudaWindow | None


class RunMeter:
    """COUNTERS-mode run meter. Does not synchronize CUDA on scope entry/exit —
    only in resolve(), which drains every pending CUDA window in one batched
    torch.cuda.synchronize() call.
    """

    def __init__(
        self,
        *,
        event_pool: EventPool | None = None,
        device_index: int = 0,
        enable_cuda_events: bool = True,
    ) -> None:
        self._pool = event_pool
        self._device_index = device_index
        self._enable_cuda_events = enable_cuda_events and event_pool is not None
        self._pending: list[_PendingScope] = []
        self._resolved_records: list[LatencyRecord] = []
        self._closed = False

    @property
    def cuda_available(self) -> bool:
        try:
            import torch
        except ImportError:
            return False
        return bool(torch.cuda.is_available())

    @contextmanager
    def scope(self, name: str, *, step: int = 0, tokens: int | None = None) -> Iterator[None]:
        start_ns = cpu_start_ns()
        cuda_window: CudaWindow | None = None
        if self._enable_cuda_events and self.cuda_available and self._pool is not None:
            cuda_window = open_window(self._pool, device_index=self._device_index)
            if cuda_window is not None:
                cuda_window.mark_start()
        try:
            yield
        except Exception as exc:
            end_ns_elapsed = cpu_elapsed_ms(start_ns)
            self._resolved_records.append(
                LatencyRecord(
                    scope_name=name,
                    step=step,
                    status="error",
                    end_to_end_ms=end_ns_elapsed,
                    gpu_kernel_ms=0.0,
                    tokens=tokens,
                    error_type=type(exc).__name__,
                )
            )
            raise
        else:
            if cuda_window is not None:
                cuda_window.mark_end()
            self._pending.append(
                _PendingScope(
                    name=name, step=step, tokens=tokens, cpu_start_ns=start_ns, cuda_window=cuda_window
                )
            )

    def measure_step(self, fn: Callable[[], Any], *, step: int, tokens: int | None = None) -> Any:
        with self.scope("step", step=step, tokens=tokens):
            return fn()

    def resolve(self) -> list[LatencyRecord]:
        """Batch-resolve every pending scope: one torch.cuda.synchronize() call
        (only if any pending scope actually opened a CUDA window), then read
        end_to_end_ms for every scope regardless of whether it had a window.
        """
        cuda_windows = [p.cuda_window for p in self._pending if p.cuda_window is not None]
        gpu_ms_by_id = {}
        if cuda_windows and self._pool is not None:
            elapsed = resolve_windows(cuda_windows, self._pool)
            gpu_ms_by_id = {id(window): ms for window, ms in zip(cuda_windows, elapsed, strict=False)}

        newly_resolved: list[LatencyRecord] = []
        for pending in self._pending:
            end_to_end_ms = cpu_elapsed_ms(pending.cpu_start_ns)
            gpu_ms = gpu_ms_by_id.get(id(pending.cuda_window), 0.0) if pending.cuda_window else 0.0
            record = LatencyRecord(
                scope_name=pending.name,
                step=pending.step,
                status="ok",
                end_to_end_ms=end_to_end_ms,
                gpu_kernel_ms=gpu_ms,
                tokens=pending.tokens,
            )
            newly_resolved.append(record)
        self._resolved_records.extend(newly_resolved)
        self._pending.clear()
        return newly_resolved

    def flush(self) -> list[LatencyRecord]:
        return list(self._resolved_records)

    def close(self) -> None:
        if self._closed:
            return
        self.resolve()
        self._closed = True

    @property
    def records(self) -> list[LatencyRecord]:
        return list(self._resolved_records)
