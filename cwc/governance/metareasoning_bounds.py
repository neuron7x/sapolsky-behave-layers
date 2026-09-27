from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MyopicApproximationBound:
    myopic_value: float
    perfect_information_value_upper: float
    suboptimality_upper_bound: float
    pure_information_certified: bool
    method: str = "PERFECT_INFORMATION_META_GAP_BOUND_V1"


def certify_myopic_suboptimality_upper_bound(
    *,
    myopic_value: float,
    perfect_information_value_upper: float,
    pure_information_certified: bool,
) -> MyopicApproximationBound:
    """Bound any finite-horizon pure-information meta-policy above myopic value.

    For pure-information computations with non-negative compute costs, no finite
    computation sequence can deliver more object-level value than perfect
    revelation of the latent world. Hence V_h <= V_PI and

        0 <= V_h - V_1 <= max(0, V_PI - V_1).

    This is deliberately loose. It is invalid for computations that intervene
    on the world, utility function or legal action set.
    """
    if not pure_information_certified:
        raise ValueError("pure-information authority required")
    myopic = float(myopic_value)
    perfect = float(perfect_information_value_upper)
    if not math.isfinite(myopic) or not math.isfinite(perfect):
        raise ValueError("finite values required")
    if perfect < myopic - 1e-12:
        raise ValueError("perfect-information upper bound cannot be below myopic value")
    return MyopicApproximationBound(
        myopic_value=myopic,
        perfect_information_value_upper=perfect,
        suboptimality_upper_bound=max(0.0, perfect - myopic),
        pure_information_certified=True,
    )
