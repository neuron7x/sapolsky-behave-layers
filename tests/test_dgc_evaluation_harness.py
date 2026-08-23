import hashlib
import pytest

from cwc.governance.evaluation_harness import (
    FrozenEvaluationHarness,
    canonical_manifest_digest,
    certify_controlled_comparison,
)


def _h(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _harness(policy: str, *, tasks="tasks", scorer="scorer") -> FrozenEvaluationHarness:
    return FrozenEvaluationHarness(
        model_manifest_digest=_h("models"),
        prompt_policy_digest=_h("prompt"),
        tool_manifest_digest=_h("tools"),
        task_manifest_digest=_h(tasks),
        environment_digest=_h("env"),
        budget_digest=_h("budget"),
        pricing_snapshot_digest=_h("pricing"),
        scorer_digest=_h(scorer),
        statistical_plan_digest=_h("stats"),
        baseline_panel_digest=_h("baselines"),
        governance_policy_digest=_h(policy),
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


def test_semantic_label_cannot_masquerade_as_digest():
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        FrozenEvaluationHarness("models", *(_h(str(i)) for i in range(10)))


def test_canonical_manifest_digest_is_order_independent_for_mapping_keys():
    assert canonical_manifest_digest({"a": 1, "b": 2}) == canonical_manifest_digest({"b": 2, "a": 1})
    assert len(canonical_manifest_digest({"artifact": "x"})) == 64
