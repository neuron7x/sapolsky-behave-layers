import random

from cwc.credit.ablation_shapley import (
    antithetic_permutation_ablation_shapley,
    exact_ablation_shapley,
)


def test_exact_ablation_shapley_recovers_additive_game():
    weights = {"A": 0.5, "B": -0.25, "C": 0.0, "D": 0.1}
    def value(coalition):
        return sum(weights[p] for p in coalition)
    estimate = exact_ablation_shapley(tuple(weights), value)
    for key, expected in weights.items():
        assert abs(estimate.credits[key] - expected) < 1e-12
    assert estimate.unique_forward_evaluations == 16


def test_antithetic_permutation_is_exact_for_additive_game_and_variance_estimable():
    weights = {"A": 0.5, "B": -0.25, "C": 0.0, "D": 0.1}
    def value(coalition):
        return sum(weights[p] for p in coalition)
    estimate = antithetic_permutation_ablation_shapley(tuple(weights), value, pairs=2, rng=random.Random(7))
    assert estimate.variance_estimable
    for key, expected in weights.items():
        assert abs(estimate.credits[key] - expected) < 1e-12
