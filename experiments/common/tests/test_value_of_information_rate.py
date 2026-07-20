"""Falsification suite for the value-of-information rate function V*(R).

Verifies the proved envelope (V* <= min{G, Pinsker}), saturation at G, monotonicity,
and — the headline — the Pinsker phase transition: the ceiling is asymptotically
loose (ratio -> 0) at a regular problem and asymptotically tight (ratio -> 1) at a
critical/indifference problem. Constructed so a mutant that breaks the solver,
the bound, or the dichotomy is killed.
"""
import math
from itertools import pairwise

import pytest

from experiments.common.value_of_information_rate import (
    critical_pinsker_tightness,
    falsify_rate_function,
    is_critical,
    marginal_value_of_information,
    optimal_value_at_rate,
    optimal_value_at_rate_general,
    optimal_value_at_rate_ri,
    oracle_gap_value,
    pinsker_ceiling,
    pinsker_tightness,
    prior_optimal_actions,
    small_rate_exponent,
    symmetric_critical_information,
    symmetric_critical_value,
    utility_per_joule_ceiling,
    value_and_information,
)

REGULAR = [[1.0, 0.0], [0.0, 0.5]]   # E[U.,0]=0.5 > E[U.,1]=0.25 : unique prior optimum
CRITICAL = [[1.0, 0.0], [0.0, 1.0]]  # E[U.,0]=E[U.,1]=0.5 : two actions tie


# ------------------------------ channel value ------------------------------ #
def test_perfect_channel_attains_oracle_gap():
    v, i = value_and_information(CRITICAL, [[1.0, 0.0], [0.0, 1.0]], (0.5, 0.5))
    assert v == pytest.approx(oracle_gap_value(CRITICAL, (0.5, 0.5)), abs=1e-12)
    assert i == pytest.approx(math.log(2), abs=1e-9)  # 1 bit = ln2 nats


def test_uninformative_channel_has_zero_value_and_information():
    v, i = value_and_information(REGULAR, [[0.5, 0.5], [0.5, 0.5]], (0.5, 0.5))
    assert v == pytest.approx(0.0, abs=1e-12)
    assert i == pytest.approx(0.0, abs=1e-12)


# ------------------------------ regime classifier -------------------------- #
def test_regime_classification():
    assert is_critical(CRITICAL, (0.5, 0.5)) is True
    assert is_critical(REGULAR, (0.5, 0.5)) is False
    assert len(prior_optimal_actions(CRITICAL, (0.5, 0.5))) == 2
    assert prior_optimal_actions(REGULAR, (0.5, 0.5)) == [0]


# ------------------------------ envelope + shape --------------------------- #
def test_rate_function_respects_the_master_envelope():
    for u in (REGULAR, CRITICAL):
        g = oracle_gap_value(u, (0.5, 0.5))
        for r in (0.001, 0.01, 0.1, 0.5, 1.0):
            v = optimal_value_at_rate(u, r, coarse=80, refine=20)
            assert v <= min(g, pinsker_ceiling(u, r)) + 1e-6


def test_rate_function_is_monotone_and_saturates_at_G():
    u = REGULAR
    g = oracle_gap_value(u, (0.5, 0.5))
    prev = -1.0
    for r in (0.01, 0.05, 0.2, 1.0, 5.0):
        v = optimal_value_at_rate(u, r, coarse=80, refine=20)
        assert v >= prev - 1e-6
        prev = v
    assert optimal_value_at_rate(u, 8.0, coarse=80, refine=20) == pytest.approx(g, abs=1e-3)


def test_zero_rate_buys_nothing():
    assert optimal_value_at_rate(REGULAR, 0.0) == 0.0


