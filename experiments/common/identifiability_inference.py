"""From impossibility ceilings to statistical inference: a calibrated identifiability
certificate that decides, from a finite pilot, whether adaptive compute can pay.

Everything upstream (value theory, rate function, coherence audit) proves UPPER
bounds — *when adaptation cannot pay*. This module supplies the missing inferential
step: a one-sided, finite-sample, error-controlled certificate for whether a
benchmark is identifiable (``G > 0``), so the decisive Act J cloud run can be
committed or refused with a guaranteed false-positive rate.

The mathematical obstruction it clears
--------------------------------------
The oracle gap ``G = E_c max_a U[c,a] - max_a E_c U[c,a]`` is a NON-SMOOTH functional
of ``U``: the ``max`` makes the plug-in estimate from a noisy pilot **biased upward**
(Jensen). So the naive rule "estimate G-hat, spend if G-hat > 0" has an *uncontrolled*
false-positive rate — on a truly non-identifiable (``G=0``) benchmark it fires more
than half the time at a small pilot. A valid certificate must subtract BOTH the
max-operator's optimism AND the sampling fluctuation:

    G_lo := G-hat  -  b(sd, |A|)  -  d(sd, |C|, delta),
      b = sd * sqrt(2 ln|A|)                    (max-of-sub-Gaussians upward bias),
      d = (sd / sqrt|C|) * sqrt(2 ln(2/delta))  (deviation of the context average),

where ``sd = sigma / sqrt(n)`` is the per-cell standard error of the pilot mean.

> **Theorem (valid one-sided certificate).** For sub-Gaussian pilot noise,
> ``P(G >= G_lo) >= 1 - delta``. Hence ``G_lo > 0`` certifies identifiability, and
> ``G_lo > c_route`` certifies positive net value, each with false-positive rate at
> most ``delta``.

Verified by simulation (`calibration_experiment`, `falsify_inference`): on null
(``G=0``) problems the calibrated false-positive rate is ``<= delta`` while the naive
rule's exceeds ``0.5`` at a small pilot; on separated alternatives the power ``-> 1``.
A matching **sample-complexity** bound gives the pilot size that guarantees power.

This is the break from a converse-only theory to a two-sided, decidable one: the
same value-vs-cost inequality now yields an *action* — spend, or don't — with proof.
"""
from __future__ import annotations

import math
from collections.abc import Sequence

Matrix = Sequence[Sequence[float]]
Vector = Sequence[float]


def _validate_matrix(matrix: Matrix, *, name: str) -> tuple[int, int]:
    """Return matrix shape after rejecting vacuous, ragged, or non-finite inputs."""
    if not matrix or not matrix[0]:
        raise ValueError(f"{name} must be non-empty")
    n_actions = len(matrix[0])
    if any(len(row) != n_actions for row in matrix):
        raise ValueError(f"{name} must be rectangular")
    if any(not math.isfinite(value) for row in matrix for value in row):
        raise ValueError(f"{name} values must be finite")
    return len(matrix), n_actions


def _validate_bound_inputs(
    gap_hat: float,
    std_error: float,
    n_contexts: int,
    n_actions: int,
    delta: float,
) -> None:
    if not math.isfinite(gap_hat):
        raise ValueError("gap_hat must be finite")
    if not math.isfinite(std_error) or std_error < 0:
        raise ValueError("std_error must be finite and non-negative")
    if n_contexts < 1 or n_actions < 1:
        raise ValueError("n_contexts and n_actions must be positive")
    if not math.isfinite(delta) or not 0.0 < delta < 1.0:
        raise ValueError("delta must lie in (0,1)")


