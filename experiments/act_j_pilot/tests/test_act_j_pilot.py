"""Fast falsification test: a trained controller must reach V*(R) and show the
phase transition. Small training budget so it runs on CPU in a few seconds; the full
sweep lives in the runner + evidence bundle.
"""
import random

import pytest

from experiments.act_j_pilot.src.act_j_pilot import (
    symmetric_confusion_channel,
    train_controller,
    train_sensory_controller,
)
from experiments.act_j_pilot.src.compute_matched import compute_matched_gap
from experiments.common.value_of_information_rate import optimal_value_at_rate_ri

REGULAR = [[1.0, 0.0], [0.0, 0.5]]
CRITICAL = [[1.0, 0.0], [0.0, 1.0]]
PRIOR = [0.5, 0.5]


def test_trained_controller_reaches_the_analytic_ceiling():
    # at a moderate information price the trained (I, V) must land on V*(I)
    for u in (REGULAR, CRITICAL):
        res = train_controller(u, PRIOR, beta=0.5, steps=2500, seed=0)
        v_star = optimal_value_at_rate_ri(u, res.information_nats, PRIOR)
        assert res.value <= v_star + 1e-3                 # never beats the theory ceiling
        assert res.value >= v_star - 2e-2                 # and essentially attains it


def test_phase_transition_in_the_trained_controller():
    # at a HIGH information price: critical routes (value>0), regular does not
    reg = train_controller(REGULAR, PRIOR, beta=3.0, steps=2500, seed=0)
    crit = train_controller(CRITICAL, PRIOR, beta=3.0, steps=2500, seed=0)
    assert reg.value < 1e-2                                # regular: routing does not pay
    assert crit.value > 5.0 * reg.value + 1e-2            # critical: it does (sqrt onset)
    assert crit.information_nats > reg.information_nats    # critical buys info, regular abstains


def test_the_ceiling_is_realised_at_larger_scale():
    # a random |C|=4,|A|=3 problem: the trained controller still lands on V*(I)
    rng = random.Random(11)
    k, a = 4, 3
    u = [[rng.uniform(-1.0, 1.0) for _ in range(a)] for _ in range(k)]
    p = [1.0 / k] * k
    res = train_controller(u, p, beta=0.4, steps=3000, seed=0)
    v_star = optimal_value_at_rate_ri(u, res.information_nats, p)
    assert res.value == pytest.approx(v_star, abs=2e-2)


def test_sensory_controller_hits_channel_value_and_respects_the_ceiling():
    # a controller seeing only a noisy observation learns V(O) and stays <= V*(I(C;O))
    for u in (REGULAR, CRITICAL):
        r = train_sensory_controller(u, PRIOR, symmetric_confusion_channel(2, 0.3), steps=2500, seed=0)
        assert r.trained_value == pytest.approx(r.channel_value, abs=1e-2)     # reaches Bayes value
        assert r.trained_value <= r.v_star_at_channel_rate + 1e-2              # under the rate ceiling


def test_symmetric_sensor_is_rate_optimal_only_for_a_symmetric_problem():
    # critical (symmetric) -> no inefficiency; regular -> inefficiency that grows with noise
    crit = train_sensory_controller(CRITICAL, PRIOR, symmetric_confusion_channel(2, 0.4), steps=2500, seed=0)
    assert abs(crit.inefficiency) < 5e-3                                       # symmetric sensor optimal
    low = train_sensory_controller(REGULAR, PRIOR, symmetric_confusion_channel(2, 0.1), steps=2500, seed=0)
    high = train_sensory_controller(REGULAR, PRIOR, symmetric_confusion_channel(2, 0.6), steps=2500, seed=0)
    assert high.inefficiency > low.inefficiency > 1e-3                         # waste grows with noise


def test_compute_matched_adaptive_dominates_under_a_binding_budget():
    # easy solved by both, hard only by the expensive mechanism; cheap=1, expensive=4
    u, cost, p = [[1.0, 1.0], [0.0, 1.0]], [1.0, 4.0], [0.5, 0.5]
    rows = compute_matched_gap(u, cost, p, [2.0, 0.25], steps=3500, seed=0)
    for r in rows:
        assert r["adaptive_value"] >= r["static_value"] - 1e-3      # adaptive never worse
    # at the binding budget (compute ~2.5) adaptive strictly dominates by the constrained gap
    binding = [r for r in rows if r["compute"] > 1.5]
    assert binding and max(r["compute_matched_gap"] for r in binding) > 0.2


def test_compute_matched_ties_when_a_mechanism_dominates():
    # cheap mechanism solves everything -> routing buys no compute advantage
    u, cost, p = [[1.0, 1.0], [1.0, 1.0]], [1.0, 4.0], [0.5, 0.5]
    for r in compute_matched_gap(u, cost, p, [0.3], steps=2500, seed=0):
        assert abs(r["compute_matched_gap"]) < 1e-2


def test_more_information_never_decreases_realised_value():
    # lowering the price (more info) is monotone in value, and value stays <= G
    g = 0.25  # oracle gap of REGULAR
    vals = [train_controller(REGULAR, PRIOR, beta=b, steps=2000, seed=0).value for b in (2.0, 0.5, 0.15)]
    assert vals[0] <= vals[1] + 1e-2 <= vals[2] + 2e-2
    assert all(v <= g + 1e-3 for v in vals)
