"""Falsification suite for the unified adaptive-computation value theory.

Each test targets one theorem in ``docs/ADAPTIVE_COMPUTATION_VALUE_THEORY.md`` and
is constructed so it *can* fail: exhaustive/adversarial random problems verify the
inequalities, hand-built witnesses pin the tightness cases, and malformed inputs
must raise. A mutant that weakens any bound, drops the ``max``/``min``, or breaks
the ANOVA identity is killed by at least one assertion here.
"""
import math
import random

import pytest

from experiments.common.adaptive_value_theory import (
    budgeted_gap,
    falsify_theory,
    identifiable_window,
    oracle_gap,
    saturation_lambda,
    signal_value,
    total_variation,
)


# --------------------------- Theorem 1: decomposition ---------------------- #
def test_decomposition_identity_and_nonnegativity_random():
    rng = random.Random(1)
    for _ in range(3000):
        n_c, n_a = rng.randint(2, 5), rng.randint(2, 5)
        u = [[rng.uniform(-9, 9) for _ in range(n_a)] for _ in range(n_c)]
        r = oracle_gap(u)
        assert r["gap_matches_decomposition"] is True
        assert float(r["gap"]) >= -1e-12
        assert float(r["gap"]) == pytest.approx(float(r["gap_via_anova"]), abs=1e-9)


def test_zero_interaction_forces_zero_gap():
    # U[c,a] = alpha_c + beta_a (no interaction) => G = 0 exactly.
    alpha, beta = [0.3, -1.1, 2.0], [1.0, -0.5, 0.25, 4.0]
    u = [[a + b for b in beta] for a in alpha]
    assert float(oracle_gap(u)["gap"]) == pytest.approx(0.0, abs=1e-12)


# --------------------------- Theorem 2: dominance iff ---------------------- #
def test_weak_dominance_iff_zero_gap_random():
    rng = random.Random(2)
    for _ in range(5000):
        n_c, n_a = rng.randint(2, 4), rng.randint(2, 4)
        # small integer utilities create frequent exact ties -> exercises both branches
        u = [[float(rng.randint(0, 3)) for _ in range(n_a)] for _ in range(n_c)]
        r = oracle_gap(u)
        assert bool(r["weakly_dominant"]) == bool(r["gap_is_zero"])


def test_dominant_action_gives_zero_gap_but_large_interaction():
    # action 1 weakly dominates everywhere, yet interaction is non-trivial -> G=0.
    u = [[0.0, 5.0], [3.0, 5.0]]
    r = oracle_gap(u)
    assert r["weakly_dominant"] is True
    assert float(r["gap"]) == pytest.approx(0.0, abs=1e-12)


# ------------------ Theorem 3: data-processing ceiling V(Z) <= G ----------- #
def test_signal_value_between_zero_and_oracle_gap_random():
    rng = random.Random(3)
    for _ in range(4000):
        n_c, n_a, n_z = rng.randint(2, 4), rng.randint(2, 4), rng.randint(1, 4)
        u = [[rng.uniform(-4, 6) for _ in range(n_a)] for _ in range(n_c)]
        raw = [[rng.random() for _ in range(n_z)] for _ in range(n_c)]
        tot = sum(map(sum, raw))
        joint = [[raw[c][z] / tot for z in range(n_z)] for c in range(n_c)]
        r = signal_value(joint, u)
        assert float(r["signal_gap"]) >= -1e-12
        assert r["data_processing_holds"] is True


def test_perfect_signal_attains_oracle_gap():
    # Z = C (diagonal joint) => V(Z) == G.
    u = [[1.0, 0.0], [0.0, 1.0]]
    r = signal_value([[0.5, 0.0], [0.0, 0.5]], u)
    assert float(r["signal_gap"]) == pytest.approx(float(r["oracle_gap"]), abs=1e-12)
    assert float(r["signal_gap"]) == pytest.approx(0.5, abs=1e-12)