# --------------------------------------------------------------------------- #
# Point estimate and its correction terms                                     #
# --------------------------------------------------------------------------- #
def plugin_gap(utility_hat: Matrix, prior: Vector | None = None) -> float:
    """Plug-in oracle gap ``G-hat = E_c max_a U-hat - max_a E_c U-hat`` (upward biased)."""
    n_c, n_a = _validate_matrix(utility_hat, name="utility_hat")
    p = [1.0 / n_c] * n_c if prior is None else list(prior)
    if (
        len(p) != n_c
        or any(not math.isfinite(weight) or weight < 0 for weight in p)
        or not math.isclose(math.fsum(p), 1.0, rel_tol=0.0, abs_tol=1e-12)
    ):
        raise ValueError("prior must be a distribution over contexts")
    v_oracle = math.fsum(p[c] * max(utility_hat[c]) for c in range(n_c))
    v_fixed = max(
        math.fsum(p[c] * utility_hat[c][a] for c in range(n_c))
        for a in range(n_a)
    )
    return v_oracle - v_fixed


def oracle_bias_bound(std_error: float, n_actions: int) -> float:
    """Upper bound on the plug-in oracle term's upward bias: ``sd*sqrt(2 ln|A|)``."""
    if not math.isfinite(std_error) or std_error < 0 or n_actions < 1:
        raise ValueError("std_error must be finite and >= 0; n_actions must be >= 1")
    return std_error * math.sqrt(2.0 * math.log(max(2, n_actions)))


def deviation_bound(std_error: float, n_contexts: int, delta: float) -> float:
    """One-sided sub-Gaussian deviation of the context-averaged estimate at level delta."""
    if not math.isfinite(delta) or not 0.0 < delta < 1.0:
        raise ValueError("delta must lie in (0,1)")
    if not math.isfinite(std_error) or std_error < 0 or n_contexts < 1:
        raise ValueError("finite std_error >= 0 and n_contexts >= 1 required")
    return std_error / math.sqrt(n_contexts) * math.sqrt(2.0 * math.log(2.0 / delta))


def gap_lower_confidence_bound(
    gap_hat: float, std_error: float, n_contexts: int, n_actions: int, delta: float
) -> float:
    """Valid ``1-delta`` lower confidence bound ``G_lo`` on the true oracle gap."""
    _validate_bound_inputs(gap_hat, std_error, n_contexts, n_actions, delta)
    return gap_hat - oracle_bias_bound(std_error, n_actions) - deviation_bound(std_error, n_contexts, delta)


def gap_lower_confidence_bound_corrected(
    gap_hat: float, std_error: float, n_contexts: int, n_actions: int, delta: float
) -> float:
    """Proof-complete ``1-delta`` lower bound: budgets BOTH deviation terms, union-bounded.

    Closes the gap flagged in the audit of ``docs/IDENTIFIABILITY_INFERENCE.md``: the original
    ``gap_lower_confidence_bound`` bounds only the *expectation* of the oracle-term overshoot
    (``E[O] <= b``) and allocates the whole deviation budget to the fixed term ``F``, with no
    separate concentration term for ``O``. Decompose ``G-hat - G = O - F`` with
    ``O = V-hat_oracle - V_oracle`` and ``F = V-hat_fixed - V_fixed``. Then, for sub-Gaussian
    per-cell noise with per-context independence:

      * ``E[O] <= b = sd*sqrt(2 ln|A|)``          (max-operator optimism), and
      * ``O - E[O]`` concentrates:  ``<= d`` w.p. ``1 - delta/2``  (average of |C| context terms),
      * ``V_fixed - V-hat_fixed <= d`` w.p. ``1 - delta/2``,

    with ``d = deviation_bound(sd, |C|, delta/2)``. Union bound gives
    ``P(G-hat - G <= b + 2d) >= 1 - delta``, hence ``P(G >= G-hat - b - 2d) >= 1 - delta``.
    Strictly more conservative than the original; empirically the identifiability positives
    survive it (see ``experiments/wp7_certificate_hardening``).
    """
    _validate_bound_inputs(gap_hat, std_error, n_contexts, n_actions, delta)
    b = oracle_bias_bound(std_error, n_actions)
    d = deviation_bound(std_error, n_contexts, delta / 2.0)
    return gap_hat - b - 2.0 * d


