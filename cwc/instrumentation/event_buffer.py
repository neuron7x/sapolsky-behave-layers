"""Bounded pool of pre-created CUDA event pairs (Act 4.5).

Events are allocated once, before warm-up, never inside the measurement loop.
Pool exhaustion fails closed: it counts a dropped event pair and returns None
rather than silently allocating a fresh (expensive, out-of-band) event.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import torch

EventPair = tuple["torch.cuda.Event", "torch.cuda.Event"]


class EventPool:
    """Not thread-safe by design (Act 4.5: "thread safety не потрібна, якщо це
    явно задокументовано"). One pool per (process, DDP rank); do not share
    across threads or ranks.
    """

    def __init__(self, size: int) -> None:
        if size <= 0:
            raise ValueError("size must be > 0")
        self._size = size
        self._available: list[EventPair] = []
        self._warmed_up = False
        self._dropped_event_pairs = 0
        self._acquired_count = 0

    def warm_up(self) -> None:
        if self._warmed_up:
            return
        import torch

        for _ in range(self._size):
            pair: EventPair = (
                torch.cuda.Event(enable_timing=True),
                torch.cuda.Event(enable_timing=True),
            )
            self._available.append(pair)
        self._warmed_up = True

    def acquire(self) -> EventPair | None:
        if not self._available:
            self._dropped_event_pairs += 1
            return None
        self._acquired_count += 1
        return self._available.pop()

    def release(self, pair: EventPair) -> None:
        self._available.append(pair)

    @property
    def dropped_event_pairs(self) -> int:
        return self._dropped_event_pairs

    @property
    def size(self) -> int:
        return self._size

    @property
    def available_count(self) -> int:
        return len(self._available)

    @property
    def warmed_up(self) -> bool:
        return self._warmed_up
