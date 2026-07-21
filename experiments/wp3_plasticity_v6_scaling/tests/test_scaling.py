"""Tests for L4d — lock the higher-power scaling result deterministically.

analyze() is expensive (24 seeds x 11 margins x 6 cells), so it is computed once and reused.
"""
from __future__ import annotations

import math

import pytest

from experiments.wp3_plasticity_v6_scaling.src import scaling as S


@pytest.fixture(scope="module")
def result():
    return S.analyze()


def test_verdict_budget_scaling_violated(result):
    assert result["verdict"] == "L4D_BUDGET_SCALING_VIOLATED"


def test_delta_star_monotone_decreasing_no_nan(result):
    ds = [result["budget_delta_star"][f"N_{n}"] for n in S.BUDGETS]
    assert not any(math.isnan(x) for x in ds)          # extended grid: all measurable
    assert all(ds[i] >= ds[i + 1] for i in range(len(ds) - 1))


def test_budget_ratio_steeper_than_law(result):
    # 0.247 < the 1/sqrt(8)=0.354 law and just below the a-priori band floor 0.25
    r = result["budget_ratio_N12000_over_N1500"]
    assert r < result["predicted_budget_ratio_1_over_sqrt8"]
    assert r < 0.25


def test_noise_axis_refutes_samplecomplexity(result):
    # ratio < 1: more noise -> smaller collapse margin (exploration), opposite of (sigma/Delta)^2
    r = result["sigma_scaling_ratio_highpower"]
    assert r < 1.0
    assert result["sigma_scaling_is_samplecomplexity"] is False