# ------------------------- THE PINSKER PHASE TRANSITION -------------------- #
def test_pinsker_is_asymptotically_loose_at_a_regular_problem():
    # ratio V*/Pinsker decreases toward 0 as R shrinks
    ratios = [float(pinsker_tightness(REGULAR, rate=r)["tightness_ratio"])
              for r in (0.02, 0.005, 0.00125)]
    assert ratios[0] > ratios[1] > ratios[2]        # strictly decreasing
    assert ratios[-1] < 0.1                           # heading to zero
    assert small_rate_exponent(REGULAR) > 0.8         # ~linear (regular)


def test_pinsker_is_asymptotically_tight_at_a_critical_problem():
    r = float(pinsker_tightness(CRITICAL, rate=0.002)["tightness_ratio"])
    assert r > 0.9                                    # ceiling nearly attained
    assert 0.45 < small_rate_exponent(CRITICAL) < 0.6  # ~sqrt (critical)


def test_the_two_regimes_are_qualitatively_separated():
    reg = pinsker_tightness(REGULAR, rate=0.002)
    crit = pinsker_tightness(CRITICAL, rate=0.002)
    # a regular problem leaves a large gap; a critical one nearly closes it
    assert float(reg["tightness_ratio"]) < 0.15
    assert float(crit["tightness_ratio"]) > 0.9
    assert crit["is_critical"] is True and reg["is_critical"] is False


# ---------- THE TRANSITION IS UNIVERSAL: general |C| > 2 confirmation ------- #
P3 = [1 / 3, 1 / 3, 1 / 3]
REG3 = [[1.0, 0.0, 0.2], [0.3, 0.9, 0.1], [0.2, 0.1, 0.8]]   # unique prior optimum
CRIT3 = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.5, 0.5, 0.0]]  # actions 0,1 tie at mean 0.5


def _exponent3(u, rates, grid=36):
    vs = [optimal_value_at_rate_general(u, r, P3, grid=grid) for r in rates]
    slopes = [
        (math.log(vs[k + 1]) - math.log(vs[k])) / (math.log(rates[k + 1]) - math.log(rates[k]))
        for k in range(len(vs) - 1) if vs[k] > 1e-9 and vs[k + 1] > 1e-9
    ]
    return vs, (sum(slopes) / len(slopes) if slopes else float("nan"))


def test_general_solver_respects_the_envelope():
    g = oracle_gap_value(CRIT3, P3)
    for r in (0.005, 0.05, 0.3):
        v = optimal_value_at_rate_general(CRIT3, r, P3, grid=28)
        assert v <= min(g, pinsker_ceiling(CRIT3, r)) + 1e-6


def test_phase_transition_holds_for_three_contexts():
    assert is_critical(REG3, P3) is False
    assert is_critical(CRIT3, P3) is True
    _vr, e_reg = _exponent3(REG3, (0.03, 0.008))
    _vc, e_crit = _exponent3(CRIT3, (0.02, 0.005, 0.00125))
    assert e_reg > 0.8                                   # regular: ~linear (Pinsker loose)
    assert 0.45 < e_crit < 0.65                          # critical: ~sqrt (Pinsker tight)
    # and the Pinsker tightness separates the two regimes at |C|=3, as in binary
    r_reg = optimal_value_at_rate_general(REG3, 0.008, P3, grid=44) / pinsker_ceiling(REG3, 0.008)
    r_crit = optimal_value_at_rate_general(CRIT3, 0.00125, P3, grid=44) / pinsker_ceiling(CRIT3, 0.00125)
    assert r_reg < 0.2 and r_crit > 0.5


def test_general_solver_guards_against_intractable_size():
    with pytest.raises(ValueError):
        optimal_value_at_rate_general([[0.0, 1.0]] * 6, 0.1, grid=60)  # grid**|C| too large


# ------- SHARP CRITICAL CONSTANT: Pinsker is ATTAINED (c = 1) -------------- #
def test_symmetric_channel_information_expansion():
    assert symmetric_critical_information(0.0) == 0.0
    for t in (0.05, 0.01, 0.002):
        # I(t) = 2 t^2 + O(t^4): leading coefficient is exactly 2
        assert symmetric_critical_information(t) / (2 * t * t) == pytest.approx(1.0, abs=1e-2)
    with pytest.raises(ValueError):
        symmetric_critical_information(0.5)


