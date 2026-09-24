from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProviderLimits:
    max_concurrency: int
    bucket_capacity: float
    refill_per_second: float

    def __post_init__(self) -> None:
        if self.max_concurrency <= 0:
            raise ValueError("max_concurrency must be positive")
        for name in ("bucket_capacity", "refill_per_second"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and >= 0")
            object.__setattr__(self, name, value)


@dataclass(frozen=True, slots=True)
class SchedulerState:
    in_flight: int
    available_tokens: float
    last_timestamp: float

    def __post_init__(self) -> None:
        if self.in_flight < 0:
            raise ValueError("in_flight must be >= 0")
        if not math.isfinite(self.available_tokens) or self.available_tokens < 0:
            raise ValueError("available_tokens must be finite and >= 0")
        if not math.isfinite(self.last_timestamp):
            raise ValueError("last_timestamp must be finite")


@dataclass(frozen=True, slots=True)
class SchedulerDecision:
    granted: bool
    reason_code: str
    state: SchedulerState


def _refill(state: SchedulerState, limits: ProviderLimits, now: float) -> SchedulerState:
    now = float(now)
    if not math.isfinite(now) or now < state.last_timestamp:
        raise ValueError("now must be finite and monotone")
    replenished = min(
        limits.bucket_capacity,
        state.available_tokens + (now - state.last_timestamp) * limits.refill_per_second,
    )
    return SchedulerState(state.in_flight, replenished, now)


def acquire(
    state: SchedulerState,
    limits: ProviderLimits,
    *,
    now: float,
    token_units: float = 1.0,
) -> SchedulerDecision:
    token_units = float(token_units)
    if not math.isfinite(token_units) or token_units <= 0:
        raise ValueError("token_units must be finite and > 0")
    state = _refill(state, limits, now)
    if state.in_flight >= limits.max_concurrency:
        return SchedulerDecision(False, "CONCURRENCY_LIMIT", state)
    if state.available_tokens < token_units:
        return SchedulerDecision(False, "RATE_LIMIT", state)
    return SchedulerDecision(
        True,
        "PERMIT",
        SchedulerState(state.in_flight + 1, state.available_tokens - token_units, state.last_timestamp),
    )


def release(state: SchedulerState) -> SchedulerState:
    if state.in_flight <= 0:
        raise RuntimeError("RELEASE_WITHOUT_PERMIT")
    return SchedulerState(state.in_flight - 1, state.available_tokens, state.last_timestamp)
