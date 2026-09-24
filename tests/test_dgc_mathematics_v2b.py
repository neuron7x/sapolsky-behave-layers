from __future__ import annotations

import pytest

from cwc.governance.metareasoning_bounds import certify_myopic_suboptimality_upper_bound
from cwc.governance.nonstationary import current_mean_lower_bound_under_bounded_drift


def test_bounded_drift_lcb_reduces_stationary_bound_by_average_drift() -> None:
    result = current_mean_lower_bound_under_bounded_drift(
        [0.8] * 100,
        drift_to_current=[0.05] * 100,
        lower=0.0,
        upper=1.0,
        delta=0.05,
    )
    assert result.average_drift_budget == pytest.approx(0.05)
    assert result.current_mean_lower == pytest.approx(result.stationary_mean_lower - 0.05)


def test_bounded_drift_lcb_rejects_negative_drift_budget() -> None:
    with pytest.raises(ValueError, match="drift bounds"):
        current_mean_lower_bound_under_bounded_drift(
            [0.5], drift_to_current=[-0.1], lower=0.0, upper=1.0, delta=0.05
        )


def test_perfect_information_bounds_myopic_multistep_gap() -> None:
    bound = certify_myopic_suboptimality_upper_bound(
        myopic_value=0.0,
        perfect_information_value_upper=1.0,
        pure_information_certified=True,
    )
    assert bound.suboptimality_upper_bound == pytest.approx(1.0)
    assert 0.8 <= bound.suboptimality_upper_bound


def test_myopic_gap_bound_refuses_interventional_compute() -> None:
    with pytest.raises(ValueError, match="pure-information"):
        certify_myopic_suboptimality_upper_bound(
            myopic_value=0.0,
            perfect_information_value_upper=1.0,
            pure_information_certified=False,
        )
