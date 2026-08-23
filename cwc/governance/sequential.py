from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Sequence


class SamplingMode(str, Enum):
    IID_BOUNDED = "IID_BOUNDED"
    ADAPTIVE = "ADAPTIVE"


class SequentialDecision(str, Enum):
    STOP_VALUE_EXHAUSTED = "STOP_VALUE_EXHAUSTED"
    CONTINUE_VALUE_POSITIVE = "CONTINUE_VALUE_POSITIVE"
    INDETERMINATE = "INDETERMINATE"


@dataclass(frozen=True, slots=True)
class SequentialSamplingContract:
    mode: SamplingMode
    lower: float
    upper: float
    delta: float
    contract_id: str = "DGC-IID-BOUNDED-V1"

    def __post_init__(self) -> None:
        if not self.contract_id.strip():
            raise ValueError("contract_id required")
        for name in ("lower", "upper", "delta"):
            value = float(getattr(self, name))
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
            object.__setattr__(self, name, value)
        if self.upper <= self.lower:
            raise ValueError("upper must be > lower")
        if not 0 < self.delta < 1:
            raise ValueError("delta must be in (0,1)")


@dataclass(frozen=True, slots=True)
class BoundedMeanConfidenceSequence:
    n: int
    mean: float
    lower: float
    upper: float
    half_width: float
    delta: float
    observation_lower: float
    observation_upper: float
    method: str
    contract_id: str

    def __post_init__(self) -> None:
        if self.n <= 0:
            raise ValueError("n must be positive")
        if not (self.observation_lower <= self.lower <= self.mean <= self.upper <= self.observation_upper):
            raise ValueError("invalid confidence sequence interval")


def stitched_hoeffding_confidence_sequence(
    observations: Sequence[float],
    *,
    contract: SequentialSamplingContract,
) -> BoundedMeanConfidenceSequence:
    """Anytime-valid mean CS for a frozen i.i.d. bounded draw process.

    At time n we spend delta_n = 6*delta/(pi^2*n^2). Hoeffding's fixed-n
    two-sided bound then has failure probability <= delta_n. Since
    sum_n delta_n = delta, a union bound gives simultaneous coverage over
    every n, so an arbitrary stopping time preserves the declared coverage.

    This deliberately refuses adaptive sampling. Adaptive perturbation policies
    require a separately justified e-process/martingale construction.
    """
    if contract.mode is not SamplingMode.IID_BOUNDED:
        raise ValueError("ADAPTIVE_POLICY_REQUIRES_SEPARATE_E_PROCESS")
    if not observations:
        raise ValueError("at least one observation required")

    values = tuple(float(x) for x in observations)
    for value in values:
        if not math.isfinite(value) or not contract.lower <= value <= contract.upper:
            raise ValueError("observation outside declared bounded support")

    n = len(values)
    mean = math.fsum(values) / n
    delta_n = 6.0 * contract.delta / (math.pi**2 * n**2)
    width = (contract.upper - contract.lower) * math.sqrt(math.log(2.0 / delta_n) / (2.0 * n))
    lower = max(contract.lower, mean - width)
    upper = min(contract.upper, mean + width)
    return BoundedMeanConfidenceSequence(
        n=n,
        mean=mean,
        lower=lower,
        upper=upper,
        half_width=width,
        delta=contract.delta,
        observation_lower=contract.lower,
        observation_upper=contract.upper,
        method="STITCHED_HOEFFDING_UNION_BOUND_V1",
        contract_id=contract.contract_id,
    )


def sequential_voc_decision(
    cs: BoundedMeanConfidenceSequence,
    *,
    compute_cost: float,
    safety_margin: float = 0.0,
) -> SequentialDecision:
    compute_cost = float(compute_cost)
    safety_margin = float(safety_margin)
    if not math.isfinite(compute_cost) or compute_cost < 0:
        raise ValueError("compute_cost must be finite and >= 0")
    if not math.isfinite(safety_margin) or safety_margin < 0:
        raise ValueError("safety_margin must be finite and >= 0")
    voc_lower = cs.lower - compute_cost
    voc_upper = cs.upper - compute_cost
    if voc_upper <= 0.0:
        return SequentialDecision.STOP_VALUE_EXHAUSTED
    if voc_lower > safety_margin:
        return SequentialDecision.CONTINUE_VALUE_POSITIVE
    return SequentialDecision.INDETERMINATE
