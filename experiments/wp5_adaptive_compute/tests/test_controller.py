"""Tests for WP5-AC2 learned compute-controller."""
from __future__ import annotations

import pytest

from experiments.wp5_adaptive_compute.src import controller as C


@pytest.fixture(scope="module")
def result():
    return C.analyze()


def test_verdict_recovers(result):
    assert result["verdict"] == "AC2_CONTROLLER_RECOVERS"


def test_recovers_out_of_sample(result):
    assert result["worst_recovery"] >= 0.8
    assert result["oracle"] > result["best_fixed"] > result["random"]


def test_null_falsifier_and_baseline(result):
    assert result["null_recovery"] <= 0.10
    assert result["random_below_fixed"] is True
