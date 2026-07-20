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

import itertools
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
# General-|C| solver (binary signal) — the transition is not a binary artifact #
# --------------------------------------------------------------------------- #
def _vi_general(utility: Matrix, prior: Vector, qs: Sequence[float]) -> tuple[float, float]:
    """Fast (V, I) for a general-context binary-signal channel, ``qs[c]=P(Z=1|C=c)``."""
    n_c, n_a = len(utility), len(utility[0])
    j0 = [prior[c] * (1.0 - qs[c]) for c in range(n_c)]
    j1 = [prior[c] * qs[c] for c in range(n_c)]
    pz0 = sum(j0)
    pz1 = sum(j1)
    prior_v = max(sum(prior[c] * utility[c][a] for c in range(n_c)) for a in range(n_a))
    informed = 0.0
    if pz0 > _TOL:
        informed += max(sum(j0[c] * utility[c][a] for c in range(n_c)) for a in range(n_a))
    if pz1 > _TOL:
        informed += max(sum(j1[c] * utility[c][a] for c in range(n_c)) for a in range(n_a))
    info = 0.0
    for c in range(n_c):
        if j0[c] > _TOL:
            info += j0[c] * math.log(j0[c] / (prior[c] * pz0))
        if j1[c] > _TOL:
            info += j1[c] * math.log(j1[c] / (prior[c] * pz1))
    return informed - prior_v, info if info > 0.0 else 0.0


def optimal_value_at_rate_general(
    utility: Matrix, rate: float, prior: Vector | None = None, *, grid: int = 40
) -> float:
    """Lower bound on ``V*(R)`` for a GENERAL context via a grid over binary-signal
    channels ``(P(Z=1|C=c))_c``.

    Two signal values suffice to expose the small-rate behaviour; the search returns
    the best achievable ``V(Z)`` with ``I <= R`` over the grid, so it is a valid lower
    bound bracketed above by ``min{G, Delta_u sqrt(R/2)}``. Cost is ``grid^|C|`` — this
    confirms the phase transition beyond binary context for ``|C| <= 4``.
    """
    n_c = len(utility)
    p = [1.0 / n_c] * n_c if prior is None else list(prior)
    if (grid + 1) ** n_c > 6_000_000:
        raise ValueError("grid**|C| too large; reduce grid or |C|")
    if rate < 0:
        raise ValueError("rate must be non-negative")
    if rate == 0.0:
        return 0.0
    axis = [i / grid for i in range(grid + 1)]
    best = 0.0
    thr = rate + 1e-12
    for combo in itertools.product(axis, repeat=n_c):
        v, i = _vi_general(utility, p, combo)
        if i <= thr and v > best:
            best = v
    return best


# --------------------------------------------------------------------------- #
# Sharp GENERAL solver via rational inattention (Matejka-McKay fixed point)     #
# --------------------------------------------------------------------------- #
def _rational_inattention(
    utility: Matrix, prior: Vector, beta: float, *, iters: int = 4000, tol: float = 1e-14
) -> tuple[float, float]:
    """Value ``V(Z)`` and information ``I(C;Z)`` at the Shannon-cost optimum for a
    given shadow price ``beta`` (the Lagrangian ``max V - beta*I``).

    Solves the Matejka-McKay fixed point (numerically stabilised softmax):
    ``P(a|c) ∝ P(a) exp(U[c,a]/beta)``, ``P(a) = sum_c p_c P(a|c)``. This IS the
    optimal information structure for a mutual-information cost, so sweeping ``beta``
    traces the sharp rate function for any finite ``|C|, |A|``.
    """
    n_c, n_a = len(utility), len(utility[0])
    p_a = [1.0 / n_a] * n_a
    cond = [[1.0 / n_a] * n_a for _ in range(n_c)]
    for _ in range(iters):
        cond = []
        for c in range(n_c):
            m = max(utility[c])
            logw = [(math.log(p_a[a]) if p_a[a] > 0.0 else -1e300) + (utility[c][a] - m) / beta
                    for a in range(n_a)]
            mx = max(logw)
            w = [math.exp(lw - mx) for lw in logw]
            s = sum(w)
            cond.append([x / s for x in w])
        new_p_a = [sum(prior[c] * cond[c][a] for c in range(n_c)) for a in range(n_a)]
        if max(abs(new_p_a[a] - p_a[a]) for a in range(n_a)) < tol:
            p_a = new_p_a
            break
        p_a = new_p_a
    info = 0.0
    gross = 0.0
    for c in range(n_c):
        for a in range(n_a):
            gross += prior[c] * cond[c][a] * utility[c][a]
            if cond[c][a] > _TOL and p_a[a] > _TOL:
                info += prior[c] * cond[c][a] * math.log(cond[c][a] / p_a[a])
    v_fixed = max(sum(prior[c] * utility[c][a] for c in range(n_c)) for a in range(n_a))
    return gross - v_fixed, max(0.0, info)


def _solve_shadow_price(utility: Matrix, prior: Vector, rate: float) -> float:
    """Bisect the rational-inattention shadow price ``beta`` so that ``I(beta) = rate``
    (``I`` is decreasing in ``beta``)."""
    b_lo, b_hi = 1e-4, 1e7
    for _ in range(80):
        b_mid = math.sqrt(b_lo * b_hi)
        _v, info = _rational_inattention(utility, prior, b_mid)
        if info > rate:            # too much information purchased -> raise the price
            b_lo = b_mid
        else:
            b_hi = b_mid
    return b_hi


