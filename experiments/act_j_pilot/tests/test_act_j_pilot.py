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


def test_symmetric_sensor_is_rate_optimal_iff_context_exchangeable():
    # EXCHANGEABLE problems (full permutation symmetry) -> no inefficiency, at any |C|
    exch2 = train_sensory_controller(CRITICAL, PRIOR, symmetric_confusion_channel(2, 0.4), steps=2500, seed=0)
    assert abs(exch2.inefficiency) < 5e-3
    ident3 = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]               # exchangeable |C|=3
    exch3 = train_sensory_controller(ident3, [1 / 3] * 3, symmetric_confusion_channel(3, 0.4), steps=2500, seed=0)
    assert abs(exch3.inefficiency) < 5e-3                                       # exchangeability, not just 2x2
    # CRITICAL but NON-exchangeable -> the symmetric sensor is NOT rate-optimal
    crit_asym = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.5, 0.5, 0.0]]            # two actions tie, contexts differ
    ca = train_sensory_controller(crit_asym, [1 / 3] * 3, symmetric_confusion_channel(3, 0.45), steps=2500, seed=0)
    assert ca.inefficiency > 0.02                                              # criticality is NOT sufficient
    # a regular problem: inefficiency grows with noise
    low = train_sensory_controller(REGULAR, PRIOR, symmetric_confusion_channel(2, 0.1), steps=2500, seed=0)
    high = train_sensory_controller(REGULAR, PRIOR, symmetric_confusion_channel(2, 0.6), steps=2500, seed=0)
    assert high.inefficiency > low.inefficiency > 1e-3


def test_compute_matched_adaptive_dominates_under_a_binding_budget():
    # easy solved by both, hard only by the expensive mechanism; cheap=1, expensive=4
    u, cost, p = [[1.0, 1.0], [0.0, 1.0]], [1.0, 4.0], [0.5, 0.5]
    rows = compute_matched_gap(u, cost, p, [2.0, 0.25], steps=3500, seed=0)
    for r in rows:
        assert r["adaptive_value"] >= r["static_value"] - 1e-3      # adaptive never worse
    # at the binding budget (compute ~2.5) adaptive strictly dominates by the constrained gap
    binding = [r for r in rows if r["compute"] > 1.5]
    assert binding and max(r["compute_matched_gap"] for r in binding) > 0.2


def test_static_baseline_is_the_true_lp_optimum():
    # DESTRUCTION STAGE: static_value_at_compute must equal the brute-force best
    # context-blind policy (LP optimum mixes <=2 mechanisms), not an under-estimate
    from experiments.act_j_pilot.src.compute_matched import static_value_at_compute

    def brute(u, cost, p, b, n=120):
        k, a = len(u), len(u[0])
        mean = [sum(p[c] * u[c][x] for c in range(k)) for x in range(a)]
        best = -1e18

        def rec(rem, left, cur):
            nonlocal best
            if left == 1:
                q = [*cur, rem / n]
                if sum(q[x] * cost[x] for x in range(a)) <= b + 1e-9:
                    best = max(best, sum(q[x] * mean[x] for x in range(a)))
                return
            for kk in range(rem + 1):
                rec(rem - kk, left - 1, [*cur, kk / n])
        rec(n, a, [])
        return best

    rng = random.Random(3)
    worst = 0.0
    for _ in range(40):
        a, k = rng.randint(2, 3), rng.randint(2, 3)
        u = [[rng.uniform(0.0, 1.0) for _ in range(a)] for _ in range(k)]
        cost = [rng.uniform(1.0, 5.0) for _ in range(a)]
        p = [1.0 / k] * k
        b = rng.uniform(min(cost), max(cost))
        worst = max(worst, abs(static_value_at_compute(u, cost, p, b) - brute(u, cost, p, b)))
    assert worst < 1e-2       # matches the LP optimum to grid resolution


def test_compute_matched_dominance_is_robust_across_seeds():
    # the +0.25 compute-matched advantage is not a single-seed fluke
    u, cost, p = [[1.0, 1.0], [0.0, 1.0]], [1.0, 4.0], [0.5, 0.5]
    gaps = []
    for s in range(3):
        r = compute_matched_gap(u, cost, p, [0.25], steps=3000, seed=s)[0]
        gaps.append(r["compute_matched_gap"])
    assert min(gaps) > 0.2                                         # dominance every seed


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
