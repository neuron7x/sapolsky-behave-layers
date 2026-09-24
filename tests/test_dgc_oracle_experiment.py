from __future__ import annotations

from experiments.dgc_01.baselines import b0_fixed, b1_uncertainty, b2_cost_quality, b3_dgc
from experiments.dgc_01.oracle import oracle_should_compute
from experiments.dgc_01.workloads import generate_task


def test_regime_a_high_uncertainty_same_action_stops_dgc() -> None:
    t = generate_task("A", 1)
    assert t.uncertainty_bits > 0.9
    assert not oracle_should_compute(t)
    assert not b3_dgc(t).buy_diagnostic
    assert b0_fixed(t).buy_diagnostic
    assert b1_uncertainty(t).buy_diagnostic


def test_regime_e_low_uncertainty_high_regret_distinguishes_utility_from_accuracy() -> None:
    for seed in range(50):
        t = generate_task("E", seed)
        assert t.uncertainty_bits < 0.3
        assert oracle_should_compute(t)
        assert b3_dgc(t).buy_diagnostic
        assert not b1_uncertainty(t).buy_diagnostic
        assert not b2_cost_quality(t).buy_diagnostic


def test_dgc_matches_exact_one_step_oracle_in_all_frozen_regimes() -> None:
    for regime in "ABCDE":
        for seed in range(200):
            t = generate_task(regime, seed)
            assert b3_dgc(t).buy_diagnostic == oracle_should_compute(t)


def test_frozen_paired_difference_support_bounds_hold() -> None:
    from experiments.dgc_01.baselines import POLICIES

    bounds = {
        "B0_FIXED": (0.0, 0.12),
        "B1_UNCERTAINTY": (-0.06, 1.545),
        "B2_COST_QUALITY_ROUTER": (-0.06, 1.545),
    }
    for regime in "ABCDE":
        for seed in range(2000):
            t = generate_task(regime, seed)
            results = {p(t).policy: p(t).score for p in POLICIES}
            for baseline, (lo, hi) in bounds.items():
                delta = results["B3_DGC"] - results[baseline]
                assert lo <= delta <= hi


def test_misspecified_belief_has_explicit_dgc_counterexample() -> None:
    from experiments.dgc_01.falsifier import find_counterexample

    c = find_counterexample()
    assert c is not None
    assert c["dgc_buy"] is False
    assert float(c["dgc_minus_b0"]) < 0
