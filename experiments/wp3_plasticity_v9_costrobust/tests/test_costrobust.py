"""Tests for L4g cost-model robustness."""
from __future__ import annotations

import pytest

from experiments.wp3_plasticity_v9_costrobust.src import costrobust as C


@pytest.fixture(scope="module")
def result():
    return C.analyze()


def test_verdict_robust(result):
    assert result["verdict"] == "L4G_ROBUST"


def test_every_transform_identifiable(result):
    for name in C.TRANSFORMS:
        assert result["per_transform"][name]["identifiable"] is True
        assert result["per_transform"][name]["gap_lower_bound"] > 0.0


def test_governor_recovers_under_every_transform(result):
    for name in C.TRANSFORMS:
        assert result["per_transform"][name]["worst_governor_recovery"] >= 0.8


def test_log_transform_shrinks_but_keeps_gap(result):
    # log compresses the head-vs-attn ratio -> smaller gap, still positive
    glo = {n: result["per_transform"][n]["gap_lower_bound"] for n in C.TRANSFORMS}
    assert glo["log"] < glo["linear"]
    assert glo["log"] > 0.0
