"""Tests for WP6 real-LM boundary (analysis over frozen raw runs). Locks the frozen negative."""
from __future__ import annotations

import pytest

from experiments.wp6_real_lm.src import analyze as A


@pytest.fixture(scope="module")
def result():
    return A.analyze()


def test_verdict_real_lm_not_identifiable(result):
    assert result["verdict"] == "WP6_REAL_LM_NOT_IDENTIFIABLE"


def test_real_lm_gap_vanishes_at_every_lambda(result):
    for lam in A.LAMBDAS:
        assert result["real_lm"][str(lam)]["gap_lower_bound"] <= 0.0


def test_positive_control_detects_the_synthetic_gap(result):
    # the null must be real, not an instrument failure: the certificate finds the AC1 gap
    assert result["positive_control_synthetic_ac1"]["gap_lower_bound"] > 0.0
    assert result["positive_control_detects_gap"] is True
