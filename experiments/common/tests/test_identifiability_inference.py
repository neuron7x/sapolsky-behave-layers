"""Falsification suite for the calibrated identifiability inference certificate.

The headline is a calibration guarantee: on a truly non-identifiable (G=0) pilot the
debiased certificate's false-positive rate stays <= delta, while the naive
"estimate-and-spend" rule blows past it. Also checks power on separated alternatives,
the exact correction-term formulas (anti-mutation), monotone sample complexity, and
fail-closed validation.
"""
import math

import pytest

from experiments.common.identifiability_inference import (
    _Rng,
    adaptive_gap_lower_bound,
    bootstrap_debias,
    calibration_experiment,
    certifies_positive_value,
    certify_identifiable,
    deviation_bound,
    falsify_adaptive,
    falsify_inference,
    gap_lower_confidence_bound,
    oracle_bias_bound,
    plugin_gap,
    power_comparison,
    sample_complexity,
)

# additive utility => G = 0 exactly (null); interaction => G > 0 (alt)
NULL = [[a + b for b in (0.2, -0.1, 0.4)] for a in (0.5, -0.3, 1.1)]
ALT = [[1.0 if a == c else 0.0 for a in range(3)] for c in range(3)]


# ------------------------------ point estimate ----------------------------- #
def test_plugin_gap_matches_definition():
    assert plugin_gap(ALT) == pytest.approx(2.0 / 3.0, abs=1e-12)  # E max = 1, V_fixed = 1/3
    assert plugin_gap(NULL) == pytest.approx(0.0, abs=1e-12)       # additive => G = 0


# --------------------- correction terms (anti-mutation) -------------------- #
def test_correction_terms_are_exact():
    assert oracle_bias_bound(0.1, 4) == pytest.approx(0.1 * math.sqrt(2 * math.log(4)), rel=1e-12)
    assert deviation_bound(0.1, 4, 0.1) == pytest.approx(0.1 / 2 * math.sqrt(2 * math.log(20)), rel=1e-12)
    glo = gap_lower_confidence_bound(1.0, 0.1, 4, 4, 0.1)
    assert glo == pytest.approx(1.0 - oracle_bias_bound(0.1, 4) - deviation_bound(0.1, 4, 0.1), rel=1e-12)


def test_lower_bound_is_below_the_point_estimate():
    for sd in (0.05, 0.2, 0.5):
        assert gap_lower_confidence_bound(0.5, sd, 4, 4, 0.05) < 0.5


# ----------------------- THE CALIBRATION GUARANTEE ------------------------- #
def test_naive_rule_is_miscalibrated_but_debiased_is_valid():
    # small pilot: naive fires on the null far above delta; calibrated stays <= delta
    rep = calibration_experiment(NULL, ALT, std_error=0.14, delta=0.1, trials=4000)
    assert rep["naive_fpr"] > 0.3            # naive false-positive catastrophe
    assert rep["calibrated_fpr"] <= 0.1      # valid: FPR <= delta
    assert rep["power"] > 0.9                # still powerful on the alternative


def test_calibration_holds_across_pilot_sizes():
    for sd in (0.3, 0.1, 0.03):
        rep = calibration_experiment(NULL, ALT, std_error=sd, delta=0.1, trials=3000)
        assert rep["calibrated_fpr"] <= 0.1


def test_max_bias_term_is_load_bearing_with_many_actions():
    # least-favorable null: all actions tied (G=0) with many actions, so the max
    # operator's upward bias dominates. The FULL certificate (module function) must
    # stay <= delta; dropping ONLY the max-bias term must break calibration. This
    # kills any mutation that weakens gap_lower_confidence_bound's bias correction.
    from experiments.common.identifiability_inference import _Rng
    n_c, n_a, sd, delta = 6, 30, 0.12, 0.1
    rng = _Rng(3)
    full_fp = nobias_fp = 0
    trials = 3000
    for _ in range(trials):
        u_hat = [[sd * rng.gauss() for _ in range(n_a)] for _ in range(n_c)]
        g_hat = plugin_gap(u_hat)
        if gap_lower_confidence_bound(g_hat, sd, n_c, n_a, delta) > 0.0:   # module (full)
            full_fp += 1
        if g_hat - deviation_bound(sd, n_c, delta) > 0.0:                  # bias term removed
            nobias_fp += 1
    assert full_fp / trials <= delta            # valid with the max-bias correction
    assert nobias_fp / trials > 0.3             # invalid without it -> term is necessary


def test_falsification_harness_holds():
    rep = falsify_inference(trials=2000)
    assert rep["all_ok"] is True
    assert rep["calibration_valid"] is True   # calibrated FPR <= delta on every random null
    assert rep["naive_rule_fails"] is True    # naive rule provably necessary to fix
    assert rep["has_power"] is True


