"""Tests for WP11 Pinsker dichotomy certification."""
from __future__ import annotations

import pytest

from experiments.wp11_pinsker.src import pinsker as P


@pytest.fixture(scope="module")
def result():
    return P.analyze()


def test_verdict_certified(result):
    assert result["verdict"] == "PINSKER_DICHOTOMY_CERTIFIED"


def test_regular_regime_exponent_near_one(result):
    r = result["regular"]
    assert r["n"] >= 50
    assert 0.85 <= r["mean"] <= 1.15
    assert r["frac_in_band"] >= 0.85


def test_critical_regime_exponent_near_half(result):
    c = result["critical"]
    assert c["n"] >= 50
    assert 0.40 <= c["mean"] <= 0.65
    assert c["frac_in_band"] >= 0.90
