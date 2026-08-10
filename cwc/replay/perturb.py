"""Generic counterfactual replay contracts.

The benchmark supplies the structural model.  This module merely defines the
result type so intervention semantics remain explicit at the evidence boundary.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CounterfactualProbe:
    candidate_id: str
    context_id: str
    factual_outcome: int
    counterfactual_outcome: int
    signed_effect: float

    def __post_init__(self) -> None:
        if self.factual_outcome not in (0, 1) or self.counterfactual_outcome not in (0, 1):
            raise ValueError("benchmark outcomes must be binary")
