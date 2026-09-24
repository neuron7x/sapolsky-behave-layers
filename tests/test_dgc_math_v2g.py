from __future__ import annotations

import pytest

from cwc.governance.adaptive_eprocess import AdaptiveImportanceSample
from cwc.governance.pareto import PairedBaselineEvidence, certify_multi_baseline_pareto_improvement
from cwc.governance.restricted_sampling import certify_restricted_adaptive_policy
from cwc.governance.sequential_risk_control import certify_anytime_adaptive_risk


def _baseline(name: str, *, task_digest: str = "tasks", coverage: float = 1.0, quality: float = 0.25, catastrophic: float = 0.0) -> PairedBaselineEvidence:
    n=200
    return PairedBaselineEvidence(
        baseline_id=name,
        paired_task_digest=task_digest,
        coverage=coverage,
        baseline_minus_dgc_cost=(0.4,)*n,
        dgc_minus_baseline_quality=(quality,)*n,
        baseline_minus_dgc_catastrophic_regret=(catastrophic,)*n,
        cost_gain_support=(0.4,0.4),
        quality_gain_support=(quality,quality),
        catastrophic_gain_support=(catastrophic,catastrophic),
    )


def test_multi_baseline_pareto_certifies_all_three_metrics_simultaneously():
    cert=certify_multi_baseline_pareto_improvement([_baseline("fixed"),_baseline("router"),_baseline("strong")],alpha=.05)
    assert cert.all_baselines_certified
    assert cert.per_metric_delta == pytest.approx(.05/9)
    assert all(r.certified_cost_reduction and r.certified_quality_noninferiority and r.certified_catastrophic_noninferiority for r in cert.results)


def test_multi_baseline_pareto_rejects_selective_coverage_and_population_mismatch():
    with pytest.raises(ValueError): certify_multi_baseline_pareto_improvement([_baseline("a"),_baseline("b",coverage=.99)])
    with pytest.raises(ValueError): certify_multi_baseline_pareto_improvement([_baseline("a"),_baseline("b",task_digest="other")])


def test_multi_baseline_pareto_fails_if_any_strong_baseline_breaks_quality():
    cert=certify_multi_baseline_pareto_improvement([_baseline("a"),_baseline("bad",quality=-.2)],quality_noninferiority_margin=.0)
    assert not cert.all_baselines_certified
    bad=next(r for r in cert.results if r.baseline_id=="bad")
    assert not bad.certified_quality_noninferiority


def _risk_fixture(loss: float, n: int = 100):
    policy=certify_restricted_adaptive_policy(target_distribution={"a":.5,"b":.5},minimum_propensity=.5)
    samples=tuple(AdaptiveImportanceSample("a" if i%2==0 else "b",loss,.5) for i in range(n))
    return policy,samples


def test_anytime_adaptive_risk_certifies_low_risk_under_restricted_policy():
    policy,samples=_risk_fixture(0.0)
    cert=certify_anytime_adaptive_risk(samples,sampling_policy=policy,sampling_trace_digest="trace",risk_threshold=.2,alpha=.05,predictable_lambdas=(.5,)*len(samples),predictable_lambda_attested=True)
    assert cert.certified_risk_control and cert.risk_upper_confidence_bound <= .2


def test_anytime_adaptive_risk_does_not_certify_high_risk():
    policy,samples=_risk_fixture(.5)
    cert=certify_anytime_adaptive_risk(samples,sampling_policy=policy,sampling_trace_digest="trace",risk_threshold=.2,alpha=.05,predictable_lambdas=(.5,)*len(samples),predictable_lambda_attested=True)
    assert not cert.certified_risk_control


def test_anytime_adaptive_risk_requires_predictable_lambda_and_trace():
    policy,samples=_risk_fixture(0.0,10)
    with pytest.raises(ValueError): certify_anytime_adaptive_risk(samples,sampling_policy=policy,sampling_trace_digest="trace",risk_threshold=.2,alpha=.05,predictable_lambdas=(.5,)*10,predictable_lambda_attested=False)
    with pytest.raises(ValueError): certify_anytime_adaptive_risk(samples,sampling_policy=policy,sampling_trace_digest="",risk_threshold=.2,alpha=.05,predictable_lambdas=(.5,)*10,predictable_lambda_attested=True)
