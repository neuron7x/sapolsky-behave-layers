"""Tests for WP5 adaptive-compute identifiability (analysis over frozen raw runs)."""
from __future__ import annotations

import pytest

from experiments.wp5_adaptive_compute.src import analyze as A


@pytest.fixture(scope="module")
def result():
    return A.analyze()


def test_verdict_identifiable(result):
    assert result["verdict"] == "AC1_IDENTIFIABLE"


def test_diagonal_mechanism_is_real(result):
    assert result["diagonal_ok"] is True
    assert result["worst_diagonal"] >= 0.9
    assert result["worst_offdiagonal"] <= 0.3


def test_identifiable_at_every_lambda(result):
    for lam in A.LAMBDAS:
        assert result["real"][str(lam)]["gap_lower_bound"] > 0.0


def test_nulls_vanish_at_zero_cost(result):
    # at lambda=0 both nulls must vanish (isolates the overshoot source)
    assert result["monotone_null"]["0.0"]["gap_lower_bound"] <= 0.0
    assert result["additive_null"]["0.0"]["gap_lower_bound"] <= 0.0


def test_additive_null_vanishes_at_every_lambda(result):
    for lam in A.LAMBDAS:
        assert result["additive_null"][str(lam)]["gap_lower_bound"] <= 0.0
