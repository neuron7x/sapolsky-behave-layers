"""CPU wall clock (perf_counter_ns) and deferred-synchronization CUDA clock
(Act 4.4). No torch.cuda.synchronize() call happens on the start/end path —
only inside resolve_windows(), once per batch.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .event_buffer import EventPair, EventPool

if TYPE_CHECKING:
    import torch


def cpu_start_ns() -> int:
    return time.perf_counter_ns()


def cpu_elapsed_ms(start_ns: int) -> float:
    return (time.perf_counter_ns() - start_ns) / 1_000_000.0


@dataclass
class CudaWindow:
    """One pending start/end CUDA-event pair. Not resolved until
    resolve_windows() runs — no synchronization is performed on this object's
    own path.
    """

    pair: EventPair
    device_index: int
    stream_ptr: int | None = None

    def mark_start(self) -> None:
        start_event, _ = self.pair
        start_event.record()

    def mark_end(self) -> None:
        _, end_event = self.pair
        end_event.record()


def open_window(pool: EventPool, *, device_index: int, stream: "torch.cuda.Stream | None" = None) -> CudaWindow | None:
    pair = pool.acquire()
    if pair is None:
        return None
    stream_ptr = stream.cuda_stream if stream is not None else None
    return CudaWindow(pair=pair, device_index=device_index, stream_ptr=stream_ptr)


def resolve_windows(windows: list[CudaWindow], pool: EventPool) -> list[float]:
    """Synchronize exactly once for the whole batch, read elapsed_time for
    each pair, then return the pairs to the pool. Events must not be
    resolved across devices — every window in the batch must share the
    same device_index.
    """
    if not windows:
        return []
    device_indices = {window.device_index for window in windows}
    if len(device_indices) > 1:
        raise ValueError("resolve_windows cannot mix CUDA events from different devices")

    import torch

    torch.cuda.synchronize(next(iter(device_indices)))
    elapsed_ms: list[float] = []
    for window in windows:
        start_event, end_event = window.pair
        elapsed_ms.append(float(start_event.elapsed_time(end_event)))
        pool.release(window.pair)
    return elapsed_ms