def test_pinsker_ceiling_is_asymptotically_attained_c_equals_one():
    # V*(R)/(Du sqrt(R/2)) -> 1 : the critical constant is exactly 1
    ratios = [critical_pinsker_tightness(r)["ratio"] for r in (1e-2, 1e-3, 1e-4, 1e-5)]
    assert all(a < b for a, b in pairwise(ratios))          # increasing toward 1
    assert ratios[-1] > 0.99999                              # essentially attained


def test_exact_first_order_correction_is_R_over_six():
    # V*/Pinsker = 1 - R/6 + O(R^2): the first correction coefficient is exactly 1/6
    for r in (1e-2, 1e-3, 1e-4):
        one_minus = critical_pinsker_tightness(r)["one_minus_ratio"]
        assert one_minus == pytest.approx(r / 6.0, rel=2e-2)


def test_exact_solver_dominates_and_matches_the_grid():
    # the closed-form symmetric optimum is exact; the grid is a (slightly looser) lower bound
    u = [[1.0, 0.0], [0.0, 1.0]]
    for r in (0.05, 0.02):
        exact = symmetric_critical_value(r, utility_range=1.0)
        grid = optimal_value_at_rate(u, r, coarse=200, refine=60)
        assert exact >= grid - 1e-9              # exact is optimal
        assert exact == pytest.approx(grid, abs=3e-3)  # and close


def test_symmetric_critical_value_is_monotone_and_fails_closed():
    prev = -1.0
    for r in (0.001, 0.01, 0.1, 0.4):
        v = symmetric_critical_value(r, 2.0)
        assert v >= prev
        prev = v
    with pytest.raises(ValueError):
        symmetric_critical_value(-0.1)


# -------- SHARP GENERAL SOLVER via rational inattention -------------------- #
def test_ri_reproduces_closed_form_critical_to_machine_precision():
    # the RI fixed point IS the optimum, so it must match the analytic ground truth
    for r in (0.01, 0.001, 0.0001):
        assert optimal_value_at_rate_ri([[1.0, 0.0], [0.0, 1.0]], r) == pytest.approx(
            symmetric_critical_value(r), abs=1e-7
        )


def test_ri_matches_the_exact_binary_grid_solver():
    u = [[1.0, 0.0], [0.0, 0.5]]
    for r in (0.05, 0.02, 0.005):
        assert optimal_value_at_rate_ri(u, r) == pytest.approx(
            optimal_value_at_rate(u, r, coarse=240, refine=60), abs=2e-3
        )


def test_ri_strictly_beats_the_binary_signal_lower_bound_when_actions_exceed_two():
    # |C|=3,|A|=3: the optimal channel needs 3 signals; RI finds it, the 2-signal grid can't
    u, p = CRIT3, P3
    for r in (0.02, 0.01):
        ri = optimal_value_at_rate_ri(u, r, p)
        grid2 = optimal_value_at_rate_general(u, r, p, grid=40)
        upper = min(oracle_gap_value(u, p), pinsker_ceiling(u, r))
        assert ri >= grid2 - 1e-9         # never worse than the lower bound
        assert ri > grid2 + 1e-3          # and strictly better (stochastic optimum)
        assert ri <= upper + 1e-9         # still under the envelope


def test_ri_is_monotone_saturates_and_respects_envelope():
    u, p = [[1.0, 0.0, 0.2], [0.3, 0.9, 0.1], [0.2, 0.1, 0.8]], P3
    g = oracle_gap_value(u, p)
    prev = -1.0
    for r in (0.01, 0.05, 0.2, 1.0):
        v = optimal_value_at_rate_ri(u, r, p)
        assert v >= prev - 1e-9
        assert v <= min(g, pinsker_ceiling(u, r)) + 1e-6
        prev = v
    assert optimal_value_at_rate_ri(u, 6.0, p) == pytest.approx(g, abs=1e-3)  # saturation
    assert optimal_value_at_rate_ri(u, 0.0, p) == 0.0


