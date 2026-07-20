"""Falsification suite for the value-of-information rate function V*(R).

Verifies the proved envelope (V* <= min{G, Pinsker}), saturation at G, monotonicity,
and — the headline — the Pinsker phase transition: the ceiling is asymptotically
loose (ratio -> 0) at a regular problem and asymptotically tight (ratio -> 1) at a
critical/indifference problem. Constructed so a mutant that breaks the solver,
the bound, or the dichotomy is killed.
"""
import math

import pytest

from experiments.common.value_of_information_rate import (
    falsify_rate_function,
    is_critical,
    optimal_value_at_rate,
    optimal_value_at_rate_general,
    oracle_gap_value,
    pinsker_ceiling,
    pinsker_tightness,
    prior_optimal_actions,
    small_rate_exponent,
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
