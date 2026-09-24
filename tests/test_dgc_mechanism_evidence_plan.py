from __future__ import annotations

import pytest

from cwc.governance.mechanism_evidence_plan import (
    MechanismStatisticalPlan,
    PairedMechanismEvidence,
    certify_multi_baseline_mechanism_pareto,
)


def _rows(*, quality: float = 0.5, coverage: float = 1.0):
    return tuple(
        PairedMechanismEvidence(
            baseline_id=f"B{i}",
            paired_task_digest="a" * 64,
            coverage=coverage,
            baseline_minus_dgc_cost=(1.0,) * 500,
            dgc_minus_baseline_quality=(quality,) * 500,
            cost_gain_support=(-1.0, 1.0),
            quality_gain_support=(-1.0, 1.0),
        )
        for i in range(4)
    )


def test_mechanism_plan_is_two_endpoint_and_cannot_promote_product():
    plan = MechanismStatisticalPlan()
    assert plan.endpoint_count == 2
    assert plan.per_claim_alpha == pytest.approx(0.003125)
    assert plan.risk_qualification_required_for_product is True
    assert plan.product_promotion_authorized is False


def test_mechanism_certificate_requires_all_four_baselines():
    with pytest.raises(ValueError, match="exactly four"):
        certify_multi_baseline_mechanism_pareto(
            _rows()[:3],
            alpha=0.025,
            quality_noninferiority_margin=0.02,
        )


def test_mechanism_certificate_uses_two_endpoint_bonferroni():
    cert = certify_multi_baseline_mechanism_pareto(
        _rows(),
        alpha=0.025,
        quality_noninferiority_margin=0.02,
    )
    assert cert.per_metric_delta == pytest.approx(0.025 / 8.0)
    assert cert.all_baselines_certified is True
    assert cert.risk_qualification_required_for_product is True
    assert cert.product_promotion_authorized is False


def test_quality_failure_blocks_mechanism_support():
    cert = certify_multi_baseline_mechanism_pareto(
        _rows(quality=-1.0),
        alpha=0.025,
        quality_noninferiority_margin=0.02,
    )
    assert cert.all_baselines_certified is False
    assert all(not row.certified_quality_noninferiority for row in cert.results)


def test_selective_coverage_is_rejected():
    with pytest.raises(ValueError, match="full matched coverage"):
        _rows(coverage=0.99)


def test_task_population_substitution_is_rejected():
    rows = list(_rows())
    rows[-1] = PairedMechanismEvidence(
        baseline_id="B3",
        paired_task_digest="b" * 64,
        coverage=1.0,
        baseline_minus_dgc_cost=(1.0,) * 500,
        dgc_minus_baseline_quality=(0.5,) * 500,
        cost_gain_support=(-1.0, 1.0),
        quality_gain_support=(-1.0, 1.0),
    )
    with pytest.raises(ValueError, match="same paired task population"):
        certify_multi_baseline_mechanism_pareto(
            rows,
            alpha=0.025,
            quality_noninferiority_margin=0.02,
        )
