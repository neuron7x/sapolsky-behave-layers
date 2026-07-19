"""A unified, self-certifying theory of the value of adaptive computation.

This module is the *executable* half of `docs/ADAPTIVE_COMPUTATION_VALUE_THEORY.md`.
It formalises, and re-derives from first principles, the three certificates that
independently bound how much a context-adaptive controller can beat a fixed policy:

  1. the ORACLE GAP  ``G = V_oracle - V_fixed``  (value under a *free, perfect*
     view of context) and its exact ANOVA decomposition;
  2. the INFORMATION CEILING  ``V(Z) <= Delta_u * sqrt(I(C;Z)/2)``  (value under a
     *finite* router-visible signal ``Z``), sharp up to the Pinsker constant;
  3. the ROUTE-DECISION COST  ``c_route``  charged to actually computing the choice.

The master inequality (Theorem 6) unifies them:

    V_net  <=  min( G ,  Delta_u * sqrt(I(C;Z)/2) )  -  c_route .

Every function is pure finite arithmetic with NO third-party dependency, fails
closed on malformed input, and is exercised by an adversarial falsification
harness (:func:`falsify_theory`) that would surface any violation of the theorems
to machine precision. "A test that cannot fail is not a test": the harness is
built to *try* to break each inequality on thousands of random decision problems.

Conventions
-----------
* ``C`` is a finite context set (rows), ``A`` a finite action/mechanism set
  (columns), ``Z`` a finite router-visible signal.
* ``utility[c][a]`` is bounded utility; ``prior[c]`` is the context law (sums to 1).
* ``joint_cz[c][z]`` is the joint law of ``(C, Z)`` (sums to 1).
* Mutual information is in **nats** (natural log), matching the Pinsker constant
  ``1/2`` used throughout.
"""
from __future__ import annotations

import math
from collections.abc import Sequence

_TOL = 1e-12

Matrix = Sequence[Sequence[float]]
Vector = Sequence[float]


# --------------------------------------------------------------------------- #
# Validation (fail closed)                                                     #
# --------------------------------------------------------------------------- #
def _check_matrix(m: Matrix, name: str) -> tuple[int, int]:
    if not m or not m[0]:
        raise ValueError(f"{name} must be a non-empty matrix")
    width = len(m[0])
    if any(len(row) != width for row in m):
        raise ValueError(f"{name} must be rectangular")
    if any(not math.isfinite(x) for row in m for x in row):
        raise ValueError(f"{name} entries must be finite")
    return len(m), width


def _check_prior(p: Vector, n_contexts: int) -> None:
    if len(p) != n_contexts:
        raise ValueError("prior must have one weight per context")
    if any(w < 0 or not math.isfinite(w) for w in p):
        raise ValueError("prior weights must be finite and non-negative")
    if not math.isclose(sum(p), 1.0, rel_tol=0.0, abs_tol=1e-9):
        raise ValueError("prior weights must sum to one")


def _uniform(n: int) -> list[float]:
    return [1.0 / n] * n


# --------------------------------------------------------------------------- #
# Theorem 1 — oracle gap and its exact ANOVA decomposition                     #
# --------------------------------------------------------------------------- #
def oracle_gap(utility: Matrix, prior: Vector | None = None) -> dict[str, float | bool]:
    """Oracle gap ``G = V_oracle - V_fixed`` with its ANOVA-decomposition identity.

    ``V_oracle = E_c max_a U[c,a]`` (choose per context); ``V_fixed = max_a E_c U[c,a]``
    (one choice for all). Writing the weighted two-way ANOVA
    ``U = mu + alpha_c + beta_a + gamma[c,a]``, Theorem 1 states

        G = E_c[ max_a ( beta_a + gamma[c,a] ) ] - max_a beta_a ,

    and ``G >= 0`` always (Jensen). ``gap_matches_decomposition`` re-derives ``G``
    through the ANOVA path and asserts equality to machine precision, so the
    identity is *checked*, not asserted.

    ``weakly_dominant`` is True iff some action attains the per-context maximum in
    every context of positive prior mass — the exact ``G = 0`` condition (Theorem 2).
    """
    n_c, n_a = _check_matrix(utility, "utility")
    p = _uniform(n_c) if prior is None else list(prior)
    _check_prior(p, n_c)

    mu = sum(p[c] * utility[c][a] for c in range(n_c) for a in range(n_a)) / n_a
    beta = [sum(p[c] * utility[c][a] for c in range(n_c)) - mu for a in range(n_a)]
    alpha = [sum(utility[c][a] for a in range(n_a)) / n_a - mu for c in range(n_c)]
    gamma = [[utility[c][a] - mu - alpha[c] - beta[a] for a in range(n_a)] for c in range(n_c)]

    v_oracle = sum(p[c] * max(utility[c]) for c in range(n_c))
    v_fixed = max(sum(p[c] * utility[c][a] for c in range(n_c)) for a in range(n_a))
    gap = v_oracle - v_fixed
    gap_via_anova = sum(p[c] * max(beta[a] + gamma[c][a] for a in range(n_a)) for c in range(n_c)) - max(beta)

    # G = 0  <=>  exists a* attaining the per-context argmax on every positive-mass context.
    row_max = [max(utility[c]) for c in range(n_c)]
    weakly_dominant = any(
        all(p[c] == 0.0 or utility[c][a] >= row_max[c] - _TOL for c in range(n_c))
        for a in range(n_a)
    )
    return {
        "v_oracle": v_oracle,
        "v_fixed": v_fixed,
        "gap": gap,
        "gap_via_anova": gap_via_anova,
        "gap_matches_decomposition": math.isclose(gap, gap_via_anova, rel_tol=0.0, abs_tol=1e-9),
        "gap_nonnegative": gap >= -1e-12,
        "weakly_dominant": weakly_dominant,
        "gap_is_zero": abs(gap) <= 1e-9,
    }


