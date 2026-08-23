from __future__ import annotations

import pytest

from cwc.governance.finite_panel_bernstein_planning import (
    empirical_bernstein_proxy_half_width,
    required_replicates_for_proxy_width,
)


def test_proxy_width_shrinks_with_more_observations():
    small = empirical_bernstein_proxy_half_width(
        sample_variance_proxy=0.01,
        support_range=2.0,
        n=100,
        delta=0.05 / 24.0,
    )
    large = empirical_bernstein_proxy_half_width(
        sample_variance_proxy=0.01,
        support_range=2.0,
        n=1000,
        delta=0.05 / 24.0,
    )
    assert large < small


def test_required_replicates_is_minimal_integer_solution():
    result = required_replicates_for_proxy_width(
        sample_variance_proxy=0.01,
        support_range=2.0,
        target_half_width=0.02,
        delta=0.05 / 24.0,
        task_count=300,
        max_replicates_per_task=50,
    )
    assert result.required_replicates_per_task >= 1
    assert result.achieved_proxy_half_width <= 0.02
    if result.required_replicates_per_task > 1:
        previous = empirical_bernstein_proxy_half_width(
            sample_variance_proxy=0.01,
            support_range=2.0,
            n=300 * (result.required_replicates_per_task - 1),
            delta=0.05 / 24.0,
        )
        assert previous > 0.02


def test_bounded_variance_ceiling_is_enforced():
    with pytest.raises(ValueError, match="variance ceiling"):
        empirical_bernstein_proxy_half_width(
            sample_variance_proxy=1.1,
            support_range=2.0,
            n=100,
            delta=0.01,
        )


def test_underpowered_cap_fails_closed():
    with pytest.raises(RuntimeError, match="UNDERPOWERED_EMPIRICAL_BERNSTEIN_PROXY"):
        required_replicates_for_proxy_width(
            sample_variance_proxy=0.25,
            support_range=2.0,
            target_half_width=0.005,
            delta=0.05 / 24.0,
            task_count=20,
            max_replicates_per_task=5,
        )