def test_phase_transition_via_accurate_ri_solver():
    def expo(u, rates):
        vs = [optimal_value_at_rate_ri(u, r, P3) for r in rates]
        return sum(
            (math.log(vs[k + 1]) - math.log(vs[k])) / (math.log(rates[k + 1]) - math.log(rates[k]))
            for k in range(len(vs) - 1)
        ) / (len(vs) - 1)
    assert expo(REG3, (0.02, 0.005, 0.00125)) > 0.85     # regular ~ linear
    assert 0.45 < expo(CRIT3, (0.02, 0.005, 0.00125)) < 0.56  # critical ~ sqrt


# ---- MARGINAL VALUE beta = dV*/dR : concavity + physical exchange rate ----- #
def test_marginal_value_equals_the_derivative_of_the_rate_function():
    u = [[1.0, 0.0], [0.0, 0.5]]
    for r in (0.01, 0.05, 0.2):
        beta = marginal_value_of_information(u, r)
        num = (optimal_value_at_rate_ri(u, r * 1.01) - optimal_value_at_rate_ri(u, r * 0.99)) / (0.02 * r)
        assert beta == pytest.approx(num, rel=3e-2)     # beta is exactly dV*/dR


def test_rate_function_is_concave_marginal_value_decreases():
    u = [[1.0, 0.0], [0.0, 0.5]]
    betas = [marginal_value_of_information(u, r) for r in (0.001, 0.01, 0.05, 0.2)]
    assert all(a > b for a, b in pairwise(betas))       # decreasing -> V* concave


def test_marginal_value_dichotomy_finite_regular_divergent_critical():
    reg = [marginal_value_of_information([[1.0, 0.0], [0.0, 0.5]], r) for r in (0.05, 0.005, 0.0005)]
    crit = [marginal_value_of_information([[1.0, 0.0], [0.0, 1.0]], r) for r in (0.05, 0.005, 0.0005)]
    assert reg[-1] < 2.0                                 # regular: bounded (finite sigma)
    assert crit[-1] > 3.0 * crit[0]                      # critical: diverges as R->0


def test_utility_per_joule_ceiling_couples_to_landauer():
    # a router paying beta utility/nat cannot beat beta/(kT) utility per joule
    kT = 1.380649e-23 * 310.15
    assert utility_per_joule_ceiling(1.0) == pytest.approx(1.0 / kT, rel=1e-9)
    assert utility_per_joule_ceiling(2.0) == pytest.approx(2.0 * utility_per_joule_ceiling(1.0), rel=1e-12)
    with pytest.raises(ValueError):
        utility_per_joule_ceiling(-1.0)


# ------------------------------ bundled harness ---------------------------- #
def test_falsification_harness_holds():
    rep = falsify_rate_function(seed=20260720, trials=30)
    assert rep["all_ok"] is True
    assert rep["bound_violations"] == 0
    assert rep["monotone_violations"] == 0
    assert rep["saturation_violations"] == 0
    assert rep["dichotomy_holds"] is True


# ------------------------------ fail-closed -------------------------------- #
def test_fail_closed():
    with pytest.raises(ValueError):
        optimal_value_at_rate([[1.0, 0.0], [0.0, 1.0], [0.0, 0.0]], 0.1)  # non-binary context
    with pytest.raises(ValueError):
        optimal_value_at_rate(REGULAR, -0.1)                              # negative rate
    with pytest.raises(ValueError):
        pinsker_ceiling(REGULAR, -1.0)
    with pytest.raises(ValueError):
        value_and_information(REGULAR, [[0.4, 0.4], [0.5, 0.5]], (0.5, 0.5))  # row not a distribution
