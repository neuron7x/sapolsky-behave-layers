from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class LoopGuard:
    max_steps: int
    step: int = 0

    def __post_init__(self) -> None:
        if self.max_steps <= 0:
            raise ValueError("max_steps must be positive")
        if not 0 <= self.step <= self.max_steps:
            raise ValueError("step outside [0,max_steps]")

    @property
    def exhausted(self) -> bool:
        return self.step >= self.max_steps

    def advance(self) -> "LoopGuard":
        if self.exhausted:
            raise RuntimeError("DGC_MAX_STEPS_EXHAUSTED")
        return LoopGuard(max_steps=self.max_steps, step=self.step + 1)
