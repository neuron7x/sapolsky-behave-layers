import pytest

from cwc.governance.product_statistical_plan import (
    ProductStatisticalPlan,
    approximate_required_trials_per_task,
    cluster_aware_required_trials_per_task,
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
    assert plan.method == "DGC_PRODUCT_PAIRED_CLUSTER_AWARE_V2"


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


def test_cluster_aware_sizing_respects_minimum_floor_when_variance_small():
    plan = ProductStatisticalPlan()
    sizing = cluster_aware_required_trials_per_task(
        between_task_std=0.01,
        within_task_std=0.01,
        effect_of_interest=0.10,
        confirmatory_task_count=400,
        plan=plan,
    )
    assert sizing.required_trials_per_task == plan.min_trials_per_task
    assert sizing.achieved_standard_error_at_required_trials <= sizing.target_standard_error


def test_cluster_aware_repeats_increase_with_within_task_variance():
    plan = ProductStatisticalPlan(max_trials_per_task=200)
    low = cluster_aware_required_trials_per_task(
        between_task_std=0.01,
        within_task_std=0.10,
        effect_of_interest=0.05,
        confirmatory_task_count=80,
        plan=plan,
    )
    high = cluster_aware_required_trials_per_task(
        between_task_std=0.01,
        within_task_std=0.30,
        effect_of_interest=0.05,
        confirmatory_task_count=80,
        plan=plan,
    )
    assert high.required_trials_per_task >= low.required_trials_per_task


def test_between_task_heterogeneity_cannot_be_hidden_by_infinite_repeats():
    plan = ProductStatisticalPlan(max_trials_per_task=500)
    with pytest.raises(RuntimeError, match="UNDERPOWERED_TASK_HETEROGENEITY"):
        cluster_aware_required_trials_per_task(
            between_task_std=1.0,
            within_task_std=0.01,
            effect_of_interest=0.01,
            confirmatory_task_count=20,
            plan=plan,
        )


def test_cluster_aware_hard_cap_fails_closed():
    plan = ProductStatisticalPlan(max_trials_per_task=5)
    with pytest.raises(RuntimeError, match="UNDERPOWERED"):
        cluster_aware_required_trials_per_task(
            between_task_std=0.0,
            within_task_std=1.0,
            effect_of_interest=0.05,
            confirmatory_task_count=80,
            plan=plan,
        )


def test_legacy_iid_helper_retained_only_for_research_compatibility():
    plan = ProductStatisticalPlan(max_trials_per_task=200)
    n = approximate_required_trials_per_task(
        calibration_std=0.10,
        effect_of_interest=0.05,
        confirmatory_task_count=80,
        plan=plan,
    )
    assert isinstance(n, int) and n >= plan.min_trials_per_task


def test_invalid_plan_fails_closed():
    with pytest.raises(ValueError):
        ProductStatisticalPlan(familywise_alpha=1.0)
    with pytest.raises(ValueError):
        ProductStatisticalPlan(calibration_fraction=0.5)
    with pytest.raises(ValueError):
        ProductStatisticalPlan(min_trials_per_task=10, max_trials_per_task=5)
