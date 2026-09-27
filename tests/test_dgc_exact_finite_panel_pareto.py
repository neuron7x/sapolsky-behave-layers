from __future__ import annotations

import pytest

from cwc.governance.exact_finite_panel_pareto import certify_exact_finite_panel
from cwc.governance.pareto import PairedBaselineEvidence


def row(baseline_id: str, *, cost=(0.1, 0.2), quality=(0.0, -0.01), catastrophic=(0.0, 0.0), coverage=1.0):
    return PairedBaselineEvidence(
        baseline_id=baseline_id,
        paired_task_digest="a" * 64,
        coverage=coverage,
        baseline_minus_dgc_cost=tuple(cost),
        dgc_minus_baseline_quality=tuple(quality),
        baseline_minus_dgc_catastrophic_regret=tuple(catastrophic),
        cost_gain_support=(-1.0, 1.0),
        quality_gain_support=(-1.0, 1.0),
        catastrophic_gain_support=(-1.0, 1.0),
    )


def test_exact_panel_pass_has_no_probability_semantics():
    cert = certify_exact_finite_panel(
        tuple(row(f"B{i}") for i in range(4)),
        quality_noninferiority_margin=0.02,
        catastrophic_noninferiority_margin=0.01,
    )
    assert cert.all_baselines_observed is True
    assert all(result.n == 2 for result in cert.results)
    assert all(result.mean_cost_gain == pytest.approx(0.15) for result in cert.results)


def test_exact_panel_rejects_quality_margin_violation():
    cert = certify_exact_finite_panel(
        (row("B0", quality=(-0.03, -0.03)),),
        quality_noninferiority_margin=0.02,
        catastrophic_noninferiority_margin=0.01,
    )
    assert cert.all_baselines_observed is False
    assert cert.results[0].quality_noninferiority_observed is False


def test_exact_panel_rejects_partial_coverage():
    with pytest.raises(ValueError, match="full paired coverage"):
        certify_exact_finite_panel(
            (row("B0", coverage=0.99),),
            quality_noninferiority_margin=0.02,
            catastrophic_noninferiority_margin=0.01,
        )


def test_exact_panel_rejects_out_of_support_value():
    with pytest.raises(ValueError, match="outside declared support"):
        certify_exact_finite_panel(
            (row("B0", cost=(2.0, 2.0)),),
            quality_noninferiority_margin=0.02,
            catastrophic_noninferiority_margin=0.01,
        )
