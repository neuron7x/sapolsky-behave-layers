import pytest

from cwc.governance.product_statistical_plan import (
    ProductStatisticalPlan,
    approximate_required_trials_per_task,
    deterministic_task_split,
)


def test_default_plan_has_global_24_claim_familywise_allocation():
    plan = ProductStatisticalPlan()
    assert plan.family_count == 2
    assert plan.baseline_count == 4
    assert plan.endpoint_count == 3
    assert plan.per_claim_alpha == pytest.approx(0.05 / 24.0)
    assert plan.quality_noninferiority_margin == pytest.approx(0.02)
    assert plan.catastrophic_regret_noninferiority_margin == pytest.approx(0.01)
    assert plan.minimum_cost_effect_of_interest == pytest.approx(0.05)


def test_plan_digest_is_deterministic_and_changes_with_margin():
    a = ProductStatisticalPlan()
    b = ProductStatisticalPlan()
    c = ProductStatisticalPlan(quality_noninferiority_margin=0.03)
    assert a.digest == b.digest
    assert a.digest != c.digest


def test_task_split_is_deterministic_disjoint_and_complete():
    tasks = [f"task-{i:03d}" for i in range(100)]
    cal_a, conf_a = deterministic_task_split(tasks, calibration_fraction=0.20)
    cal_b, conf_b = deterministic_task_split(reversed(tasks), calibration_fraction=0.20)
    assert cal_a == cal_b
    assert conf_a == conf_b
    assert len(cal_a) == 20
    assert len(conf_a) == 80
    assert not (set(cal_a) & set(conf_a))
    assert set(cal_a) | set(conf_a) == set(tasks)


def test_split_requires_nontrivial_population():
    with pytest.raises(ValueError):
        deterministic_task_split(["a", "b", "c", "d"])


def test_power_sizing_respects_minimum_trials_floor():
    plan = ProductStatisticalPlan()
    n = approximate_required_trials_per_task(
        calibration_std=0.01,
        effect_of_interest=0.10,
        confirmatory_task_count=400,
        plan=plan,
    )
    assert n == plan.min_trials_per_task


def test_power_sizing_increases_with_variance():
    plan = ProductStatisticalPlan(max_trials_per_task=200)
    low = approximate_required_trials_per_task(
        calibration_std=0.10,
        effect_of_interest=0.05,
        confirmatory_task_count=80,
        plan=plan,
    )
    high = approximate_required_trials_per_task(
        calibration_std=0.20,
        effect_of_interest=0.05,
        confirmatory_task_count=80,
        plan=plan,
    )
    assert high >= low


def test_underpowered_plan_fails_closed_instead_of_lowering_standard():
    plan = ProductStatisticalPlan(max_trials_per_task=5)
    with pytest.raises(RuntimeError, match="UNDERPOWERED"):
        approximate_required_trials_per_task(
            calibration_std=1.0,
            effect_of_interest=0.001,
            confirmatory_task_count=5,
            plan=plan,
        )


def test_invalid_plan_fails_closed():
    with pytest.raises(ValueError):
        ProductStatisticalPlan(familywise_alpha=1.0)
    with pytest.raises(ValueError):
        ProductStatisticalPlan(calibration_fraction=0.5)
    with pytest.raises(ValueError):
        ProductStatisticalPlan(min_trials_per_task=10, max_trials_per_task=5)
