"""Tests for WP5-AC3 inferred-difficulty boundary."""
from __future__ import annotations

import pytest

from experiments.wp5_adaptive_compute.src import inferred as I


@pytest.fixture(scope="module")
def result():
    return I.analyze()


def test_verdict_boundary_mapped(result):
    assert result["verdict"] == "AC3_BOUNDARY_MAPPED"


def test_full_information_reproduces_ac2(result):
    assert result["recovery_full_info"] >= 0.9


def test_zero_information_no_gap(result):
    assert result["recovery_zero_info"] <= 0.15


def test_monotone_and_abstains(result):
    assert result["monotone_in_information"] is True
    assert result["controller_abstains"] is True


def test_recovery_tracks_information(result):
    # recovery should fall as info falls across the sweep
    recs = [r["recovery_mean"] for r in result["sweep"]]
    assert recs[0] > recs[len(recs) // 2] > recs[-1]
