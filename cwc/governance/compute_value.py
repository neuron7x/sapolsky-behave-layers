from __future__ import annotations

import math
from dataclasses import dataclass


def _finite(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return value


@dataclass(frozen=True, slots=True)
class ValueOfComputationEstimate:
    operation_id: str
    gross_value: float
    total_cost: float
    voc: float
    lower_bound: float
    upper_bound: float
    method: str

    def __post_init__(self) -> None:
        if not self.operation_id.strip():
            raise ValueError("operation_id required")
        if not self.method.strip():
            raise ValueError("method required")
        if self.total_cost < 0:
            raise ValueError("total_cost must be >= 0")
        if self.lower_bound > self.voc or self.voc > self.upper_bound:
            raise ValueError("VOC interval must contain point estimate")


def estimate_voc(
    *,
    operation_id: str,
    gross_value: float,
    total_cost: float,
    gross_lower: float,
    gross_upper: float,
    method: str,
) -> ValueOfComputationEstimate:
    """Convert a caller-supplied gross decision-value estimate into net VOC.

    Statistical validity of ``gross_lower``/``gross_upper`` is deliberately not
    invented here.  The experiment/harness must bind them to a preregistered
    estimator (confidence sequence, exact oracle interval, or other valid method).
    """
    gross_value = _finite("gross_value", gross_value)
    gross_lower = _finite("gross_lower", gross_lower)
    gross_upper = _finite("gross_upper", gross_upper)
    total_cost = _finite("total_cost", total_cost)
    if total_cost < 0:
        raise ValueError("total_cost must be >= 0")
    if gross_lower > gross_value or gross_value > gross_upper:
        raise ValueError("gross interval must contain gross_value")
    return ValueOfComputationEstimate(
        operation_id=operation_id,
        gross_value=gross_value,
        total_cost=total_cost,
        voc=gross_value - total_cost,
        lower_bound=gross_lower - total_cost,
        upper_bound=gross_upper - total_cost,
        method=method,
    )
