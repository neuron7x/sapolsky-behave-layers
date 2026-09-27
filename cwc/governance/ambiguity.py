from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class CredalExpectationInterval:
    lower: float
    upper: float
    minimizing_distribution: tuple[float, ...]
    maximizing_distribution: tuple[float, ...]
    method: str = "FINITE_INTERVAL_CREDAL_LP_EXACT_V1"


@dataclass(frozen=True, slots=True)
class MinimaxRegretDecision:
    action: str
    worst_case_regret: float
    action_worst_case_regrets: tuple[tuple[str, float], ...]
    method: str = "FINITE_WORLD_MINIMAX_REGRET_V1"


@dataclass(frozen=True, slots=True)
class PerfectInformationStopCertificate:
    max_plausible_evpi: float
    minimum_compute_cost: float
    stop_certified: bool
    method: str = "CREDAL_PERFECT_INFORMATION_UPPER_BOUND_V1"


def _validate_probability_box(lower: Sequence[float], upper: Sequence[float]) -> tuple[list[float], list[float]]:
    if not lower or len(lower) != len(upper):
        raise ValueError("equal non-empty probability bounds required")
    lo = [float(x) for x in lower]
    hi = [float(x) for x in upper]
    for l, u in zip(lo, hi, strict=True):
        if not math.isfinite(l) or not math.isfinite(u) or l < 0.0 or u > 1.0 or l > u:
            raise ValueError("invalid probability interval")
    if math.fsum(lo) > 1.0 + 1e-12 or math.fsum(hi) < 1.0 - 1e-12:
        raise ValueError("probability box has empty simplex intersection")
    return lo, hi


def _extreme_distribution(
    values: Sequence[float], lower: Sequence[float], upper: Sequence[float], *, maximize: bool
) -> tuple[float, tuple[float, ...]]:
    vals = [float(v) for v in values]
    if any(not math.isfinite(v) for v in vals):
        raise ValueError("values must be finite")
    lo, hi = _validate_probability_box(lower, upper)
    if len(vals) != len(lo):
        raise ValueError("one probability interval per value required")
    p = lo[:]
    remaining = 1.0 - math.fsum(p)
    order = sorted(range(len(vals)), key=lambda i: (vals[i], i), reverse=maximize)
    for i in order:
        if remaining <= 1e-15:
            break
        room = hi[i] - p[i]
        add = min(room, remaining)
        p[i] += add
        remaining -= add
    if remaining > 1e-9:
        raise ValueError("failed to construct feasible credal extreme point")
    expectation = math.fsum(pi * vi for pi, vi in zip(p, vals, strict=True))
    return expectation, tuple(p)


def credal_expectation_interval(
    values: Sequence[float], *, probability_lower: Sequence[float], probability_upper: Sequence[float]
) -> CredalExpectationInterval:
    """Exact min/max expectation over box-constrained finite probabilities.

    The feasible set is the simplex intersected with l_i <= p_i <= u_i. The
    objective is linear. Starting at all lower bounds, the minimizing LP is
    solved by assigning remaining mass greedily to the smallest values; the
    maximizing LP assigns it to the largest values. Exchange arguments prove
    optimality, so no numerical optimizer is needed.
    """
    low, p_low = _extreme_distribution(values, probability_lower, probability_upper, maximize=False)
    high, p_high = _extreme_distribution(values, probability_lower, probability_upper, maximize=True)
    return CredalExpectationInterval(low, high, p_low, p_high)


def minimax_regret_action(world_utilities: Sequence[Mapping[str, float]]) -> MinimaxRegretDecision:
    if not world_utilities:
        raise ValueError("at least one world required")
    action_sets = [set(w) for w in world_utilities]
    common = set.intersection(*action_sets)
    if not common:
        raise ValueError("worlds must share at least one legal action")
    rows: list[tuple[str, float]] = []
    for action in sorted(common):
        worst = -math.inf
        for world in world_utilities:
            vals = {a: float(world[a]) for a in common}
            if any(not math.isfinite(v) for v in vals.values()):
                raise ValueError("utilities must be finite")
            best = max(vals.values())
            worst = max(worst, best - vals[action])
        rows.append((action, worst))
    action, regret = min(rows, key=lambda item: (item[1], item[0]))
    return MinimaxRegretDecision(action, regret, tuple(rows))


def certify_no_information_worth_cost(
    *,
    current_action_regrets: Sequence[float],
    probability_lower: Sequence[float],
    probability_upper: Sequence[float],
    minimum_compute_cost: float,
) -> PerfectInformationStopCertificate:
    """Robust STOP certificate using perfect information as an upper bound.

    For a pure-information operation (it does not intervene on W, U or A), its
    gross value cannot exceed the value of perfect revelation of W. For current
    action a0, perfect revelation gains exactly R(W;a0). Therefore if even the
    maximum expected regret over every distribution in the credal set is <= the
    minimum possible compute cost, every less-informative operation has VOC<=0.
    """
    cost = float(minimum_compute_cost)
    if not math.isfinite(cost) or cost < 0.0:
        raise ValueError("minimum_compute_cost must be finite and >= 0")
    if any(float(r) < 0.0 or not math.isfinite(float(r)) for r in current_action_regrets):
        raise ValueError("regrets must be finite and >= 0")
    interval = credal_expectation_interval(
        current_action_regrets,
        probability_lower=probability_lower,
        probability_upper=probability_upper,
    )
    return PerfectInformationStopCertificate(
        max_plausible_evpi=interval.upper,
        minimum_compute_cost=cost,
        stop_certified=interval.upper <= cost + 1e-15,
    )
