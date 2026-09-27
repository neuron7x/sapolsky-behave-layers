import pytest

from cwc.governance.calibration_variance import CalibrationObservation
from cwc.governance.product_statistical_plan import ProductStatisticalPlan
from cwc.governance.trial_sizing_receipt import freeze_cluster_aware_trial_sizing


def obs(comparison, task, values):
    return [CalibrationObservation(comparison, task, index, value) for index, value in enumerate(values)]


def population():
    rows = []
    for comparison, shift in [("cost", 0.0), ("quality", 0.01)]:
        rows += obs(comparison, "a", [0.00 + shift, 0.01 + shift])
        rows += obs(comparison, "b", [0.01 + shift, 0.02 + shift])
        rows += obs(comparison, "c", [0.02 + shift, 0.03 + shift])
    return rows


def test_receipt_is_deterministic_and_planning_only():
    plan = ProductStatisticalPlan()
    kwargs = dict(
        observations=population(),
        effects_of_interest={"cost": 0.2, "quality": 0.2},
        confirmatory_task_count=80,
        plan=plan,
    )
    first = freeze_cluster_aware_trial_sizing(**kwargs)
    second = freeze_cluster_aware_trial_sizing(**kwargs)
    assert first == second
    assert first.planning_only is True
    assert first.required_trials_per_task >= plan.min_trials_per_task
    assert len(first.receipt_digest) == 64


def test_effect_map_must_be_exact():
    with pytest.raises(ValueError, match="match"):
        freeze_cluster_aware_trial_sizing(
            observations=population(),
            effects_of_interest={"cost": 0.2},
            confirmatory_task_count=80,
            plan=ProductStatisticalPlan(),
        )


def test_comparisons_must_share_design():
    rows = population()
    rows = [
        row for row in rows
        if not (row.comparison_id == "quality" and row.task_id == "c" and row.replicate == 1)
    ]
    with pytest.raises(ValueError):
        freeze_cluster_aware_trial_sizing(
            observations=rows,
            effects_of_interest={"cost": 0.2, "quality": 0.2},
            confirmatory_task_count=80,
            plan=ProductStatisticalPlan(),
        )


def test_task_heterogeneity_can_fail_closed():
    rows = []
    for task, value in [("a", 0.0), ("b", 1.0), ("c", 2.0)]:
        rows += obs("cost", task, [value, value])
    with pytest.raises(RuntimeError, match="UNDERPOWERED_TASK_HETEROGENEITY"):
        freeze_cluster_aware_trial_sizing(
            observations=rows,
            effects_of_interest={"cost": 0.01},
            confirmatory_task_count=10,
            plan=ProductStatisticalPlan(),
        )
