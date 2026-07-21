"""Tests for L4e — lock the mechanism result. analyze() is expensive; compute once."""
from __future__ import annotations

import math

import pytest

from experiments.wp3_plasticity_v7_mechanism.src import mechanism as M


@pytest.fixture(scope="module")
def result():
    return M.analyze()


def test_verdict_mechanism_incomplete(result):
    assert result["verdict"] == "L4E_MECHANISM_INCOMPLETE"


def test_two_arm_is_drift_limited(result):
    # 2-arm reduction scales near the drift limit -1, steeper than the full governor -0.654
    e = result["reduced_budget_exponent"]
    assert not math.isnan(e)
    assert e < -0.9                                   # near -1 (drift-limited)
    assert e < result["target_full_governor_exponent"]  # steeper than the full governor


def test_dead_arms_matter_exponent_mismatch(result):
    assert result["exponent_match_within_0.15"] is False


def test_noise_as_exploration_is_two_arm(result):
    # the one signature the ablation DOES reproduce
    assert result["reduced_noise_ratio"] < 1.0
    assert result["noise_sign_match_both_below_1"] is True