def optimal_value_at_rate_ri(
    utility: Matrix, rate: float, prior: Vector | None = None
) -> float:
    """Sharp ``V*(R)`` for GENERAL ``|C|, |A|`` via rational inattention.

    ``I(beta)`` is decreasing in the shadow price ``beta``; bisect on ``log beta`` to
    hit ``I(beta) = R``, then return the value there. Cross-validated: it reproduces
    the closed-form symmetric-critical value to machine precision and matches the exact
    binary grid solver, while strictly exceeding the binary-signal lower bound when
    ``|A| > 2`` (it finds the optimal stochastic channel the grid cannot resolve).
    """
    n_c = len(utility)
    p = [1.0 / n_c] * n_c if prior is None else list(prior)
    if rate < 0 or not math.isfinite(rate):
        raise ValueError("rate must be finite and non-negative")
    if rate == 0.0:
        return 0.0
    value, _info = _rational_inattention(utility, p, _solve_shadow_price(utility, p, rate))
    return max(0.0, value)


def marginal_value_of_information(
    utility: Matrix, rate: float, prior: Vector | None = None
) -> float:
    """The marginal value of information ``beta(R) = dV*/dR`` [utility per nat].

    This is the rational-inattention shadow price at rate ``R``. Since ``beta`` is the
    Lagrange multiplier, ``beta = dV*/dR`` exactly; it is **decreasing** in ``R`` (so
    ``V*`` is CONCAVE), finite as ``R->0`` at a regular problem (the information
    sensitivity ``sigma``) and diverges as ``R->0`` at a critical one (the sqrt onset).
    """
    n_c = len(utility)
    p = [1.0 / n_c] * n_c if prior is None else list(prior)
    if rate <= 0 or not math.isfinite(rate):
        raise ValueError("rate must be finite and positive to price the marginal nat")
    return _solve_shadow_price(utility, p, rate)


# Physical exchange rate: the marginal nat is worth `beta` utility, and every nat
# costs at least k_B*T joules to acquire/erase irreversibly (Landauer, per nat).
_K_B: float = 1.380649e-23  # J/K


def utility_per_joule_ceiling(marginal_value_nats: float, temperature_k: float = 310.15) -> float:
    """Thermodynamic ceiling on decision value per joule: ``beta / (k_B T)`` [utility/J].

    Couples the rate function to the physical substrate (`NEURON_INFORMATION_BUDGET.md`):
    a router that pays ``beta`` utility per nat cannot beat ``beta / (k_B T)`` utility
    per joule, since one nat of erased information costs at least ``k_B T`` joules. The
    same information-market price, now in physical units — the fractal link from the
    abstract decision to the biological substrate.
    """
    if marginal_value_nats < 0 or not math.isfinite(marginal_value_nats):
        raise ValueError("marginal value must be finite and non-negative")
    if temperature_k <= 0:
        raise ValueError("temperature must be positive")
    return marginal_value_nats / (_K_B * temperature_k)


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
# Exact critical constant: Pinsker is ATTAINED at symmetric indifference        #
# --------------------------------------------------------------------------- #
def symmetric_critical_information(t: float) -> float:
    """Mutual information of the symmetric binary channel ``q0=1/2-t, q1=1/2+t``:
    ``I(t) = (1/2+t) ln(1+2t) + (1/2-t) ln(1-2t)`` (nats). ``I(t) = 2 t^2 + O(t^4)``.
    """
    if not (0.0 <= t < 0.5):
        raise ValueError("t must lie in [0, 1/2)")
    if t == 0.0:
        return 0.0
    return (0.5 + t) * math.log(1.0 + 2.0 * t) + (0.5 - t) * math.log(1.0 - 2.0 * t)


def symmetric_critical_value(rate: float, utility_range: float = 1.0) -> float:
    """Exact ``V*(R)`` at a symmetric binary indifference point (``U = Δu·I_2``).

    By symmetry the optimal channel is ``q0=1/2-t, q1=1/2+t`` with two signals; then
    ``V(t) = Δu·t`` and ``I(t) = symmetric_critical_information(t)``. Solving
    ``I(t) = R`` by bisection gives the exact rate function — the ground truth against
    which the grid solver is validated. It obeys ``V*(R)/(Δu√(R/2)) = 1 - R/6 + O(R²)``,
    so the Pinsker ceiling is asymptotically ATTAINED (leading constant exactly 1).
    """
    if rate < 0 or not math.isfinite(rate):
        raise ValueError("rate must be finite and non-negative")
    if utility_range < 0:
        raise ValueError("utility_range must be non-negative")
    if rate == 0.0:
        return 0.0
    lo, hi = 0.0, 0.5 - 1e-15
    if symmetric_critical_information(hi) <= rate:
        return utility_range * hi
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if symmetric_critical_information(mid) < rate:
            lo = mid
        else:
            hi = mid
    return utility_range * 0.5 * (lo + hi)


def critical_pinsker_tightness(rate: float, utility_range: float = 1.0) -> dict[str, float]:
    """Exact ``V*(R)`` vs the Pinsker ceiling at symmetric indifference: ratio -> 1."""
    v = symmetric_critical_value(rate, utility_range)
    ceil = utility_range * math.sqrt(rate / 2.0)
    return {"rate": rate, "v_star": v, "pinsker_ceiling": ceil,
            "ratio": v / ceil if ceil > _TOL else 0.0, "one_minus_ratio": 1.0 - (v / ceil if ceil > _TOL else 0.0)}


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