# ------------------ Theorem 4: information ceiling + tightness -------------- #
def test_information_bound_holds_random():
    rng = random.Random(4)
    for _ in range(4000):
        n_c, n_a, n_z = rng.randint(2, 4), rng.randint(2, 4), rng.randint(1, 4)
        u = [[rng.uniform(-4, 6) for _ in range(n_a)] for _ in range(n_c)]
        raw = [[rng.random() for _ in range(n_z)] for _ in range(n_c)]
        tot = sum(map(sum, raw))
        joint = [[raw[c][z] / tot for z in range(n_z)] for c in range(n_c)]
        r = signal_value(joint, u)
        assert r["information_bound_holds"] is True
        # exactness: the reported bound must equal Delta_u * sqrt(I/2) recomputed
        # independently here (kills any loosening/tightening mutation of the formula).
        expected = float(r["utility_range"]) * math.sqrt(max(0.0, float(r["mutual_information_nats"])) / 2.0)
        assert float(r["information_bound"]) == pytest.approx(expected, abs=1e-12)


def test_tv_bound_is_tight_for_indicator_utility():
    # Prop 4.1: with a {0,1} indicator utility, V(Z) == Delta_u * E_z TV(P(C|z), P(C)).
    joint = [[0.4, 0.1], [0.1, 0.4]]
    u = [[1.0, 0.0], [0.0, 1.0]]
    r = signal_value(joint, u)
    p_c = [sum(joint[c]) for c in range(2)]
    p_z = [joint[0][z] + joint[1][z] for z in range(2)]
    e_tv = 0.0
    for z in range(2):
        if p_z[z]:
            post = [joint[c][z] / p_z[z] for c in range(2)]
            e_tv += p_z[z] * total_variation(post, p_c)
    assert float(r["signal_gap"]) == pytest.approx(float(r["utility_range"]) * e_tv, abs=1e-12)


def test_pinsker_constant_is_rate_optimal_in_the_small_signal_limit():
    # Prop 4.2: for a near-symmetric binary channel, TV / sqrt(I/2) -> 1 as eps -> 0,
    # so the sqrt-rate and the 1/2 constant cannot be improved in general.
    ratios = []
    for eps in (1e-1, 1e-2, 1e-3):
        # C ~ Bernoulli(1/2); Z flips C with prob (1/2 - eps).
        a = 0.5 * (0.5 + eps)
        b = 0.5 * (0.5 - eps)
        joint = [[a, b], [b, a]]
        p_c = [0.5, 0.5]
        p_z = [0.5, 0.5]
        mi = 0.0
        for c in range(2):
            for z in range(2):
                p = joint[c][z]
                mi += p * math.log(p / (p_c[c] * p_z[z]))
        post0 = [joint[c][0] / p_z[0] for c in range(2)]
        tv = total_variation(post0, p_c)
        ratios.append(tv / math.sqrt(mi / 2.0))
    # monotonically approaching 1 from below and bounded by 1 (Pinsker).
    assert ratios[-1] > ratios[0]
    assert ratios[-1] > 0.99
    assert all(r <= 1.0 + 1e-9 for r in ratios)


# ------------------ Theorem 5: budgeted identifiability window -------------- #
def test_cost_saturation_kills_the_gap_above_lambda_star_random():
    rng = random.Random(5)
    checked = 0
    for _ in range(4000):
        n_c, n_a = rng.randint(2, 4), rng.randint(2, 4)
        u = [[rng.uniform(-4, 6) for _ in range(n_a)] for _ in range(n_c)]
        cost = [rng.uniform(0, 3) for _ in range(n_a)]
        sat = saturation_lambda(u, cost)
        if sat["unique_cheapest"]:
            checked += 1
            assert sat["gap_above_star_is_zero"] is True
            # one explicit probe strictly above lambda_star
            probe = float(sat["lambda_star"]) * 2.0 + 1.0
            assert float(budgeted_gap(u, cost, probe)["gap"]) == pytest.approx(0.0, abs=1e-9)
    assert checked > 100  # the branch is actually exercised


