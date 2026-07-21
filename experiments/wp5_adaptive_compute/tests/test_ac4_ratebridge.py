"""Tests for WP5-AC4 compute rate-function bridge."""
from __future__ import annotations

import pytest

from experiments.wp5_adaptive_compute.src import ratebridge as R


@pytest.fixture(scope="module")
def result():
    return R.analyze()


def test_verdict_bridge_confirmed(result):
    assert result["verdict"] == "AC4_RATE_BRIDGE_CONFIRMED"


def test_ceiling_holds_everywhere(result):
    assert result["ceiling_holds"] is True
    for row in result["curve"]:
        assert row["v_gov"] <= row["v_star"] + 1e-6


def test_high_info_saturation(result):
    assert result["min_high_info_saturation"] >= 0.90


def test_low_info_gap_documented(result):
    # honest cross-mechanism finding: saturation falls at low info (committed != RI)
    assert result["min_saturation_all"] < result["min_high_info_saturation"]