# --------------------------------------------------------------------------- #
# Theorems 3 & 4 — signal value, data-processing ceiling, information ceiling  #
# --------------------------------------------------------------------------- #
def signal_value(joint_cz: Matrix, utility: Matrix, *, route_cost: float = 0.0) -> dict[str, float | bool]:
    """Value of a *finite* router-visible signal ``Z`` and the two ceilings on it.

    ``V(Z) = E_z max_a E[U(C,a)|Z=z] - max_a E U(C,a)``. Theorem 3 (data
    processing / Blackwell): ``0 <= V(Z) <= G``, where ``G`` is the oracle gap on
    the true context. Theorem 4 (sharp Pinsker):
    ``V(Z) <= Delta_u * sqrt(I(C;Z)/2)`` with ``I`` in nats. The realized net
    value after paying the routing decision is ``V(Z) - route_cost``.
    """
    n_c, n_z = _check_matrix(joint_cz, "joint_cz")
    n_c2, n_a = _check_matrix(utility, "utility")
    if n_c2 != n_c:
        raise ValueError("utility must have one row per context of joint_cz")
    if any(x < 0 for row in joint_cz for x in row):
        raise ValueError("joint probabilities must be non-negative")
    if not math.isclose(sum(map(sum, joint_cz)), 1.0, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("joint probabilities must sum to one")
    if route_cost < 0 or not math.isfinite(route_cost):
        raise ValueError("route_cost must be finite and non-negative")

    p_c = [sum(joint_cz[c]) for c in range(n_c)]
    p_z = [sum(joint_cz[c][z] for c in range(n_c)) for z in range(n_z)]

    prior_value = max(sum(p_c[c] * utility[c][a] for c in range(n_c)) for a in range(n_a))
    informed_value = 0.0
    for z in range(n_z):
        if p_z[z] > 0.0:
            informed_value += max(
                sum(joint_cz[c][z] * utility[c][a] for c in range(n_c)) for a in range(n_a)
            )
    signal_gap = informed_value - prior_value

    mutual_information = 0.0
    for c in range(n_c):
        for z in range(n_z):
            pcz = joint_cz[c][z]
            if pcz > 0.0:
                mutual_information += pcz * math.log(pcz / (p_c[c] * p_z[z]))

    flat = [u for row in utility for u in row]
    utility_range = max(flat) - min(flat)
    information_bound = utility_range * math.sqrt(max(0.0, mutual_information) / 2.0)

    # oracle gap on the TRUE context, using the marginal p_c as the context law
    oracle = oracle_gap(utility, p_c) if all(p_c) else oracle_gap(utility, [w if w else 0.0 for w in p_c])
    oracle_gap_value = float(oracle["gap"])

    return {
        "prior_value": prior_value,
        "informed_value": informed_value,
        "signal_gap": signal_gap,
        "route_cost": route_cost,
        "net_value": signal_gap - route_cost,
        "mutual_information_nats": mutual_information,
        "utility_range": utility_range,
        "information_bound": information_bound,
        "oracle_gap": oracle_gap_value,
        "signal_nonnegative": signal_gap >= -1e-12,
        "data_processing_holds": signal_gap <= oracle_gap_value + 1e-9,
        "information_bound_holds": signal_gap <= information_bound + 1e-9,
        "master_bound": min(oracle_gap_value, information_bound) - route_cost,
    }


def total_variation(p: Vector, q: Vector) -> float:
    """Total variation distance ``(1/2) * sum |p_i - q_i|`` between two laws."""
    if len(p) != len(q):
        raise ValueError("distributions must have equal support")
    return 0.5 * sum(abs(pi - qi) for pi, qi in zip(p, q, strict=True))


# --------------------------------------------------------------------------- #
# Theorem 5 — the budgeted identifiability window                              #
# --------------------------------------------------------------------------- #
def budgeted_gap(utility: Matrix, cost: Vector, lam: float, prior: Vector | None = None) -> dict[str, float | bool]:
    """Oracle gap of the Lagrangian utility ``U_lambda[c,a] = U[c,a] - lam * K[a]``.

    Both ``V_oracle(lam)`` and ``V_fixed(lam)`` are convex, piecewise-linear and
    non-increasing in ``lam`` (Theorem 5). The additive per-action shift
    ``-lam*K[a]`` leaves the interaction ``gamma`` unchanged, so identifiability is
    driven purely by how the shift reorders the per-context argmax.
    """
    n_c, n_a = _check_matrix(utility, "utility")
    if len(cost) != n_a:
        raise ValueError("cost must have one entry per action")
    if any(k < 0 or not math.isfinite(k) for k in cost):
        raise ValueError("costs must be finite and non-negative")
    if not math.isfinite(lam):
        raise ValueError("lambda must be finite")
    adjusted = [[utility[c][a] - lam * cost[a] for a in range(n_a)] for c in range(n_c)]
    return oracle_gap(adjusted, prior)


def saturation_lambda(utility: Matrix, cost: Vector, prior: Vector | None = None) -> dict[str, float | bool]:
    """Explicit cost-saturation certificate (Theorem 5).

    If the cheapest action is unique with cost margin ``delta = min_{a != a0}
    (K[a] - K[a0]) > 0`` and utility range ``R``, then for every ``lam > R / delta``
    the cheapest action is the pointwise argmax in every context, so it weakly
    dominates and ``G(lam) = 0``. The identifiable set therefore lies in the
    bounded window ``[0, R/delta]``.
    """
    _n_c, n_a = _check_matrix(utility, "utility")
    if len(cost) != n_a:
        raise ValueError("cost must have one entry per action")
    flat = [u for row in utility for u in row]
    util_range = max(flat) - min(flat)
    order = sorted(range(n_a), key=lambda a: cost[a])
    cheapest = order[0]
    unique_cheapest = n_a == 1 or cost[order[1]] > cost[cheapest] + _TOL
    if not unique_cheapest:
        return {"unique_cheapest": False, "lambda_star": math.inf, "gap_above_star_is_zero": True}
    delta = 0.0 if n_a == 1 else cost[order[1]] - cost[cheapest]
    lambda_star = 0.0 if n_a == 1 else util_range / delta
    probe = lambda_star * (1.0 + 1e-6) + 1e-9
    gap_above = float(budgeted_gap(utility, cost, probe, prior)["gap"])
    return {
        "unique_cheapest": True,
        "utility_range": util_range,
        "cost_margin": delta,
        "lambda_star": lambda_star,
        "gap_above_star_is_zero": abs(gap_above) <= 1e-9,
    }


def identifiable_window(
    utility: Matrix, cost: Vector, prior: Vector | None = None, *, grid: int = 256
) -> dict[str, float | bool]:
    """Sample ``G(lam)`` on ``[0, lambda_star]`` and report the identifiable span.

    Returns the max gap and the smallest/largest ``lam`` with ``G(lam) > 0`` on the
    grid. Because ``V_oracle`` and ``V_fixed`` are piecewise-linear (finitely many
    breakpoints), ``{lam : G(lam) > 0}`` is a finite union of intervals inside the
    bounded window — the grid witnesses that structure.
    """
    sat = saturation_lambda(utility, cost, prior)
    upper = float(sat["lambda_star"])
    if not math.isfinite(upper) or upper <= 0.0:
        upper = 1.0
    best_gap = 0.0
    best_lambda = 0.0
    lo = math.inf
    hi = -math.inf
    for i in range(grid + 1):
        lam = upper * 1.25 * i / grid
        g = float(budgeted_gap(utility, cost, lam, prior)["gap"])
        if g > best_gap:
            best_gap, best_lambda = g, lam
        if g > 1e-9:
            lo = min(lo, lam)
            hi = max(hi, lam)
    identifiable = best_gap > 1e-9
    return {
        "lambda_star": float(sat["lambda_star"]),
        "max_gap": best_gap,
        "argmax_lambda": best_lambda,
        "window_lo": lo if identifiable else 0.0,
        "window_hi": hi if identifiable else 0.0,
        "identifiable_somewhere": identifiable,
    }


# --------------------------------------------------------------------------- #
# Adversarial falsification harness                                            #
# --------------------------------------------------------------------------- #
class _Rng:
    """Deterministic LCG (no ``random`` import needed at module import time)."""

    __slots__ = ("_s",)

    def __init__(self, seed: int) -> None:
        self._s = (seed ^ 0x2545F4914F6CDD1D) & 0xFFFFFFFFFFFFFFFF

    def uniform(self, lo: float, hi: float) -> float:
        self._s = (6364136223846793005 * self._s + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        frac = (self._s >> 11) / float(1 << 53)
        return lo + (hi - lo) * frac

    def randint(self, lo: int, hi: int) -> int:
        return lo + int(self.uniform(0.0, float(hi - lo + 1))) % (hi - lo + 1)


def falsify_theory(seed: int = 20260720, trials: int = 2000) -> dict[str, float | int | bool]:
    """Try to break every theorem on ``trials`` random decision problems.

    Returns the worst observed violation of each inequality/identity. All
    ``*_max_violation`` fields must be within numerical tolerance of zero; any
    positive value is a genuine counterexample to a stated theorem.
    """
    rng = _Rng(seed)
    worst_decomp = 0.0
    worst_gap_neg = 0.0
    worst_dominance = 0
    worst_dp = 0.0
    worst_info = 0.0
    worst_master = 0.0
    worst_sat = 0

    for _ in range(trials):
        n_c = rng.randint(2, 4)
        n_a = rng.randint(2, 4)
        n_z = rng.randint(1, 4)
        utility = [[rng.uniform(-5.0, 7.0) for _ in range(n_a)] for _ in range(n_c)]
        raw = [[rng.uniform(0.0, 1.0) for _ in range(n_z)] for _ in range(n_c)]
        tot = sum(map(sum, raw))
        joint = [[raw[c][z] / tot for z in range(n_z)] for c in range(n_c)]

        og = oracle_gap(utility)
        worst_decomp = max(worst_decomp, abs(float(og["gap"]) - float(og["gap_via_anova"])))
        worst_gap_neg = max(worst_gap_neg, -float(og["gap"]))
        # Theorem 2, exact iff: weakly_dominant <=> gap == 0
        if bool(og["weakly_dominant"]) != bool(og["gap_is_zero"]):
            worst_dominance += 1

        sv = signal_value(joint, utility, route_cost=rng.uniform(0.0, 2.0))
        worst_dp = max(worst_dp, float(sv["signal_gap"]) - float(sv["oracle_gap"]))
        worst_info = max(worst_info, float(sv["signal_gap"]) - float(sv["information_bound"]))
        # master inequality: net_value <= min(G, info_bound) - route_cost
        worst_master = max(worst_master, float(sv["net_value"]) - float(sv["master_bound"]))

        cost = [rng.uniform(0.0, 3.0) for _ in range(n_a)]
        sat = saturation_lambda(utility, cost)
        if bool(sat["unique_cheapest"]) and not bool(sat["gap_above_star_is_zero"]):
            worst_sat += 1

    return {
        "trials": trials,
        "decomposition_max_violation": worst_decomp,
        "gap_negativity_max": worst_gap_neg,
        "dominance_iff_failures": worst_dominance,
        "data_processing_max_violation": worst_dp,
        "information_bound_max_violation": worst_info,
        "master_inequality_max_violation": worst_master,
        "saturation_failures": worst_sat,
        "all_theorems_hold": (
            worst_decomp < 1e-9
            and worst_gap_neg < 1e-9
            and worst_dominance == 0
            and worst_dp < 1e-9
            and worst_info < 1e-9
            and worst_master < 1e-9
            and worst_sat == 0
        ),
    }


if __name__ == "__main__":  # pragma: no cover - CLI summary
    report = falsify_theory()
    for key, value in report.items():
        print(f"{key:38s} = {value}")
