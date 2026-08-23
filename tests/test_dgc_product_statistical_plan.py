import pytest

from cwc.governance.product_statistical_plan import (
    PLAN_METHOD,
    PRIMARY_ASSUMPTION_BOUNDARY,
    PRIMARY_CLAIM_TARGET,
    PRIMARY_INFERENCE_METHOD,
    PRIMARY_SEQUENCE_ORDER,
    ProductStatisticalPlan,
    approximate_required_trials_per_task,
    cluster_aware_required_trials_per_task,
    deterministic_task_split,
    deterministic_three_way_task_split,
)


def test_default_plan_has_global_24_claim_allocation_g1_holdout_and_v4_theorem_identity():
    plan = ProductStatisticalPlan()
    assert plan.family_count == 2
    assert plan.baseline_count == 4
    assert plan.endpoint_count == 3
    assert plan.per_claim_alpha == pytest.approx(0.05 / 24.0)
    assert plan.quality_noninferiority_margin == pytest.approx(0.02)
    assert plan.catastrophic_regret_noninferiority_margin == pytest.approx(0.01)
    assert plan.minimum_cost_effect_of_interest == pytest.approx(0.05)
    assert plan.calibration_fraction == pytest.approx(0.20)
    assert plan.generalization_holdout_fraction == pytest.approx(0.20)
    assert plan.primary_inference_method == PRIMARY_INFERENCE_METHOD
    assert plan.primary_claim_target == PRIMARY_CLAIM_TARGET
    assert plan.primary_assumption_boundary == PRIMARY_ASSUMPTION_BOUNDARY
    assert plan.primary_sequence_order == PRIMARY_SEQUENCE_ORDER
    assert plan.method == PLAN_METHOD


def test_plan_digest_is_deterministic_and_changes_with_scientific_identity_or_margin():
    a = ProductStatisticalPlan()
    b = ProductStatisticalPlan()
    c = ProductStatisticalPlan(quality_noninferiority_margin=0.03)
    d = ProductStatisticalPlan(generalization_holdout_fraction=0.15)
    assert a.digest == b.digest
    assert a.digest != c.digest
    assert a.digest != d.digest
    with pytest.raises(ValueError, match="theorem identity"):
        ProductStatisticalPlan(primary_inference_method="LEGACY")
    with pytest.raises(ValueError, match="estimand"):
        ProductStatisticalPlan(primary_claim_target="UNIVERSAL_MEAN")
    with pytest.raises(ValueError, match="assumption boundary"):
        ProductStatisticalPlan(primary_assumption_boundary="IID")
    with pytest.raises(ValueError, match="analysis order"):
        ProductStatisticalPlan(primary_sequence_order="OUTCOME_SORTED")
    with pytest.raises(ValueError, match="plan identity"):
        ProductStatisticalPlan(method="V3")


def test_three_way_split_is_deterministic_disjoint_complete_and_reserves_g1():
    tasks = [f"task-{i:03d}" for i in range(100)]
    cal_a, conf_a, g1_a = deterministic_three_way_task_split(
        tasks,
        calibration_fraction=0.20,
        generalization_holdout_fraction=0.20,
    )
    cal_b, conf_b, g1_b = deterministic_three_way_task_split(
        reversed(tasks),
        calibration_fraction=0.20,
        generalization_holdout_fraction=0.20,
    )
    assert (cal_a, conf_a, g1_a) == (cal_b, conf_b, g1_b)
    assert len(cal_a) == 20
    assert len(g1_a) == 20
    assert len(conf_a) == 60
    assert not (set(cal_a) & set(conf_a))
    assert not (set(cal_a) & set(g1_a))
    assert not (set(conf_a) & set(g1_a))
    assert set(cal_a) | set(conf_a) | set(g1_a) == set(tasks)


def test_three_way_split_requires_nontrivial_population():
    with pytest.raises(ValueError):
        deterministic_three_way_task_split([f"t{i}" for i in range(9)])


def test_legacy_two_way_split_is_retained_but_not_product_authorized():
    tasks = [f"task-{i:03d}" for i in range(100)]
    cal, conf = deterministic_task_split(tasks, calibration_fraction=0.20)
    assert len(cal) == 20 and len(conf) == 80
    assert not (set(cal) & set(conf))


def test_cluster_aware_sizing_respects_minimum_floor_when_variance_small():
    plan = ProductStatisticalPlan()
    sizing = cluster_aware_required_trials_per_task(
        between_task_std=0.01,
        within_task_std=0.01,
        effect_of_interest=0.10,
        confirmatory_task_count=300,
        plan=plan,
    )
    assert sizing.required_trials_per_task == plan.min_trials_per_task
    assert sizing.achieved_standard_error_at_required_trials <= sizing.target_standard_error
    assert sizing.method.endswith("PLANNING_ONLY")


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
        ProductStatisticalPlan(generalization_holdout_fraction=0.5)
    with pytest.raises(ValueError):
        ProductStatisticalPlan(calibration_fraction=0.30, generalization_holdout_fraction=0.20)
    with pytest.raises(ValueError):
        ProductStatisticalPlan(min_trials_per_task=10, max_trials_per_task=5)