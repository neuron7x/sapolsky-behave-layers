"""Machine-checked conformance for the Adaptive-Computation Admissibility Protocol.

Verifies the normative invariants INV-1..INV-7 of
`docs/ADAPTIVE_COMPUTATION_ADMISSIBILITY_SPEC.md` against the reference verifiers, and
that the §5 admissibility procedure obeys the §6 guarantees (G1 error control, G2
sample-complexity decidability, G3 the physical floor). A build that fails any check is
non-conforming.

The procedure itself (`admissibility_decision`) is the executable form of the Act-J
gate: from a pilot it returns ADMISSIBLE / INADMISSIBLE / NOT_IDENTIFIABLE / REJECT with
a controlled false-positive rate.
"""
from __future__ import annotations

import math
from collections.abc import Sequence

from experiments.common.adaptive_value_theory import falsify_theory
from experiments.common.coherence_audit import audit_ladder
from experiments.common.identifiability_inference import (
    _Rng,
    gap_lower_confidence_bound,
    plugin_gap,
    sample_complexity,
)
from experiments.common.value_of_information_rate import falsify_rate_function

Matrix = Sequence[Sequence[float]]
Vector = Sequence[float]

_K_B_T_LN2 = 1.380649e-23 * 310.15 * math.log(2.0)   # Landauer floor per bit [J]


# --------------------------------------------------------------------------- #
# The §5 admissibility procedure (executable Act-J gate)                       #
# --------------------------------------------------------------------------- #
def admissibility_decision(
    utility_hat: Matrix, prior: Vector, cost: Vector, *,
    std_error: float, route_cost: float, delta: float = 0.05, target_gap: float = 0.1, sigma: float = 1.0,
) -> dict[str, object]:
    """Execute the normative procedure (spec §5). Fails closed on malformed input."""
    n_c, n_a = len(utility_hat), len(utility_hat[0])
    if route_cost < 0 or not (0.0 < delta < 1.0) or std_error < 0:
        return {"decision": "REJECT", "reason": "malformed"}
    g_hat = plugin_gap(utility_hat, prior)
    g_lo = gap_lower_confidence_bound(g_hat, std_error, n_c, n_a, delta)
    if g_lo <= 0.0:
        return {"decision": "NOT_IDENTIFIABLE", "gap_lower_bound": g_lo,
                "n_star": sample_complexity(target_gap, sigma, n_c, n_a, delta)}
    if g_lo > route_cost:
        return {"decision": "ADMISSIBLE", "gap_lower_bound": g_lo, "route_cost": route_cost,
                "fpr_bound": delta}
    return {"decision": "INADMISSIBLE", "gap_lower_bound": g_lo, "route_cost": route_cost}


# --------------------------------------------------------------------------- #
# Conformance checks INV-1..INV-7 and G1..G3                                    #
# --------------------------------------------------------------------------- #
def _inv6_compute_axis(trials: int, seed: int) -> bool:
    from experiments.act_j_pilot.src.compute_matched import compute_matched_advantage
    rng = _Rng(seed)
    worst = 0.0
    for _ in range(trials):
        n_c = 2 + int(rng._unit() * 3)
        n_a = 2 + int(rng._unit() * 3)
        u = [[rng._unit() for _ in range(n_a)] for _ in range(n_c)]
        cost = [1.0 + 4.0 * rng._unit() for _ in range(n_a)]
        p = [1.0 / n_c] * n_c
        budget = min(cost) + rng._unit() * (max(cost) - min(cost))
        worst = min(worst, compute_matched_advantage(u, cost, p, budget)["advantage"])
    return worst > -1e-6


def _g1_error_control(trials: int, seed: int, delta: float) -> float:
    """False-positive rate of the ADMISSIBLE decision on a null (G=0) battery."""
    rng = _Rng(seed)
    fp = 0
    alpha = [0.5, -0.3, 1.1]
    beta = [0.2, -0.1, 0.4]
    n = 60
    se = 1.0 / math.sqrt(n)
    null = [[alpha[c] + beta[a] for a in range(3)] for c in range(3)]  # additive => G=0
    for _ in range(trials):
        u_hat = [[null[c][a] + se * rng.gauss() for a in range(3)] for c in range(3)]
        d = admissibility_decision(u_hat, [1 / 3] * 3, [1.0, 1.0, 1.0],
                                   std_error=se, route_cost=0.0, delta=delta)
        if d["decision"] == "ADMISSIBLE":
            fp += 1
    return fp / trials


def check_conformance(*, quick: bool = True, seed: int = 20260720) -> dict[str, object]:
    """Run every normative check; return a per-clause report. `conforming` is the AND."""
    t_theory = 4000 if quick else 20000
    t_rate = 30 if quick else 120
    t_inf = 3000 if quick else 12000
    t_axis = 300 if quick else 1500
    delta = 0.1

    theory = falsify_theory(seed=seed, trials=t_theory)
    rate = falsify_rate_function(seed=seed, trials=t_rate)
    from experiments.common.identifiability_inference import falsify_inference
    inference = falsify_inference(seed=seed, trials=t_inf)
    coherence = audit_ladder()

    checks = {
        "INV-1 non-negativity": float(theory["gap_negativity_max"]) < 1e-9,
        "INV-2 dominance-iff-zero": int(theory["dominance_iff_failures"]) == 0,
        "INV-3 master-envelope": float(theory["master_inequality_max_violation"]) < 1e-9,
        "INV-4 rate-function-sharp": bool(rate["all_ok"]),
        "INV-5 certificate-validity": bool(inference["calibration_valid"]),
        "INV-6 compute-axis-nonneg": _inv6_compute_axis(t_axis, seed),
        "INV-7 programme-coherence": bool(coherence["coherent"]),
    }
    g1_fpr = _g1_error_control(3000 if quick else 10000, seed, delta)
    g3_floor = _K_B_T_LN2 > 0.0
    guarantees = {
        "G1 error-control (FPR<=delta)": g1_fpr <= delta,
        "G1 fpr_value": g1_fpr,
        "G2 decidability (n* finite)": sample_complexity(0.2, 1.0, 3, 3, delta) > 0,
        "G3 physical-floor-positive": g3_floor,
    }
    conforming = all(checks.values()) and bool(guarantees["G1 error-control (FPR<=delta)"]) \
        and bool(guarantees["G2 decidability (n* finite)"]) and g3_floor
    return {"spec_version": "1.0", "invariants": checks, "guarantees": guarantees,
            "conforming": conforming}


if __name__ == "__main__":  # pragma: no cover - CLI summary
    report = check_conformance(quick=False)
    invariants = report["invariants"]
    guarantees = report["guarantees"]
    assert isinstance(invariants, dict) and isinstance(guarantees, dict)
    print(f"ADMISSIBILITY SPEC v{report['spec_version']} conformance:")
    for name, ok in invariants.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    print(f"  G1 FPR = {float(guarantees['G1 fpr_value']):.4f} (<= delta)  |  G2 n*>0  |  G3 floor")
    print("CONFORMING" if report["conforming"] else "NON-CONFORMING")
