from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class MyopicGapCertificate:
    perfect_information_gross_upper: float
    minimum_future_compute_cost: float
    global_net_upper: float
    myopic_value: float
    worst_case_suboptimality_upper: float
    globally_stop_certified: bool
    method: str = "PERFECT_INFORMATION_META_GAP_UPPER_BOUND_V1"


def perfect_information_myopic_gap_bound(
    *,
    current_action_regrets: Sequence[float],
    probability_upper_expectation: float,
    minimum_future_compute_cost: float,
    myopic_value: float,
) -> MyopicGapCertificate:
    """Upper-bound the value missed by a myopic pure-information controller.

    `probability_upper_expectation` must be an externally valid upper bound on
    E[R(W;a0)] over the relevant ambiguity set. Perfect revelation cannot yield
    more gross decision value than this expected regret. Therefore every finite
    pure-information computation sequence with total cost at least `c_min` has
    net value <= EVPI_upper - c_min.

    This bound is intentionally loose: it is useful as a safety ceiling, not as
    a scalable substitute for solving the metalevel MDP.
    """
    regrets = [float(r) for r in current_action_regrets]
    if not regrets or any(not math.isfinite(r) or r < 0.0 for r in regrets):
        raise ValueError("finite nonnegative regrets required")
    evpi = float(probability_upper_expectation)
    cost = float(minimum_future_compute_cost)
    myopic = float(myopic_value)
    if not math.isfinite(evpi) or evpi < 0.0:
        raise ValueError("probability_upper_expectation must be finite and >=0")
    if evpi > max(regrets) + 1e-12:
        raise ValueError("EVPI upper bound cannot exceed max realized regret support")
    if not math.isfinite(cost) or cost < 0.0:
        raise ValueError("minimum_future_compute_cost must be finite and >=0")
    if not math.isfinite(myopic):
        raise ValueError("myopic_value must be finite")

    global_upper = evpi - cost
    gap = max(0.0, global_upper - myopic)
    return MyopicGapCertificate(
        perfect_information_gross_upper=evpi,
        minimum_future_compute_cost=cost,
        global_net_upper=global_upper,
        myopic_value=myopic,
        worst_case_suboptimality_upper=gap,
        globally_stop_certified=global_upper <= 0.0,
    )
