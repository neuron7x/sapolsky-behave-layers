from __future__ import annotations

import math
from dataclasses import dataclass


def _finite_nonnegative(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"{name} must be finite and >= 0")
    return value


@dataclass(frozen=True, slots=True)
class RobustnessBudget:
    """Declared ambiguity budget for a regret-like gross decision value.

    ``total_variation_radius`` uses the standard TV convention
    TV(P,Q)=sup_A |P(A)-Q(A)|=0.5*||P-Q||_1.

    ``utility_sup_error`` means |U_true(w,a)-U_model(w,a)| <= eta for every
    admitted (w,a).  For regret max_a U(w,a)-U(w,a0), this induces at most
    2*eta absolute error.

    ``cost_underestimate`` bounds how much actual compute cost may exceed the
    nominal cost used by the governor.
    """

    total_variation_radius: float = 0.0
    utility_sup_error: float = 0.0
    cost_underestimate: float = 0.0

    def __post_init__(self) -> None:
        tv = _finite_nonnegative("total_variation_radius", self.total_variation_radius)
        eta = _finite_nonnegative("utility_sup_error", self.utility_sup_error)
        kappa = _finite_nonnegative("cost_underestimate", self.cost_underestimate)
        if tv > 1.0:
            raise ValueError("total_variation_radius must be <= 1")
        object.__setattr__(self, "total_variation_radius", tv)
        object.__setattr__(self, "utility_sup_error", eta)
        object.__setattr__(self, "cost_underestimate", kappa)


@dataclass(frozen=True, slots=True)
class RobustVOCLowerBound:
    nominal_gross_lower: float
    nominal_cost: float
    nominal_voc_lower: float
    distribution_shift_penalty: float
    utility_misspecification_penalty: float
    cost_underestimate_penalty: float
    robust_voc_lower: float
    gross_lower_support: float
    gross_upper_support: float
    method: str = "TV_UTILITY_COST_ROBUST_VOC_V1"

    @property
    def admitted(self) -> bool:
        return self.robust_voc_lower > 0.0


def robust_voc_lower_bound(
    *,
    nominal_gross_lower: float,
    nominal_cost: float,
    gross_lower_support: float,
    gross_upper_support: float,
    budget: RobustnessBudget,
) -> RobustVOCLowerBound:
    """Lower-bound net VOC under bounded distribution, utility and cost error.

    If a gross regret-like value G lies in [L,H] and Q is within TV radius eps
    of nominal P, then E_Q[G] >= E_P[G] - eps*(H-L).  If the utility function
    is uniformly misspecified by eta, regret changes by at most 2*eta.  If
    actual cost can exceed nominal cost by kappa, subtract kappa as well.

    The result composes with any statistically valid nominal gross lower bound;
    it does not invent such a bound.
    """
    values = {
        "nominal_gross_lower": nominal_gross_lower,
        "nominal_cost": nominal_cost,
        "gross_lower_support": gross_lower_support,
        "gross_upper_support": gross_upper_support,
    }
    cast: dict[str, float] = {}
    for name, raw in values.items():
        val = float(raw)
        if not math.isfinite(val):
            raise ValueError(f"{name} must be finite")
        cast[name] = val
    if cast["nominal_cost"] < 0.0:
        raise ValueError("nominal_cost must be >= 0")
    if cast["gross_upper_support"] < cast["gross_lower_support"]:
        raise ValueError("gross support is inverted")
    if not cast["gross_lower_support"] <= cast["nominal_gross_lower"] <= cast["gross_upper_support"]:
        raise ValueError("nominal gross lower bound outside declared support")

    width = cast["gross_upper_support"] - cast["gross_lower_support"]
    shift_penalty = budget.total_variation_radius * width
    utility_penalty = 2.0 * budget.utility_sup_error
    cost_penalty = budget.cost_underestimate
    nominal_voc_lower = cast["nominal_gross_lower"] - cast["nominal_cost"]
    robust_lower = nominal_voc_lower - shift_penalty - utility_penalty - cost_penalty
    return RobustVOCLowerBound(
        nominal_gross_lower=cast["nominal_gross_lower"],
        nominal_cost=cast["nominal_cost"],
        nominal_voc_lower=nominal_voc_lower,
        distribution_shift_penalty=shift_penalty,
        utility_misspecification_penalty=utility_penalty,
        cost_underestimate_penalty=cost_penalty,
        robust_voc_lower=robust_lower,
        gross_lower_support=cast["gross_lower_support"],
        gross_upper_support=cast["gross_upper_support"],
    )


def robustify_voc_estimate(
    estimate: "ValueOfComputationEstimate",
    *,
    gross_lower_support: float,
    gross_upper_support: float,
    budget: RobustnessBudget,
) -> "ValueOfComputationEstimate":
    """Return a governor-compatible estimate with an ambiguity-robust LCB."""
    from cwc.governance.compute_value import VOCAuthority, ValueOfComputationEstimate

    robust = robust_voc_lower_bound(
        nominal_gross_lower=estimate.lower_bound + estimate.total_cost,
        nominal_cost=estimate.total_cost,
        gross_lower_support=gross_lower_support,
        gross_upper_support=gross_upper_support,
        budget=budget,
    )
    return ValueOfComputationEstimate(
        operation_id=estimate.operation_id,
        gross_value=estimate.gross_value,
        total_cost=estimate.total_cost,
        voc=estimate.voc,
        lower_bound=robust.robust_voc_lower,
        upper_bound=estimate.upper_bound,
        method=f"ROBUST[{robust.method}]::{estimate.method}",
        authority=VOCAuthority.ROBUST_AMBIGUITY_BOUND,
    )


@dataclass(frozen=True, slots=True)
class WassersteinRobustnessBudget:
    radius: float
    gross_lipschitz_constant: float
    utility_sup_error: float = 0.0
    cost_underestimate: float = 0.0

    def __post_init__(self) -> None:
        for name in ("radius", "gross_lipschitz_constant", "utility_sup_error", "cost_underestimate"):
            object.__setattr__(self, name, _finite_nonnegative(name, getattr(self, name)))


def wasserstein_robust_voc_lower_bound(
    *,
    nominal_gross_lower: float,
    nominal_cost: float,
    budget: WassersteinRobustnessBudget,
) -> float:
    """Kantorovich-Rubinstein lower bound for a 1-Wasserstein ambiguity ball.

    If gross decision value g is L-Lipschitz under the declared world metric and
    W1(P,Q)<=rho, then E_Q[g] >= E_P[g]-L*rho. Regret utility error and cost
    underestimation are then subtracted as in the TV contract.
    """
    gross = float(nominal_gross_lower)
    cost = float(nominal_cost)
    if not math.isfinite(gross) or not math.isfinite(cost) or cost < 0.0:
        raise ValueError("finite gross and non-negative finite cost required")
    return (
        gross
        - cost
        - budget.radius * budget.gross_lipschitz_constant
        - 2.0 * budget.utility_sup_error
        - budget.cost_underestimate
    )
