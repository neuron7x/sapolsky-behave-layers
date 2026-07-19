"""Finite decision-problem verifier for an information-value bound (nats)."""
from __future__ import annotations

import math
from collections.abc import Sequence


def _validate(joint: Sequence[Sequence[float]], utility: Sequence[Sequence[float]]) -> None:
    if not joint or not joint[0] or not utility or not utility[0]:
        raise ValueError("joint and utility must be non-empty")
    if any(len(row) != len(joint[0]) for row in joint):
        raise ValueError("joint must be rectangular")
    if len(utility) != len(joint) or any(len(row) != len(utility[0]) for row in utility):
        raise ValueError("utility must be rectangular with one row per context")
    if any(p < 0 or not math.isfinite(p) for row in joint for p in row):
        raise ValueError("joint probabilities must be finite and non-negative")
    if any(not math.isfinite(u) for row in utility for u in row):
        raise ValueError("utilities must be finite")
    if not math.isclose(sum(map(sum, joint)), 1.0, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("joint probabilities must sum to one")


def information_value_certificate(
    joint_cz: Sequence[Sequence[float]],
    utility_ca: Sequence[Sequence[float]],
    *,
    route_cost: float = 0.0,
) -> dict[str, float | bool]:
    """Compute signal value and `V <= utility_range * sqrt(I(C;Z)/2)`."""
    _validate(joint_cz, utility_ca)
    if route_cost < 0 or not math.isfinite(route_cost):
        raise ValueError("route_cost must be finite and non-negative")
    n_contexts, n_signals, n_actions = len(joint_cz), len(joint_cz[0]), len(utility_ca[0])
    p_c = [sum(joint_cz[c]) for c in range(n_contexts)]
    p_z = [sum(joint_cz[c][z] for c in range(n_contexts)) for z in range(n_signals)]
    prior = max(sum(p_c[c] * utility_ca[c][a] for c in range(n_contexts)) for a in range(n_actions))
    informed = 0.0
    for z, mass in enumerate(p_z):
        if mass:
            informed += max(sum(joint_cz[c][z] * utility_ca[c][a] for c in range(n_contexts)) for a in range(n_actions))
    mutual_information = 0.0
    for c in range(n_contexts):
        for z in range(n_signals):
            p = joint_cz[c][z]
            if p:
                mutual_information += p * math.log(p / (p_c[c] * p_z[z]))
    flat_utility = [u for row in utility_ca for u in row]
    utility_range = max(flat_utility) - min(flat_utility)
    bound = utility_range * math.sqrt(max(0.0, mutual_information) / 2.0)
    gross = informed - prior
    return {
        "prior_value": prior, "informed_value": informed, "gross_value": gross,
        "route_cost": route_cost, "net_value": gross - route_cost,
        "mutual_information_nats": mutual_information, "utility_range": utility_range,
        "information_upper_bound": bound, "bound_holds": gross <= bound + 1e-12,
        "information_cannot_pay_route_cost": bound <= route_cost + 1e-12,
    }