def certify_identifiable(
    gap_hat: float, std_error: float, n_contexts: int, n_actions: int, *, delta: float = 0.05
) -> dict[str, float | bool]:
    """Certify ``G>0`` (and optionally ``G>c_route``) with false-positive rate <= delta."""
    g_lo = gap_lower_confidence_bound(gap_hat, std_error, n_contexts, n_actions, delta)
    return {
        "gap_hat": gap_hat,
        "gap_lower_bound": g_lo,
        "delta": delta,
        "identifiable": g_lo > 0.0,
    }


def certifies_positive_value(
    gap_hat: float, std_error: float, n_contexts: int, n_actions: int, route_cost: float, *, delta: float = 0.05
) -> bool:
    """True iff the pilot certifies ``G - c_route > 0`` at confidence ``1-delta``."""
    if not math.isfinite(route_cost) or route_cost < 0:
        raise ValueError("route_cost must be finite and non-negative")
    return gap_lower_confidence_bound(gap_hat, std_error, n_contexts, n_actions, delta) > route_cost


def sample_complexity(true_gap: float, sigma: float, n_contexts: int, n_actions: int, delta: float) -> int:
    """Pilot size ``n`` per cell that makes ``G_lo > 0`` at true gap ``true_gap``.

    Solving ``G > (sigma/sqrt n)[sqrt(2 ln|A|) + sqrt(2 ln(2/delta))/sqrt|C|]`` for n:
    ``n* = ceil( (sigma * K / G)^2 )`` with ``K`` the bracketed constant.
    """
    _validate_bound_inputs(true_gap, sigma, n_contexts, n_actions, delta)
    if true_gap <= 0:
        raise ValueError("true_gap must be positive to be certifiable")
    k = math.sqrt(2.0 * math.log(max(2, n_actions))) + math.sqrt(2.0 * math.log(2.0 / delta)) / math.sqrt(n_contexts)
    return max(1, math.ceil((sigma * k / true_gap) ** 2))


