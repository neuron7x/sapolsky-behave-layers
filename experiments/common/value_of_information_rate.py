"""The value-of-information rate function V*(R) and the Pinsker phase transition.

The routability note (`docs/ROUTABILITY_INFORMATION_BOUND.md`) proves the one-sided
ceiling `V(Z) <= Delta_u * sqrt(I(C;Z)/2)` and remarks it "can be loose". This module
answers *exactly when* it is loose by computing the sharp object it bounds — the
value-of-information rate function

    V*(R) = max{ V(Z) : I(C;Z) <= R }          (nats)

— and locating a phase transition in the tightness of the Pinsker ceiling.

Computed law (verified numerically, proved in `docs/VALUE_OF_INFORMATION_RATE_FUNCTION.md`)
------------------------------------------------------------------------------------------
Let ``a0`` be the prior-optimal action. As ``R -> 0``:

  * REGULAR case  (``a0`` unique, strict expected-utility margin):
        V*(R) = sigma * R + o(R),   sigma finite,
    so ``V*(R) / (Delta_u sqrt(R/2)) -> 0`` — the Pinsker ceiling is asymptotically
    INFINITELY LOOSE. The marginal value of the first nat is finite.

  * CRITICAL case (two actions tie in prior expectation — the indifference manifold):
        V*(R) = Delta_u sqrt(R/2) (1 + o(1)),
    so ``V*(R) / (Delta_u sqrt(R/2)) -> 1`` — the Pinsker ceiling is asymptotically
    EXACT. The marginal value of the first nat is INFINITE (sqrt slope).

The critical set ``{ exists a != a0 : E_p U[.,a] = V_fixed }`` has codimension >= 1
(measure zero). Hence for a generic decision problem the information bound is loose;
it is tight exactly on the decision-indifference manifold. This is the decision-
theoretic sharpening of Pinsker's inequality, and it tells the CWC programme that a
positive routability certificate is *conservative* off the indifference manifold —
real routing headroom is smaller than the sqrt-bound suggests unless difficulty sits
right at an indifference boundary.

Scope: the exact solver ``optimal_value_at_rate`` is implemented for a BINARY context
(the regime where the transition is analysed); the proven upper envelope
``min{G, Delta_u sqrt(R/2)}`` and the regime classifier are general.
"""
from __future__ import annotations

import math
from collections.abc import Sequence

Matrix = Sequence[Sequence[float]]
Vector = Sequence[float]
_TOL = 1e-9


# --------------------------------------------------------------------------- #
# Value and information of one channel                                        #
# --------------------------------------------------------------------------- #
def value_and_information(
    utility: Matrix, channel: Matrix, prior: Vector
) -> tuple[float, float]:
    """Return ``(V(Z), I(C;Z))`` in nats for a context->signal ``channel``.

    ``channel[c][z] = P(Z=z | C=c)`` (each row sums to 1); ``prior[c] = p(C=c)``.
    ``V(Z) = sum_z p(z) max_a E[U|z] - max_a E U``; ``I`` is the mutual information.
    """
    n_c = len(utility)
    n_a = len(utility[0])
    n_z = len(channel[0])
    if len(channel) != n_c or len(prior) != n_c:
        raise ValueError("channel and prior must have one row per context")
    if not math.isclose(sum(prior), 1.0, abs_tol=1e-9):
        raise ValueError("prior must sum to one")
    for row in channel:
        if len(row) != n_z or any(x < -1e-12 for x in row) or not math.isclose(sum(row), 1.0, abs_tol=1e-9):
            raise ValueError("each channel row must be a distribution over signals")
    joint = [[prior[c] * channel[c][z] for z in range(n_z)] for c in range(n_c)]
    p_z = [sum(joint[c][z] for c in range(n_c)) for z in range(n_z)]
    prior_value = max(sum(prior[c] * utility[c][a] for c in range(n_c)) for a in range(n_a))
    informed = 0.0
    for z in range(n_z):
        if p_z[z] > _TOL:
            informed += max(sum(joint[c][z] * utility[c][a] for c in range(n_c)) for a in range(n_a))
    value = informed - prior_value
    info = 0.0
    for c in range(n_c):
        for z in range(n_z):
            if joint[c][z] > _TOL:
                info += joint[c][z] * math.log(joint[c][z] / (prior[c] * p_z[z]))
    return value, max(0.0, info)


def oracle_gap_value(utility: Matrix, prior: Vector) -> float:
    """Full oracle gap ``G`` = value of the perfect signal (``V*(inf)``)."""
    n_c, n_a = len(utility), len(utility[0])
    v_oracle = sum(prior[c] * max(utility[c]) for c in range(n_c))
    v_fixed = max(sum(prior[c] * utility[c][a] for c in range(n_c)) for a in range(n_a))
    return v_oracle - v_fixed


def utility_range(utility: Matrix) -> float:
    flat = [u for row in utility for u in row]
    return max(flat) - min(flat)


