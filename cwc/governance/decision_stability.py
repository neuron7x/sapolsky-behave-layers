from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class DecisionStabilityCertificate:
    action: str
    worlds: int
    nominal_min_margin: float
    utility_sup_error: float
    robust_min_margin: float
    stable: bool
    method: str = "FINITE_WORLD_ROBUST_ACTION_MARGIN_V1"


@dataclass(frozen=True, slots=True)
class RemovableComputeCertificate:
    baseline_total_cost: float
    certified_suffix_cost: float
    certified_fraction: float
    action_stability: DecisionStabilityCertificate
    method: str = "DECISION_IRRELEVANT_SUFFIX_V1"


def certify_action_stability(
    world_utilities: Sequence[Mapping[str, float]],
    *,
    action: str,
    utility_sup_error: float = 0.0,
) -> DecisionStabilityCertificate:
    """Certify one action under all admitted worlds and bounded utility error.

    For a world w, margin(a)=U(w,a)-max_{b!=a}U(w,b). If |U'-U|_inf<=eta,
    the margin can shrink by at most 2*eta. Therefore min_w margin(w)>2*eta
    certifies that ``action`` remains strictly optimal for every admitted world
    and every utility perturbation inside the declared sup-norm ball.
    """
    eta = float(utility_sup_error)
    if not math.isfinite(eta) or eta < 0.0:
        raise ValueError("utility_sup_error must be finite and >= 0")
    if not world_utilities:
        raise ValueError("at least one world required")
    margins: list[float] = []
    for utilities in world_utilities:
        if action not in utilities or len(utilities) < 2:
            raise ValueError("action must exist and at least two actions are required")
        vals = {str(k): float(v) for k, v in utilities.items()}
        if any(not math.isfinite(v) for v in vals.values()):
            raise ValueError("utilities must be finite")
        best_other = max(v for k, v in vals.items() if k != action)
        margins.append(vals[action] - best_other)
    nominal = min(margins)
    robust = nominal - 2.0 * eta
    return DecisionStabilityCertificate(
        action=action,
        worlds=len(world_utilities),
        nominal_min_margin=nominal,
        utility_sup_error=eta,
        robust_min_margin=robust,
        stable=robust > 0.0,
    )


def certify_decision_irrelevant_suffix(
    *,
    baseline_total_cost: float,
    suffix_cost: float,
    stability: DecisionStabilityCertificate,
) -> RemovableComputeCertificate:
    """Certify safely removable suffix compute after robust decision stability.

    This certificate only applies when the suffix can reveal information about
    the already-admitted world but cannot intervene on the world, action set or
    utility. Under that causal contract, robust action stability makes the
    suffix's immediate action-switch value exactly zero.
    """
    total = float(baseline_total_cost)
    suffix = float(suffix_cost)
    if not math.isfinite(total) or total <= 0.0:
        raise ValueError("baseline_total_cost must be finite and > 0")
    if not math.isfinite(suffix) or not 0.0 <= suffix <= total:
        raise ValueError("suffix_cost must be finite and in [0,total]")
    certified = suffix if stability.stable else 0.0
    return RemovableComputeCertificate(
        baseline_total_cost=total,
        certified_suffix_cost=certified,
        certified_fraction=certified / total,
        action_stability=stability,
    )