def test_budgeted_objectives_are_convex_and_nonincreasing():
    # V_oracle(lam) and V_fixed(lam) are convex, PL, non-increasing in lam.
    rng = random.Random(6)
    for _ in range(500):
        n_c, n_a = rng.randint(2, 4), rng.randint(2, 4)
        u = [[rng.uniform(-4, 6) for _ in range(n_a)] for _ in range(n_c)]
        cost = [rng.uniform(0, 3) for _ in range(n_a)]
        lam1, lam2 = sorted((rng.uniform(0, 3), rng.uniform(0, 3)))
        mid = 0.5 * (lam1 + lam2)
        for key in ("v_oracle", "v_fixed"):
            f1 = float(budgeted_gap(u, cost, lam1)[key])
            f2 = float(budgeted_gap(u, cost, lam2)[key])
            fm = float(budgeted_gap(u, cost, mid)[key])
            assert fm <= 0.5 * (f1 + f2) + 1e-9  # convexity (Jensen midpoint)
            assert f2 <= f1 + 1e-9                # non-increasing


def test_binding_budget_creates_identifiability_positive_control():
    # routing-v2 shape: semantic path (col 1) dominates on quality; a cost budget
    # on the expensive path opens a strictly positive window.
    u = [[1.00, 1.00], [0.004, 1.00]]  # EASY: [direct, semantic]; HARD: [direct, semantic]
    cost = [0.0, 1.0]
    assert float(oracle_gap(u)["gap"]) == pytest.approx(0.0, abs=1e-3)  # unbudgeted: dominated
    win = identifiable_window(u, cost)
    assert win["identifiable_somewhere"] is True
    assert float(win["max_gap"]) > 0.1


# ------------------ Theorem 6: master inequality --------------------------- #
def test_master_inequality_holds_random():
    rng = random.Random(7)
    for _ in range(4000):
        n_c, n_a, n_z = rng.randint(2, 4), rng.randint(2, 4), rng.randint(1, 4)
        u = [[rng.uniform(-4, 6) for _ in range(n_a)] for _ in range(n_c)]
        raw = [[rng.random() for _ in range(n_z)] for _ in range(n_c)]
        tot = sum(map(sum, raw))
        joint = [[raw[c][z] / tot for z in range(n_z)] for c in range(n_c)]
        rc = rng.uniform(0, 2)
        r = signal_value(joint, u, route_cost=rc)
        assert float(r["net_value"]) <= float(r["master_bound"]) + 1e-9
        # exactness: master_bound must be the MIN of the two ceilings minus cost
        # (kills a min->max mutation that would silently loosen the certificate).
        expected = min(float(r["oracle_gap"]), float(r["information_bound"])) - rc
        assert float(r["master_bound"]) == pytest.approx(expected, abs=1e-12)
        assert float(r["net_value"]) == pytest.approx(float(r["signal_gap"]) - rc, abs=1e-12)


# ------------------ Bundled adversarial harness ---------------------------- #
def test_falsification_harness_finds_no_counterexample():
    report = falsify_theory(seed=20260720, trials=6000)
    assert report["all_theorems_hold"] is True
    assert float(report["decomposition_max_violation"]) < 1e-9
    assert int(report["dominance_iff_failures"]) == 0
    assert float(report["data_processing_max_violation"]) < 1e-9
    assert float(report["information_bound_max_violation"]) < 1e-9
    assert float(report["master_inequality_max_violation"]) < 1e-9
    assert int(report["saturation_failures"]) == 0


# ------------------ fail-closed validation --------------------------------- #
@pytest.mark.parametrize(
    "fn,args",
    [
        (oracle_gap, ([],)),
        (oracle_gap, ([[1.0, 2.0], [3.0]],)),                 # ragged
        (oracle_gap, ([[1.0, float("nan")]],)),               # non-finite
        (signal_value, ([[0.6, 0.6]], [[1.0]])),              # joint not summing to 1
        (signal_value, ([[0.5, 0.5]], [[1.0], [2.0]])),       # context count mismatch
    ],
)
def test_malformed_inputs_fail_closed(fn, args):
    with pytest.raises(ValueError):
        fn(*args)


def test_negative_route_cost_rejected():
    with pytest.raises(ValueError):
        signal_value([[0.5, 0.0], [0.0, 0.5]], [[1.0, 0.0], [0.0, 1.0]], route_cost=-0.1)


def test_prior_must_be_a_distribution():
    with pytest.raises(ValueError):
        oracle_gap([[1.0, 0.0], [0.0, 1.0]], prior=[0.7, 0.7])