def pinsker_ceiling(utility: Matrix, rate: float) -> float:
    """The routability ceiling ``Delta_u * sqrt(R/2)`` at rate ``R`` (nats)."""
    if rate < 0:
        raise ValueError("rate must be non-negative")
    return utility_range(utility) * math.sqrt(rate / 2.0)


# --------------------------------------------------------------------------- #
# Regime classification (general)                                             #
# --------------------------------------------------------------------------- #
def prior_optimal_actions(utility: Matrix, prior: Vector, *, tol: float = 1e-9) -> list[int]:
    """Actions attaining ``V_fixed = max_a E_p U[.,a]`` (>=2 => on indifference manifold)."""
    n_c, n_a = len(utility), len(utility[0])
    means = [sum(prior[c] * utility[c][a] for c in range(n_c)) for a in range(n_a)]
    best = max(means)
    return [a for a in range(n_a) if means[a] >= best - tol]


def is_critical(utility: Matrix, prior: Vector, *, tol: float = 1e-9) -> bool:
    """True iff two or more actions tie for the prior optimum (critical/indifference)."""
    return len(prior_optimal_actions(utility, prior, tol=tol)) >= 2


# --------------------------------------------------------------------------- #
# Exact solver for a BINARY context (two signal symbols suffice at optimum)   #
# --------------------------------------------------------------------------- #
def _vi_binary(
    u00: float, u01: float, u10: float, u11: float, p0: float, p1: float,
    prior_value: float, q0: float, q1: float,
) -> tuple[float, float]:
    """Fast inner kernel: (V, I) for a binary-context 2-symbol channel, no validation."""
    # joint pi[c][z]: c in {0,1}, z in {0,1}
    j00, j01 = p0 * (1 - q0), p0 * q0
    j10, j11 = p1 * (1 - q1), p1 * q1
    pz0, pz1 = j00 + j10, j01 + j11
    informed = 0.0
    if pz0 > _TOL:
        informed += max(j00 * u00 + j10 * u10, j00 * u01 + j10 * u11)
    if pz1 > _TOL:
        informed += max(j01 * u00 + j11 * u10, j01 * u01 + j11 * u11)
    value = informed - prior_value
    info = 0.0
    for j, pc, pz in ((j00, p0, pz0), (j01, p0, pz1), (j10, p1, pz0), (j11, p1, pz1)):
        if j > _TOL:
            info += j * math.log(j / (pc * pz))
    return value, info if info > 0.0 else 0.0


def optimal_value_at_rate(
    utility: Matrix, rate: float, prior: Vector = (0.5, 0.5), *, coarse: int = 120, refine: int = 40
) -> float:
    """Exact ``V*(R)`` for a binary context via a two-stage grid over 2-symbol channels.

    A binary-context channel to two signals is parameterised by
    ``(q0, q1) = (P(Z=1|C=0), P(Z=1|C=1))``. ``V`` is convex in the channel, so the
    constrained optimum lies on ``I = R``; a coarse sweep locates it and a local
    refinement sharpens it (needed for accuracy at small ``R``). Returns ``0`` for
    ``R = 0`` and saturates at ``G`` for large ``R``.
    """
    if len(utility) != 2:
        raise ValueError("optimal_value_at_rate is implemented for a binary context")
    if rate < 0:
        raise ValueError("rate must be non-negative")
    if rate == 0.0:
        return 0.0
    u00, u01 = utility[0][0], utility[0][1]
    u10, u11 = utility[1][0], utility[1][1]
    p0, p1 = prior[0], prior[1]
    pv = max(p0 * u00 + p1 * u10, p0 * u01 + p1 * u11)
    thr = rate + 1e-12

    best_v, bq0, bq1 = -1.0, 0.0, 0.0
    for a in range(coarse + 1):
        q0 = a / coarse
        for b in range(coarse + 1):
            q1 = b / coarse
            v, i = _vi_binary(u00, u01, u10, u11, p0, p1, pv, q0, q1)
            if i <= thr and v > best_v:
                best_v, bq0, bq1 = v, q0, q1
    span = 1.0 / coarse
    for _ in range(3 if refine > 0 else 0):
        step = span / refine
        c0, c1 = bq0, bq1
        for a in range(-refine, refine + 1):
            q0 = min(1.0, max(0.0, c0 + a * step))
            for b in range(-refine, refine + 1):
                q1 = min(1.0, max(0.0, c1 + b * step))
                v, i = _vi_binary(u00, u01, u10, u11, p0, p1, pv, q0, q1)
                if i <= thr and v > best_v:
                    best_v, bq0, bq1 = v, q0, q1
        span = step
    return max(0.0, best_v)


# --------------------------------------------------------------------------- #
# Small-rate diagnostics: the phase transition                                #
# --------------------------------------------------------------------------- #
def small_rate_exponent(
    utility: Matrix, prior: Vector = (0.5, 0.5), *, rates: Sequence[float] = (0.02, 0.005, 0.00125)
) -> float:
    """Log-log slope of ``V*(R)`` over small ``R`` (~1 regular, ~0.5 critical)."""
    pts = [(r, optimal_value_at_rate(utility, r, prior)) for r in rates]
    slopes = [
        (math.log(pts[k + 1][1]) - math.log(pts[k][1])) / (math.log(pts[k + 1][0]) - math.log(pts[k][0]))
        for k in range(len(pts) - 1)
        if pts[k][1] > _TOL and pts[k + 1][1] > _TOL
    ]
    return sum(slopes) / len(slopes) if slopes else float("nan")


