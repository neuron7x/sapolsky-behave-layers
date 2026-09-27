import pytest

from cwc.governance.deployment_qualification import (
    CanaryLimits,
    ShadowQualificationPlan,
    authorize_bounded_canary,
    qualify_shadow_mode,
)
from cwc.governance.product_evidence import ProductEvidenceRecord


def _evidence(product_qualified: bool) -> ProductEvidenceRecord:
    common = dict(
        claim_frozen=True,
        metrics_frozen=True,
        baselines_frozen=product_qualified,
        harness_frozen=product_qualified,
        statistical_plan_frozen=True,
        synthetic_mechanism_supported=True,
        external_real_workload_supported=product_qualified,
        quality_noninferiority_supported=product_qualified,
        catastrophic_regret_noninferiority_supported=product_qualified,
        coverage_equivalence_supported=product_qualified,
        physical_cost_accounting_verified=product_qualified,
        net_cost_superiority_supported=product_qualified,
        generalization_supported=product_qualified,
        fault_tolerance_supported=product_qualified,
        independent_replication_supported=product_qualified,
        evidence_bundle_complete=product_qualified,
    )
    return ProductEvidenceRecord(**common)


def _plan() -> ShadowQualificationPlan:
    return ShadowQualificationPlan(
        min_trials=100,
        min_coverage=0.99,
        max_false_stop_rate=0.02,
        max_mean_regret=0.01,
        max_p95_latency_overhead_ms=100.0,
        plan_authority_digest="shadow-plan-v1",
    )


def test_shadow_mode_rejects_any_dgc_control_authority():
    with pytest.raises(ValueError):
        qualify_shadow_mode(
            plan=_plan(),
            trials=100,
            coverage=1.0,
            false_stop_rate=0.0,
            mean_regret=0.0,
            p95_latency_overhead_ms=1.0,
            baseline_action_authority_digest="baseline",
            outcome_scorer_digest="scorer",
            dgc_had_control_authority=True,
        )


def test_shadow_qualification_requires_all_preregistered_thresholds():
    result = qualify_shadow_mode(
        plan=_plan(),
        trials=100,
        coverage=1.0,
        false_stop_rate=0.01,
        mean_regret=0.005,
        p95_latency_overhead_ms=50.0,
        baseline_action_authority_digest="baseline",
        outcome_scorer_digest="scorer",
        dgc_had_control_authority=False,
    )
    assert result.qualified
    bad = qualify_shadow_mode(
        plan=_plan(),
        trials=100,
        coverage=1.0,
        false_stop_rate=0.03,
        mean_regret=0.005,
        p95_latency_overhead_ms=50.0,
        baseline_action_authority_digest="baseline",
        outcome_scorer_digest="scorer",
        dgc_had_control_authority=False,
    )
    assert not bad.qualified


def test_canary_limits_require_small_traffic_and_rollback_fallback():
    with pytest.raises(ValueError):
        CanaryLimits(0.2, 1, 2, 2, 1000, 1, True, "rollback")
    with pytest.raises(ValueError):
        CanaryLimits(0.05, 1, 2, 2, 1000, 1, False, "rollback")


def test_canary_is_prohibited_before_product_qualification():
    shadow = qualify_shadow_mode(
        plan=_plan(), trials=100, coverage=1.0, false_stop_rate=0.0,
        mean_regret=0.0, p95_latency_overhead_ms=1.0,
        baseline_action_authority_digest="baseline", outcome_scorer_digest="scorer",
        dgc_had_control_authority=False,
    )
    limits = CanaryLimits(0.05, 1, 2, 2, 1000, 1, True, "rollback")
    with pytest.raises(RuntimeError):
        authorize_bounded_canary(evidence=_evidence(False), shadow=shadow, limits=limits)


def test_canary_requires_shadow_qualification_even_after_product_qualification():
    shadow = qualify_shadow_mode(
        plan=_plan(), trials=10, coverage=1.0, false_stop_rate=0.0,
        mean_regret=0.0, p95_latency_overhead_ms=1.0,
        baseline_action_authority_digest="baseline", outcome_scorer_digest="scorer",
        dgc_had_control_authority=False,
    )
    limits = CanaryLimits(0.05, 1, 2, 2, 1000, 1, True, "rollback")
    with pytest.raises(RuntimeError):
        authorize_bounded_canary(evidence=_evidence(True), shadow=shadow, limits=limits)
