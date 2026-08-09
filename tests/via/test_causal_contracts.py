from __future__ import annotations

import math

import pytest

from cwc.causal.cate import (
    collapse_context,
    destroy_interaction,
    doubly_robust_policy_value,
    ips_policy_value,
    oracle_gap,
    treatment_effects_against,
)
from cwc.causal.interventions import balanced_randomized_assignments
from cwc.causal.potential_outcomes import (
    PotentialOutcome,
    TrialObservation,
    context_action_matrix,
    validate_exhaustive_replay,
)


def _replay() -> list[PotentialOutcome]:
    return [
        PotentialOutcome("u1", "easy", "shallow", 1.0),
        PotentialOutcome("u1", "easy", "deep", 0.2),
        PotentialOutcome("u2", "easy", "shallow", 0.9),
        PotentialOutcome("u2", "easy", "deep", 0.3),
        PotentialOutcome("u3", "hard", "shallow", 0.1),
        PotentialOutcome("u3", "hard", "deep", 1.0),
        PotentialOutcome("u4", "hard", "shallow", 0.2),
        PotentialOutcome("u4", "hard", "deep", 0.9),
    ]


def test_exhaustive_replay_aggregates_unit_weighted_surface() -> None:
    rows = _replay()
    assert validate_exhaustive_replay(rows) == ("deep", "shallow")
    contexts, actions, matrix, counts = context_action_matrix(rows, actions=("shallow", "deep"))
    assert contexts == ("easy", "hard")
    assert actions == ("shallow", "deep")
    assert counts == {"easy": 2, "hard": 2}
    assert matrix == [[0.95, 0.25], [0.15000000000000002, 0.95]]
    assert oracle_gap(matrix)["gap"] > 0.3


def test_exhaustive_replay_fails_closed_on_missing_or_duplicate_action() -> None:
    rows = _replay()
    with pytest.raises(ValueError, match="not exhaustive"):
        validate_exhaustive_replay(rows[:-1])
    with pytest.raises(ValueError, match="duplicate"):
        validate_exhaustive_replay(rows + [rows[0]])


def test_context_cannot_change_inside_one_independent_unit() -> None:
    rows = _replay()
    rows[1] = PotentialOutcome("u1", "hard", "deep", 0.2)
    with pytest.raises(ValueError, match="changes context"):
        validate_exhaustive_replay(rows)


def test_structural_nulls_have_zero_oracle_gap() -> None:
    matrix = [[1.0, 0.0, 0.2], [0.1, 1.2, 0.3], [0.2, 0.1, 1.4]]
    assert oracle_gap(matrix)["gap"] > 0
    assert abs(float(oracle_gap(destroy_interaction(matrix))["gap"])) <= 1e-12
    assert abs(float(oracle_gap(collapse_context(matrix))["gap"])) <= 1e-12


def test_treatment_effects_are_relative_to_frozen_baseline() -> None:
    matrix = [[1.0, 2.0], [4.0, 1.0]]
    assert treatment_effects_against(matrix, baseline_action=0) == [[0.0, 1.0], [0.0, -3.0]]


def test_balanced_randomization_is_deterministic_and_stratified() -> None:
    units = [f"u{i}" for i in range(12)]
    strata = {u: ("a" if i < 6 else "b") for i, u in enumerate(units)}
    first = balanced_randomized_assignments(units, ["x", "y", "z"], seed=17, strata=strata)
    second = balanced_randomized_assignments(units, ["x", "y", "z"], seed=17, strata=strata)
    assert first == second
    for stratum in ("a", "b"):
        counts = {a: 0 for a in ("x", "y", "z")}
        for unit, action in first.items():
            if strata[unit] == stratum:
                counts[action] += 1
        assert max(counts.values()) - min(counts.values()) <= 1


def test_ips_and_doubly_robust_recover_known_policy_value() -> None:
    # Balanced randomized trial, propensity 0.5. Target policy chooses action a
    # in context x and b in context y. Outcome model is exact, so DR is exact.
    observations = [
        TrialObservation("1", "x", "a", 1.0, 0.5, {"a": 1.0, "b": 0.0}),
        TrialObservation("2", "x", "b", 0.0, 0.5, {"a": 1.0, "b": 0.0}),
        TrialObservation("3", "y", "a", 0.0, 0.5, {"a": 0.0, "b": 1.0}),
        TrialObservation("4", "y", "b", 1.0, 0.5, {"a": 0.0, "b": 1.0}),
    ]
    policy = {"x": {"a": 1.0, "b": 0.0}, "y": {"a": 0.0, "b": 1.0}}
    assert math.isclose(ips_policy_value(observations, policy), 1.0)
    assert math.isclose(doubly_robust_policy_value(observations, policy), 1.0)