# --------------------------------------------------------------------------- #
# Deterministic Gaussian RNG (Box-Muller over an LCG)                          #
# --------------------------------------------------------------------------- #
class _Rng:
    __slots__ = ("_s",)

    def __init__(self, seed: int) -> None:
        self._s = (seed ^ 0x2545F4914F6CDD1D) & 0xFFFFFFFFFFFFFFFF

    def _unit(self) -> float:
        self._s = (6364136223846793005 * self._s + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        return (self._s >> 11) / float(1 << 53)

    def gauss(self) -> float:
        u1 = max(1e-12, self._unit())
        u2 = self._unit()
        return math.sqrt(-2.0 * math.log(u1)) * math.cos(2.0 * math.pi * u2)


def _noisy(utility: Matrix, std_error: float, rng: _Rng) -> list[list[float]]:
    _validate_matrix(utility, name="utility")
    if not math.isfinite(std_error) or std_error < 0:
        raise ValueError("std_error must be finite and non-negative")
    return [[utility[c][a] + std_error * rng.gauss() for a in range(len(utility[0]))] for c in range(len(utility))]


# --------------------------------------------------------------------------- #
# Calibration and power (the empirical proof of validity)                      #
# --------------------------------------------------------------------------- #
def calibration_experiment(
    null_utility: Matrix, alt_utility: Matrix, std_error: float, *, delta: float = 0.1,
    trials: int = 3000, seed: int = 20260720,
) -> dict[str, float]:
    """Measure naive vs calibrated false-positive rate on a null and power on an alt.

    Returns ``naive_fpr`` (uncontrolled), ``calibrated_fpr`` (must be <= delta), and
    ``power`` (P[certify | alt]). Contexts/actions are read from the matrices.
    """
    n_c, n_a = _validate_matrix(null_utility, name="null_utility")
    _validate_matrix(alt_utility, name="alt_utility")
    _validate_bound_inputs(0.0, std_error, n_c, n_a, delta)
    if trials < 1:
        raise ValueError("trials must be positive")
    rng = _Rng(seed)
    naive_fp = calib_fp = 0
    for _ in range(trials):
        g_hat = plugin_gap(_noisy(null_utility, std_error, rng))
        if g_hat > 0.0:
            naive_fp += 1
        if gap_lower_confidence_bound(g_hat, std_error, n_c, n_a, delta) > 0.0:
            calib_fp += 1
    power = 0
    na2, nc2 = len(alt_utility[0]), len(alt_utility)
    for _ in range(trials):
        g_hat = plugin_gap(_noisy(alt_utility, std_error, rng))
        if gap_lower_confidence_bound(g_hat, std_error, nc2, na2, delta) > 0.0:
            power += 1
    return {
        "std_error": std_error,
        "naive_fpr": naive_fp / trials,
        "calibrated_fpr": calib_fp / trials,
        "power": power / trials,
        "delta": delta,
    }


def falsify_inference(seed: int = 20260720, trials: int = 2500) -> dict[str, float | int | bool]:
    """Try to break the certificate: calibrated FPR must stay <= delta on random nulls,
    while the naive rule must visibly fail, and power must appear on alternatives.
    """
    rng = _Rng(seed)
    delta = 0.1
    worst_calib_fpr = 0.0
    max_naive_fpr = 0.0
    min_power = 1.0
    checked = 0
    for k in range(8):
        n_c = 3 + (k % 3)
        n_a = 3 + ((k // 3) % 3)
        # NULL: additive utility (no interaction) => G = 0 exactly
        alpha = [rng.gauss() for _ in range(n_c)]
        beta = [rng.gauss() for _ in range(n_a)]
        null_u = [[alpha[c] + beta[a] for a in range(n_a)] for c in range(n_c)]
        # ALT: strong interaction => G > 0
        alt_u = [[2.0 if a == (c % n_a) else 0.0 for a in range(n_a)] for c in range(n_c)]
        rep = calibration_experiment(null_u, alt_u, std_error=0.12, delta=delta, trials=trials, seed=seed + k)
        worst_calib_fpr = max(worst_calib_fpr, rep["calibrated_fpr"])
        max_naive_fpr = max(max_naive_fpr, rep["naive_fpr"])
        min_power = min(min_power, rep["power"])
        checked += 1
    return {
        "configs": checked,
        "worst_calibrated_fpr": worst_calib_fpr,
        "delta": delta,
        "calibration_valid": worst_calib_fpr <= delta,
        "max_naive_fpr": max_naive_fpr,
        "naive_rule_fails": max_naive_fpr > delta,   # debiasing is demonstrably necessary
        "min_power": min_power,
        "has_power": min_power > 0.9,
        "all_ok": worst_calib_fpr <= delta and max_naive_fpr > delta and min_power > 0.9,
    }


# --------------------------------------------------------------------------- #
# Adaptive (bootstrap) debiasing — recover power the worst-case bound discards  #
# --------------------------------------------------------------------------- #
def bootstrap_debias(
    utility_hat: Matrix, std_error: float, rng: _Rng, *, n_boot: int = 100
) -> tuple[float, float, float]:
    """Parametric-bootstrap estimate of the plug-in gap's bias, spread, and argmax
    stability.

    Treats ``utility_hat`` as truth, resamples ``U* = U-hat + noise(sd)``, and returns
    ``(bias, gap_std, min_argmax_stability)``:
      * ``bias`` = ``E[G-hat(U*)] - G-hat(U-hat)`` estimates ``E[G-hat] - G`` — the
        actual, separation-dependent upward bias (small when actions are separated);
      * ``gap_std`` = bootstrap standard deviation of ``G-hat``;
      * ``min_argmax_stability`` = the least, over contexts, bootstrap frequency that
        the per-context argmax matches the point estimate — a near-tie / irregularity
        detector (the max functional is non-smooth exactly at ties, where the
        bootstrap is known to fail, so this flags when to fall back).
    """
    n_c, n_a = _validate_matrix(utility_hat, name="utility_hat")
    if not math.isfinite(std_error) or std_error < 0:
        raise ValueError("std_error must be finite and non-negative")
    if n_boot < 2:
        raise ValueError("n_boot must be at least 2")
    point_argmax = [max(range(n_a), key=lambda a: utility_hat[c][a]) for c in range(n_c)]
    g0 = plugin_gap(utility_hat)
    vals: list[float] = []
    stable = [0] * n_c
    for _ in range(n_boot):
        star = [[utility_hat[c][a] + std_error * rng.gauss() for a in range(n_a)] for c in range(n_c)]
        vals.append(plugin_gap(star))
        for c in range(n_c):
            if max(range(n_a), key=lambda a: star[c][a]) == point_argmax[c]:
                stable[c] += 1
    mean = sum(vals) / n_boot
    variance = sum((v - mean) ** 2 for v in vals) / max(1, n_boot - 1)
    return mean - g0, math.sqrt(variance), min(s / n_boot for s in stable)


def adaptive_gap_lower_bound(
    utility_hat: Matrix, std_error: float, n_contexts: int, n_actions: int,
    delta: float, rng: _Rng, *, n_boot: int = 100,
) -> float:
    """Tie-safeguarded bootstrap lower bound: valid everywhere, more powerful when
    the benchmark is well-separated.

    Away from ties (stable argmax) it subtracts the *estimated* bias and spread,
    recovering the power the worst-case union bound discards. Near a tie (unstable
    argmax — where the bootstrap is unreliable) it falls back to the provably valid
    conservative bound. Under-separated benchmarks are correctly deferred, not
    green-lit (collect ``sample_complexity`` more samples first).
    """
    shape = _validate_matrix(utility_hat, name="utility_hat")
    if shape != (n_contexts, n_actions):
        raise ValueError("declared matrix dimensions do not match utility_hat")
    _validate_bound_inputs(0.0, std_error, n_contexts, n_actions, delta)
    g0 = plugin_gap(utility_hat)
    bias, gap_std, min_stability = bootstrap_debias(utility_hat, std_error, rng, n_boot=n_boot)
    if min_stability < 1.0 - delta:                       # near-tie / irregular
        return gap_lower_confidence_bound(g0, std_error, n_contexts, n_actions, delta)
    return g0 - bias - gap_std * math.sqrt(2.0 * math.log(1.0 / delta))


def power_comparison(
    null_utility: Matrix, alt_utility: Matrix, std_error: float, *, delta: float = 0.1,
    trials: int = 1000, n_boot: int = 80, seed: int = 20260720,
) -> dict[str, float]:
    """Compare conservative vs adaptive certificate: FPR on the null, power on the alt."""
    n_c, n_a = len(null_utility), len(null_utility[0])
    rng = _Rng(seed)
    cons_fp = adap_fp = 0
    for _ in range(trials):
        u_hat = _noisy(null_utility, std_error, rng)
        g_hat = plugin_gap(u_hat)
        if gap_lower_confidence_bound(g_hat, std_error, n_c, n_a, delta) > 0.0:
            cons_fp += 1
        if adaptive_gap_lower_bound(u_hat, std_error, n_c, n_a, delta, rng, n_boot=n_boot) > 0.0:
            adap_fp += 1
    na2, nc2 = len(alt_utility[0]), len(alt_utility)
    cons_pw = adap_pw = 0
    for _ in range(trials):
        u_hat = _noisy(alt_utility, std_error, rng)
        g_hat = plugin_gap(u_hat)
        if gap_lower_confidence_bound(g_hat, std_error, nc2, na2, delta) > 0.0:
            cons_pw += 1
        if adaptive_gap_lower_bound(u_hat, std_error, nc2, na2, delta, rng, n_boot=n_boot) > 0.0:
            adap_pw += 1
    return {
        "conservative_fpr": cons_fp / trials, "adaptive_fpr": adap_fp / trials,
        "conservative_power": cons_pw / trials, "adaptive_power": adap_pw / trials,
        "delta": delta,
    }


def falsify_adaptive(seed: int = 20260720, trials: int = 500, n_boot: int = 50) -> dict[str, float | int | bool]:
    """Adaptive certificate must stay valid on every null (incl. least-favorable ties)
    while beating the conservative bound's power at a non-saturated operating point.
    """
    delta = 0.1
    nulls: list[tuple[list[list[float]], int, int]] = [
        ([[a + b for b in (0.2, -0.1, 0.4)] for a in (0.5, -0.3, 1.1)], 3, 3),  # additive G=0
        ([[0.0] * 12 for _ in range(4)], 4, 12),                                 # tied, many actions
        ([[0.0] * 20 for _ in range(6)], 6, 20),                                 # least-favorable tie
    ]
    worst_fpr = 0.0
    rng = _Rng(seed)
    for u, n_c, n_a in nulls:
        fp = 0
        for _ in range(trials):
            u_hat = _noisy(u, 0.12, rng)
            if adaptive_gap_lower_bound(u_hat, 0.12, n_c, n_a, delta, rng, n_boot=n_boot) > 0.0:
                fp += 1
        worst_fpr = max(worst_fpr, fp / trials)
    # power at a non-saturated operating point where the conservative bound leaves room
    alt = [[0.6 if a == c else 0.0 for a in range(4)] for c in range(4)]
    cmp = power_comparison(nulls[0][0], alt, 0.12, delta=delta, trials=trials, n_boot=n_boot, seed=seed + 1)
    return {
        "worst_null_fpr": worst_fpr,
        "delta": delta,
        "valid": worst_fpr <= delta,
        "conservative_power": cmp["conservative_power"],
        "adaptive_power": cmp["adaptive_power"],
        "power_gain": cmp["adaptive_power"] - cmp["conservative_power"],
        "adaptive_dominates": cmp["adaptive_power"] >= cmp["conservative_power"] - 1e-9,
        "all_ok": worst_fpr <= delta and cmp["adaptive_power"] > cmp["conservative_power"],
    }


if __name__ == "__main__":  # pragma: no cover - CLI summary
    print("IDENTIFIABILITY INFERENCE — calibrated pilot certificate\n")
    alpha, beta = [0.5, -0.3, 1.1, -0.2], [0.2, -0.1, 0.4, 0.05]
    null_u = [[alpha[c] + beta[a] for a in range(4)] for c in range(4)]
    alt_u = [[1.0 if a == c else 0.0 for a in range(4)] for c in range(4)]
    for n in (50, 200, 1000):
        rep = calibration_experiment(null_u, alt_u, std_error=1.0 / math.sqrt(n))
        print(f"  n={n:5d}  NULL naive-FPR={rep['naive_fpr']:.3f}  calibrated-FPR={rep['calibrated_fpr']:.3f}"
              f"  (<= {rep['delta']})  |  ALT power={rep['power']:.3f}")
    print(f"\n  sample complexity for G=0.25, sigma=1, |C|=4,|A|=4, delta=0.05:"
          f" n* = {sample_complexity(0.25, 1.0, 4, 4, 0.05)} samples/cell")
    rep = falsify_inference()
    ok = "ALL OK" if rep["all_ok"] else "VIOLATION"
    print(f"  FALSIFICATION: {ok} | calib<=delta={rep['calibration_valid']}"
          f"  naive-fails={rep['naive_rule_fails']}  power={rep['has_power']}")

    print("\nADAPTIVE (bootstrap) debiasing — power recovered at fixed validity:")
    ad = falsify_adaptive()
    print(f"  worst-null FPR={ad['worst_null_fpr']:.3f} (<= {ad['delta']})  valid={ad['valid']}"
          f"  |  power conservative={ad['conservative_power']:.3f} -> adaptive={ad['adaptive_power']:.3f}"
          f"  (+{ad['power_gain']:.3f})")
