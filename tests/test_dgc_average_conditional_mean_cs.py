from __future__ import annotations

import math

import pytest

from cwc.governance.average_conditional_mean_cs import (
    ASSUMPTION_BOUNDARY,
    METHOD,
    average_conditional_mean_bound,
    certify_multi_baseline_anytime_valid,
)
from cwc.governance.pareto import PairedBaselineEvidence


def evidence(baseline_id: str, *, n: int, cost: float = 0.2, quality: float = 0.0, regret: float = 0.0):
    return PairedBaselineEvidence(
        baseline_id=baseline_id,
        paired_task_digest="a" * 64,
        coverage=1.0,
        baseline_minus_dgc_cost=(cost,) * n,
        dgc_minus_baseline_quality=(quality,) * n,
        baseline_minus_dgc_catastrophic_regret=(regret,) * n,
        cost_gain_support=(-1.0, 1.0),
        quality_gain_support=(-1.0, 1.0),
        catastrophic_gain_support=(-1.0, 1.0),
    )


def test_terminal_slice_matches_frozen_hrms_formula_for_constant_sequence():
    result = average_conditional_mean_bound(
        (0.1,) * 1000,
        lower=-1.0,
        upper=1.0,
        alpha=0.05 / 24.0,
    )
    assert result.method == METHOD
    assert result.assumption_boundary == ASSUMPTION_BOUNDARY
    assert result.sample_mean == pytest.approx(0.1)
    assert result.half_width == pytest.approx(0.02743448269877649, abs=1e-15)
    assert result.lower == pytest.approx(0.07256551730122363, abs=1e-15)


def test_bound_shrinks_without_claiming_independence():
    small = average_conditional_mean_bound((0.1,) * 100, lower=-1.0, upper=1.0, alpha=0.01)
    large = average_conditional_mean_bound((0.1,) * 1000, lower=-1.0, upper=1.0, alpha=0.01)
    assert large.half_width < small.half_width
    assert "NO_IID_REQUIRED" in large.assumption_boundary


def test_affine_rescaling_is_equivariant():
    base = average_conditional_mean_bound((0.1, 0.2, 0.3, 0.4) * 100, lower=0.0, upper=1.0, alpha=0.01)
    scaled_values = tuple(10.0 + 4.0 * x for x in ((0.1, 0.2, 0.3, 0.4) * 100))
    scaled = average_conditional_mean_bound(scaled_values, lower=10.0, upper=14.0, alpha=0.01)
    assert scaled.sample_mean == pytest.approx(10.0 + 4.0 * base.sample_mean)
    assert scaled.lower == pytest.approx(10.0 + 4.0 * base.lower)
    assert scaled.upper == pytest.approx(10.0 + 4.0 * base.upper)


def test_out_of_support_and_bad_alpha_fail_closed():
    with pytest.raises(ValueError, match="outside declared support"):
        average_conditional_mean_bound((0.0, 1.1), lower=0.0, upper=1.0, alpha=0.01)
    with pytest.raises(ValueError, match="alpha"):
        average_conditional_mean_bound((0.0, 0.1), lower=0.0, upper=1.0, alpha=1.0)


def test_multi_baseline_union_allocation_is_exact():
    cert = certify_multi_baseline_anytime_valid(
        tuple(evidence(f"B{i}", n=20000) for i in range(4)),
        alpha=0.025,
        quality_noninferiority_margin=0.02,
        catastrophic_noninferiority_margin=0.01,
    )
    assert cert.per_metric_alpha == pytest.approx(0.025 / 12.0)
    assert cert.all_baselines_certified is True
    assert len(cert.results) == 4


def test_small_population_does_not_manufacture_support():
    cert = certify_multi_baseline_anytime_valid(
        tuple(evidence(f"B{i}", n=10, cost=0.01) for i in range(4)),
        alpha=0.025,
        quality_noninferiority_margin=0.02,
        catastrophic_noninferiority_margin=0.01,
    )
    assert cert.all_baselines_certified is False
