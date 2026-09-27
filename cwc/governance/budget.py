from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass


def _valid(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and >= 0")
    return value


@dataclass(frozen=True, slots=True)
class BudgetLedger:
    hard_tokens: float
    hard_money: float
    hard_time: float
    hard_gpu: float = 0.0
    spent_tokens: float = 0.0
    spent_money: float = 0.0
    spent_time: float = 0.0
    spent_gpu: float = 0.0
    reserved_emergency_money: float = 0.0

    def __post_init__(self) -> None:
        for field_name in (
            "hard_tokens", "hard_money", "hard_time", "hard_gpu",
            "spent_tokens", "spent_money", "spent_time", "spent_gpu",
            "reserved_emergency_money",
        ):
            object.__setattr__(self, field_name, _valid(field_name, getattr(self, field_name)))
        if self.spent_tokens > self.hard_tokens or self.spent_money > self.hard_money or self.spent_time > self.hard_time:
            raise ValueError("spent budget cannot exceed hard budget")
        if self.hard_gpu > 0 and self.spent_gpu > self.hard_gpu:
            raise ValueError("spent GPU budget cannot exceed hard GPU budget")
        if self.reserved_emergency_money > self.hard_money:
            raise ValueError("emergency reserve cannot exceed hard money budget")

    @property
    def digest(self) -> str:
        payload = {
            "hard_tokens": self.hard_tokens,
            "hard_money": self.hard_money,
            "hard_time": self.hard_time,
            "hard_gpu": self.hard_gpu,
            "spent_tokens": self.spent_tokens,
            "spent_money": self.spent_money,
            "spent_time": self.spent_time,
            "spent_gpu": self.spent_gpu,
            "reserved_emergency_money": self.reserved_emergency_money,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(raw).hexdigest()

    def can_spend(self, *, tokens: float = 0, money: float = 0, time: float = 0, gpu: float = 0, emergency: bool = False) -> bool:
        tokens, money, time, gpu = (_valid("tokens", tokens), _valid("money", money), _valid("time", time), _valid("gpu", gpu))
        usable_money = self.hard_money if emergency else max(0.0, self.hard_money - self.reserved_emergency_money)
        gpu_ok = True if self.hard_gpu == 0 else self.spent_gpu + gpu <= self.hard_gpu
        return (
            self.spent_tokens + tokens <= self.hard_tokens
            and self.spent_money + money <= usable_money
            and self.spent_time + time <= self.hard_time
            and gpu_ok
        )

    def spend(self, *, tokens: float = 0, money: float = 0, time: float = 0, gpu: float = 0, emergency: bool = False) -> "BudgetLedger":
        if not self.can_spend(tokens=tokens, money=money, time=time, gpu=gpu, emergency=emergency):
            raise RuntimeError("HARD_BUDGET_EXCEEDED")
        return BudgetLedger(
            hard_tokens=self.hard_tokens,
            hard_money=self.hard_money,
            hard_time=self.hard_time,
            hard_gpu=self.hard_gpu,
            spent_tokens=self.spent_tokens + tokens,
            spent_money=self.spent_money + money,
            spent_time=self.spent_time + time,
            spent_gpu=self.spent_gpu + gpu,
            reserved_emergency_money=self.reserved_emergency_money,
        )
