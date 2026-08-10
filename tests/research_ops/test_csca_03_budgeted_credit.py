from __future__ import annotations

import random

from cwc.credit.budgeted_shapley import antithetic_crn_mc, crn_chain_mc, exact_resampling_shapley, legacy_independent_mc
from cwc.credit.context_authority import decide_context_direction

PLAYERS = ("A", "B", "C", "D")


def test_crn_gives_exact_zero_to_structurally_irrelevant_candidates() -> None:
    factual = {"A": 1, "B": 1, "C": -1, "D": 1}
    def f(x): return 1.0 * x["A"]
    est = crn_chain_mc(factual, PLAYERS, f, permutations=32, rng=random.Random(7))
    assert all(abs(est.credits[p]) <= 1e-15 for p in ("B", "C", "D"))


def test_legacy_independent_resampling_can_create_false_credit_noise() -> None:
    factual = {"A": 1, "B": 1, "C": -1, "D": 1}
    def f(x): return 1.0 * x["A"]
    est = legacy_independent_mc(factual, PLAYERS, f, permutations=8, rng=random.Random(11))
    assert any(abs(est.credits[p]) > 1e-12 for p in ("B", "C", "D"))


def test_antithetic_exact_on_additive_symmetric_single_cause() -> None:
    factual = {"A": -1, "B": 1, "C": -1, "D": 1}
    def f(x): return 1.0 * x["A"]
    exact = exact_resampling_shapley(factual, PLAYERS, f)
    est = antithetic_crn_mc(factual, PLAYERS, f, pairs=1, rng=random.Random(3))
    for p in PLAYERS:
        assert abs(est.credits[p] - exact.credits[p]) <= 1e-15
        assert est.estimator_variance[p] == 0.0
    assert est.variance_estimable is False
    assert exact.variance_estimable is True


def test_low_variance_can_be_precisely_wrong_under_spurious_model_edge() -> None:
    factual = {"A": 1, "B": 1, "C": 1, "D": 1}
    def true(x): return float(x["A"])
    def wrong(x): return 0.1 * x["A"] + 0.9 * x["C"]
    true_phi = exact_resampling_shapley(factual, PLAYERS, true)
    wrong_phi = exact_resampling_shapley(factual, PLAYERS, wrong)
    est = antithetic_crn_mc(factual, PLAYERS, wrong, pairs=4, rng=random.Random(5))
    assert abs(est.credits["C"] - wrong_phi.credits["C"]) <= 1e-15
    assert est.estimator_variance["C"] == 0.0
    assert abs(true_phi.credits["C"]) <= 1e-15
    assert abs(est.credits["C"]) > 0.5


def test_context_sign_flip_forces_context_conditional_authority() -> None:
    decision = decide_context_direction({
        "negative": {"A": -1.0, "B": 0.0, "C": 0.0, "D": 0.0},
        "positive": {"A": 1.0, "B": 0.0, "C": 0.0, "D": 0.0},
    })
    assert decision.state == "CONTEXT_CONDITIONAL_ONLY"
    assert decision.candidate == "A"
    assert decision.sign is None
