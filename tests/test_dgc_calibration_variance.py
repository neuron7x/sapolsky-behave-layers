import math
import pytest
from cwc.governance.calibration_variance import (
    CalibrationObservation,
    estimate_all_balanced_variance_components,
    estimate_balanced_variance_components,
)


def rows(values_by_task, comparison="cmp"):
    out = []
    for task, values in values_by_task.items():
        for replicate, value in enumerate(values):
            out.append(CalibrationObservation(comparison, task, replicate, value))
    return out


def test_zero_within_known_between():
    est = estimate_balanced_variance_components(
        rows({"a": [0, 0], "b": [2, 2], "c": [4, 4]}), comparison_id="cmp"
    )
    assert est.within_task_std == 0
    assert est.between_task_std == pytest.approx(2.0)
    assert est.grand_mean == 2.0
    assert len(est.population_digest) == 64


def test_known_variance_decomposition():
    est = estimate_balanced_variance_components(
        rows({"a": [0, 2], "b": [2, 4], "c": [4, 6]}), comparison_id="cmp"
    )
    assert est.within_task_std == pytest.approx(math.sqrt(2.0))
    assert est.task_mean_variance == pytest.approx(4.0)
    assert est.between_task_std == pytest.approx(math.sqrt(3.0))


def test_duplicate_rejected():
    obs = rows({"a": [0, 1], "b": [1, 2]})
    obs.append(CalibrationObservation("cmp", "a", 0, 3))
    with pytest.raises(ValueError, match="duplicate"):
        estimate_balanced_variance_components(obs, comparison_id="cmp")


def test_unbalanced_rejected():
    obs = rows({"a": [0, 1], "b": [1, 2, 3]})
    with pytest.raises(ValueError, match="balanced"):
        estimate_balanced_variance_components(obs, comparison_id="cmp")


def test_noncontiguous_rejected():
    obs = [
        CalibrationObservation("cmp", "a", 0, 0),
        CalibrationObservation("cmp", "a", 2, 1),
        CalibrationObservation("cmp", "b", 0, 1),
        CalibrationObservation("cmp", "b", 2, 2),
    ]
    with pytest.raises(ValueError, match="contiguous"):
        estimate_balanced_variance_components(obs, comparison_id="cmp")


def test_multi_comparison_is_separate():
    obs = rows({"a": [0, 0], "b": [2, 2]}, "x") + rows({"a": [1, 1], "b": [5, 5]}, "y")
    estimates = estimate_all_balanced_variance_components(obs)
    assert [e.comparison_id for e in estimates] == ["x", "y"]
    assert estimates[0].between_task_std != estimates[1].between_task_std


def test_minimum_tasks_and_repeats():
    with pytest.raises(ValueError, match="two calibration tasks"):
        estimate_balanced_variance_components(rows({"a": [0, 1]}), comparison_id="cmp")
    with pytest.raises(ValueError, match="two replicates"):
        estimate_balanced_variance_components(rows({"a": [0], "b": [1]}), comparison_id="cmp")