# ------------------- ADAPTIVE (bootstrap) debiasing ------------------------ #
def test_bootstrap_bias_grows_and_stability_falls_toward_a_tie():
    # separated (stable argmax, small bias) vs least-favorable tie (unstable, large bias)
    sep = [[1.0, 0.0], [0.2, 0.9]]        # per-context AND fixed-term argmax well separated
    tied = [[0.0] * 8 for _ in range(4)]  # all actions tied in every context
    bias_sep, _s1, stab_sep = bootstrap_debias(sep, 0.08, _Rng(1), n_boot=200)
    bias_tied, _s2, stab_tied = bootstrap_debias(tied, 0.08, _Rng(1), n_boot=200)
    assert stab_sep > 0.9                       # separated: bootstrap trustworthy
    assert stab_tied < 0.5                       # tied: argmax unstable (irregular point)
    assert stab_sep > stab_tied                  # stability falls toward the tie
    assert bias_tied > abs(bias_sep)             # upward bias grows toward the tie
    assert bias_tied > 0.05                       # the tie's bias is the term worth correcting


def test_adaptive_certificate_is_valid_on_all_nulls_and_more_powerful():
    rep = falsify_adaptive(trials=500, n_boot=50)
    assert rep["valid"] is True                          # FPR <= delta on every null
    assert float(rep["worst_null_fpr"]) <= 0.1           # incl. the least-favorable tie
    assert rep["adaptive_power"] > rep["conservative_power"]  # strict power gain
    assert float(rep["power_gain"]) > 0.05


def test_adaptive_falls_back_to_conservative_near_a_tie():
    # on an all-tied null the safeguard must trigger, giving the conservative bound
    tied = [[0.0] * 12 for _ in range(4)]
    rng = _Rng(2)
    u_hat = [[tied[c][a] + 0.12 * rng.gauss() for a in range(12)] for c in range(4)]
    g_hat = plugin_gap(u_hat)
    adaptive = adaptive_gap_lower_bound(u_hat, 0.12, 4, 12, 0.1, rng, n_boot=100)
    conservative = gap_lower_confidence_bound(g_hat, 0.12, 4, 12, 0.1)
    assert adaptive == pytest.approx(conservative, abs=1e-12)  # safeguard used the valid bound


def test_power_comparison_never_lets_adaptive_break_validity_on_null():
    null = [[a + b for b in (0.2, -0.1, 0.4)] for a in (0.5, -0.3, 1.1)]
    alt = [[0.6 if a == c else 0.0 for a in range(3)] for c in range(3)]
    cmp = power_comparison(null, alt, 0.12, delta=0.1, trials=600, n_boot=50)
    assert cmp["adaptive_fpr"] <= 0.1
    assert cmp["adaptive_power"] >= cmp["conservative_power"] - 1e-9


# --------------------------- sample complexity ----------------------------- #
def test_sample_complexity_decreases_with_gap_and_grows_with_noise():
    fine = sample_complexity(0.5, 1.0, 4, 4, 0.05)
    coarse = sample_complexity(0.1, 1.0, 4, 4, 0.05)   # smaller gap -> more samples
    assert coarse > fine
    noisier = sample_complexity(0.5, 2.0, 4, 4, 0.05)  # 2x noise -> 4x samples
    assert noisier == pytest.approx(4 * fine, rel=0.05)


def test_sample_complexity_actually_confers_power():
    # at n* samples, the certificate should recover power on that gap
    g, sigma = 0.5, 1.0
    n = sample_complexity(g, sigma, 3, 3, 0.1)
    rep = calibration_experiment(NULL, ALT, std_error=sigma / math.sqrt(n), delta=0.1, trials=3000)
    assert rep["power"] > 0.8


# ----------------------------- decision helpers ---------------------------- #
def test_positive_value_certificate_accounts_for_route_cost():
    # a gap that clears zero but not the route cost must not certify positive value
    assert certify_identifiable(0.4, 0.02, 4, 4, delta=0.05)["identifiable"] is True
    assert certifies_positive_value(0.4, 0.02, 4, 4, route_cost=0.05, delta=0.05) is True
    assert certifies_positive_value(0.4, 0.02, 4, 4, route_cost=0.5, delta=0.05) is False


# ----------------------------- fail-closed --------------------------------- #
def test_fail_closed():
    with pytest.raises(ValueError):
        deviation_bound(0.1, 4, 1.5)                 # delta out of (0,1)
    with pytest.raises(ValueError):
        oracle_bias_bound(-0.1, 4)                   # negative std error
    with pytest.raises(ValueError):
        sample_complexity(0.0, 1.0, 4, 4, 0.05)      # non-positive gap not certifiable
    with pytest.raises(ValueError):
        certifies_positive_value(0.4, 0.02, 4, 4, route_cost=-0.1)