def pinsker_tightness(utility: Matrix, prior: Vector = (0.5, 0.5), *, rate: float = 0.002) -> dict[str, float | bool]:
    """Report ``V*(R) / (Delta_u sqrt(R/2))`` at small ``R`` and the regime it implies."""
    v = optimal_value_at_rate(utility, rate, prior)
    ceil = pinsker_ceiling(utility, rate)
    ratio = v / ceil if ceil > _TOL else 0.0
    critical = is_critical(utility, prior)
    return {
        "rate": rate,
        "v_star": v,
        "pinsker_ceiling": ceil,
        "tightness_ratio": ratio,
        "is_critical": critical,
        "bound_holds": v <= ceil + 1e-9,
    }


# --------------------------------------------------------------------------- #
# Adversarial falsification harness                                           #
# --------------------------------------------------------------------------- #
class _Rng:
    __slots__ = ("_s",)

    def __init__(self, seed: int) -> None:
        self._s = (seed ^ 0x2545F4914F6CDD1D) & 0xFFFFFFFFFFFFFFFF

    def unit(self) -> float:
        self._s = (6364136223846793005 * self._s + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        return (self._s >> 11) / float(1 << 53)


def falsify_rate_function(seed: int = 20260720, trials: int = 40) -> dict[str, float | int | bool]:
    """Try to break the proved properties of ``V*`` on random binary problems.

    Checks, for each random 2x2 utility: (1) V*(R) <= min{G, Pinsker(R)} at several
    rates (Theorems 3-4); (2) V* is non-decreasing in R; (3) V*(R) -> G at large R
    (saturation). Also confirms the regime dichotomy on the two canonical problems.
    A coarse grid suffices: V* over any grid is a lower estimate, so the bound and
    monotonicity (fixed grid = expanding feasible set) are exercised honestly.
    """
    rng = _Rng(seed)
    bound_violations = 0
    monotone_violations = 0
    saturation_violations = 0
    rates = (0.001, 0.01, 0.05, 0.2, 1.0)
    for _ in range(trials):
        u = [[rng.unit() * 2 - 0.5 for _ in range(2)] for _ in range(2)]
        g = oracle_gap_value(u, (0.5, 0.5))
        prev = -1.0
        for r in rates:
            v = optimal_value_at_rate(u, r, (0.5, 0.5), coarse=64, refine=0)
            if v > min(g, pinsker_ceiling(u, r)) + 1e-6:
                bound_violations += 1
            if v < prev - 1e-6:
                monotone_violations += 1
            prev = v
        v_big = optimal_value_at_rate(u, 5.0, (0.5, 0.5), coarse=64, refine=0)
        if v_big < g - 1e-3:
            saturation_violations += 1

    # dichotomy on canonical problems
    reg = pinsker_tightness([[1.0, 0.0], [0.0, 0.5]])
    crit = pinsker_tightness([[1.0, 0.0], [0.0, 1.0]])
    dichotomy_holds = (
        (not bool(reg["is_critical"])) and float(reg["tightness_ratio"]) < 0.15
        and bool(crit["is_critical"]) and float(crit["tightness_ratio"]) > 0.9
    )
    return {
        "trials": trials,
        "bound_violations": bound_violations,
        "monotone_violations": monotone_violations,
        "saturation_violations": saturation_violations,
        "regular_tightness_ratio": float(reg["tightness_ratio"]),
        "critical_tightness_ratio": float(crit["tightness_ratio"]),
        "dichotomy_holds": dichotomy_holds,
        "all_ok": (
            bound_violations == 0 and monotone_violations == 0
            and saturation_violations == 0 and dichotomy_holds
        ),
    }


if __name__ == "__main__":  # pragma: no cover - CLI summary
    print("VALUE-OF-INFORMATION RATE FUNCTION — Pinsker phase transition\n")
    for label, u in (("REGULAR  [[1,0],[0,0.5]]", [[1.0, 0.0], [0.0, 0.5]]),
                     ("CRITICAL [[1,0],[0,1.0]]", [[1.0, 0.0], [0.0, 1.0]])):
        print(label, " critical =", is_critical(u, (0.5, 0.5)))
        for r in (0.02, 0.005, 0.00125):
            v = optimal_value_at_rate(u, r)
            print(f"    R={r:.5f}  V*={v:.5f}  V*/Pinsker={v / pinsker_ceiling(u, r):.4f}")
        print(f"    small-R exponent ~ {small_rate_exponent(u):.3f}  (1=regular linear, 0.5=critical sqrt)\n")
    rep = falsify_rate_function()
    print("FALSIFICATION:", "ALL OK" if rep["all_ok"] else "VIOLATION", "| dichotomy", rep["dichotomy_holds"])
