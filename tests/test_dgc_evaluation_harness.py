import pytest

from cwc.governance.evaluation_harness import (
    FrozenEvaluationHarness,
    certify_controlled_comparison,
)


def _harness(policy: str, *, tasks="tasks", scorer="scorer") -> FrozenEvaluationHarness:
    return FrozenEvaluationHarness(
        model_manifest_digest="models",
        prompt_policy_digest="prompt",
        tool_manifest_digest="tools",
        task_manifest_digest=tasks,
        environment_digest="env",
        budget_digest="budget",
        pricing_snapshot_digest="pricing",
        scorer_digest=scorer,
        statistical_plan_digest="stats",
        baseline_panel_digest="baselines",
        governance_policy_digest=policy,
    )


def test_only_governance_policy_may_differ():
    baseline = _harness("B1")
    dgc = _harness("DGC")
    assert certify_controlled_comparison(baseline, dgc) == baseline.comparison_frame_digest


def test_task_population_drift_invalidates_comparison():
    with pytest.raises(ValueError):
        certify_controlled_comparison(_harness("B1", tasks="t1"), _harness("DGC", tasks="t2"))


def test_scorer_drift_invalidates_comparison():
    with pytest.raises(ValueError):
        certify_controlled_comparison(_harness("B1", scorer="s1"), _harness("DGC", scorer="s2"))


def test_identical_policy_is_not_policy_comparison():
    with pytest.raises(ValueError):
        certify_controlled_comparison(_harness("same"), _harness("same"))


def test_missing_digest_fails_closed():
    with pytest.raises(ValueError):
        FrozenEvaluationHarness("", "p", "t", "tasks", "e", "b", "price", "s", "stats", "panel", "dgc")
