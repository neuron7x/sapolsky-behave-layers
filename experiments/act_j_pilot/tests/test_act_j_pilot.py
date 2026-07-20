"""Fast falsification test: a trained controller must reach V*(R) and show the
phase transition. Small training budget so it runs on CPU in a few seconds; the full
sweep lives in the runner + evidence bundle.
"""
from experiments.act_j_pilot.src.act_j_pilot import train_controller
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


def test_more_information_never_decreases_realised_value():
    # lowering the price (more info) is monotone in value, and value stays <= G
    g = 0.25  # oracle gap of REGULAR
    vals = [train_controller(REGULAR, PRIOR, beta=b, steps=2000, seed=0).value for b in (2.0, 0.5, 0.15)]
    assert vals[0] <= vals[1] + 1e-2 <= vals[2] + 2e-2
    assert all(v <= g + 1e-3 for v in vals)
