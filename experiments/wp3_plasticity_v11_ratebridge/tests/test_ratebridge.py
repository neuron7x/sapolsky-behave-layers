"""Tests for L4i rate-function bridge."""
from __future__ import annotations

import pytest

from experiments.wp3_plasticity_v11_ratebridge.src import ratebridge as R


@pytest.fixture(scope="module")
def result():
    return R.analyze()


def test_verdict_bridge_confirmed(result):
    assert result["verdict"] == "L4I_BRIDGE_CONFIRMED"


def test_ceiling_holds_everywhere(result):
    assert result["ceiling_holds"] is True
    for row in result["curve"]:
        assert row["v_gov"] <= row["v_star"] + 1e-6      # V* is a valid ceiling


def test_near_saturation(result):
    assert result["min_saturation"] >= 0.90
    # near-optimal at full information
    full = next(r for r in result["curve"] if r["flip_p"] == 0.0)
    assert full["saturation"] >= 0.999


def test_gap_matches_confirmatory(result):
    import math
    assert math.isclose(result["oracle_gap"], 0.1909, abs_tol=6e-3)
