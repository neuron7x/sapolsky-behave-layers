from __future__ import annotations

import math

import pytest

from cwc.governance.empirical_bernstein_pareto import (
    BOUND_METHOD,
    certify_multi_baseline_empirical_bernstein,
    empirical_bernstein_lower_bound,
)
from cwc.governance.pareto import PairedBaselineEvidence


def evidence(baseline_id: str, *, n: int, cost: float = 0.10, quality: float = 0.0, regret: float = 0.0, coverage: float = 1.0):
    return PairedBaselineEvidence(
        baseline_id=baseline_id,
        paired_task_digest="a" * 64,
        coverage=coverage,
        baseline_minus_dgc_cost=(cost,) * n,
        dgc_minus_baseline_quality=(quality,) * n,
        baseline_minus_dgc_catastrophic_regret=(regret,) * n,
        cost_gain_support=(-1.0, 1.0),
        quality_gain_support=(-1.0, 1.0),
        catastrophic_gain_support=(-1.0, 1.0),
    )


def test_empirical_bernstein_constant_sequence_shrinks_with_n():
    small = empirical_bernstein_lower_bound((0.1,) * 100, lower=-1.0, upper=1.0, delta=0.01)
    large = empirical_bernstein_lower_bound((0.1,) * 1000, lower=-1.0, upper=1.0, delta=0.01)
    assert large.lower > small.lower
    assert large.method == BOUND_METHOD
    assert large.mean == pytest.approx(0.1)


def test_zero_variance_matches_maurer_pontil_remainder_term_exactly():
    n = 101
    delta = 0.01
    lower, upper = -1.0, 1.0
    mean = 0.25
    bound = empirical_bernstein_lower_bound((mean,) * n, lower=lower, upper=upper, delta=delta)
    expected_width = 7.0 * (upper - lower) * math.log(2.0 / delta) / (3.0 * (n - 1))
    assert bound.lower == pytest.approx(max(lower, mean - expected_width), rel=0, abs=1e-15)


def test_affine_rescaling_preserves_empirical_bernstein_lower_bound():
    raw = (2.0, 2.5, 3.0, 3.5, 4.0, 2.25, 3.25, 3.75)
    delta = 0.02
    x = empirical_bernstein_lower_bound(raw, lower=2.0, upper=4.0, delta=delta)
    unit = tuple((value - 2.0) / 2.0 for value in raw)
    y = empirical_bernstein_lower_bound(unit, lower=0.0, upper=1.0, delta=delta)
    assert x.lower == pytest.approx(2.0 + 2.0 * y.lower, rel=0, abs=1e-12)


def test_empirical_bernstein_rejects_out_of_support_observation():
    with pytest.raises(ValueError, match="outside declared support"):
        empirical_bernstein_lower_bound((0.0, 1.1), lower=-1.0, upper=1.0, delta=0.01)


def test_multi_baseline_requires_unique_ids_and_full_coverage():
    rows = (evidence("B0", n=1000), evidence("B0", n=1000))
    with pytest.raises(ValueError, match="unique"):
        certify_multi_baseline_empirical_bernstein(
            rows,
            alpha=0.025,
            quality_noninferiority_margin=0.02,
            catastrophic_noninferiority_margin=0.01,
        )
    with pytest.raises(ValueError, match="full paired coverage"):
        certify_multi_baseline_empirical_bernstein(
            (evidence("B0", n=1000, coverage=0.99),),
            alpha=0.025,
            quality_noninferiority_margin=0.02,
            catastrophic_noninferiority_margin=0.01,
        )


def test_large_low_variance_population_can_certify_all_three_endpoints():
    rows = tuple(evidence(f"B{i}", n=20000) for i in range(4))
    cert = certify_multi_baseline_empirical_bernstein(
        rows,
        alpha=0.025,
        quality_noninferiority_margin=0.02,
        catastrophic_noninferiority_margin=0.01,
    )
    assert cert.all_baselines_certified is True
    assert cert.per_metric_delta == pytest.approx(0.025 / 12.0)
    assert cert.per_metric_delta == pytest.approx(0.05 / 24.0)
    assert all(row.certified_cost_reduction for row in cert.results)
    assert all(row.certified_quality_noninferiority for row in cert.results)
    assert all(row.certified_catastrophic_noninferiority for row in cert.results)


def test_small_population_does_not_manufacture_cost_superiority():
    cert = certify_multi_baseline_empirical_bernstein(
        tuple(evidence(f"B{i}", n=10, cost=0.01) for i in range(4)),
        alpha=0.025,
        quality_noninferiority_margin=0.02,
        catastrophic_noninferiority_margin=0.01,
    )
    assert cert.all_baselines_certified is False
