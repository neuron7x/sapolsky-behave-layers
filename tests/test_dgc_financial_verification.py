from __future__ import annotations

from experiments.dgc_02_finance.analysis import evaluate_financial_gate
from experiments.dgc_02_finance.run import run


def test_financial_gate_rejects_large_overhead() -> None:
    result = evaluate_financial_gate(
        reference_costs=[0.1] * 2000, dgc_core_costs=[0.05] * 2000,
        reference_losses=[0.0] * 2000, dgc_losses=[0.0] * 2000,
        governance_overhead_per_task=0.03, max_reference_cost=0.1, max_dgc_core_cost=0.05,
    )
    assert abs(result.net_inference_savings - 0.2) < 1e-12
    assert not result.threshold_met


def test_quality_degradation_blocks_savings_claim() -> None:
    result = evaluate_financial_gate(
        reference_costs=[0.1] * 5000, dgc_core_costs=[0.01] * 5000,
        reference_losses=[0.0] * 5000, dgc_losses=[0.1] * 5000,
        governance_overhead_per_task=0.0, max_reference_cost=0.1,
        max_dgc_core_cost=0.01, max_loss=0.1,
    )
    assert result.net_inference_savings > 0.8
    assert result.quality_lcb < 0
    assert not result.threshold_met


def test_development_financial_threshold_is_non_promoting() -> None:
    result = run(per_regime=2000, seed_offset=0)
    primary = result["zero_unmetered_overhead_ceiling"]
    assert result["commercial_claim_allowed"] is False
    assert result["claim_promotion"] == "PROHIBITED"
    assert result["development_threshold_status"] == "DEVELOPMENT_THRESHOLD_MET"
    assert primary["net_inference_savings"] > 0.30
    assert primary["savings_lcb"] > 0.30
    assert primary["quality_lcb"] >= 0.0
    assert primary["max_mean_overhead_for_threshold"] > 0.0


def test_overhead_sweep_must_eventually_fail_30pct_gate() -> None:
    result = run(per_regime=1000, seed_offset=17)
    statuses = [row["threshold_met"] for row in result["overhead_sensitivity"]]
    assert statuses[0] is True
    assert False in statuses


def test_value_based_pricing_is_fail_closed_before_client_verification() -> None:
    from experiments.dgc_02_finance.economics import value_based_case
    try:
        value_based_case(
            decision_volume=1_000_000, baseline_cost_per_decision=0.01,
            dgc_cost_per_decision=0.006, contractual_share=0.2,
            client_verified=False, quality_gate_passed=True,
        )
    except RuntimeError as exc:
        assert str(exc) == "COMMERCIAL_PRICING_NOT_AUTHORIZED"
    else:
        raise AssertionError("unverified client savings must not be monetized")


def test_synthetic_financial_theorem_matches_frozen_workload_algebra() -> None:
    from experiments.dgc_02_finance.analytic import synthetic_financial_theorem, savings_with_mean_overhead
    t = synthetic_financial_theorem()
    assert abs(t.reference_expected_cost - 0.0785) < 1e-15
    assert abs(t.dgc_core_expected_cost - 0.0385) < 1e-15
    assert abs(t.core_savings - (1 - 0.0385 / 0.0785)) < 1e-15
    assert abs(t.max_overhead_for_threshold - 0.01645) < 1e-15
    assert t.quality_delta == 0.0
    assert savings_with_mean_overhead(0.01645) >= 0.30 - 1e-15
    assert savings_with_mean_overhead(0.016451) < 0.30


def test_provider_rate_card_prices_cached_and_uncached_tokens_separately() -> None:
    from cwc.governance.cost_accounting import ProviderRateCard
    card = ProviderRateCard(
        provider="example", model="m", input_usd_per_million=2.0,
        cached_input_usd_per_million=0.2, output_usd_per_million=10.0,
        source_uri="https://example.invalid/rates", retrieved_at="2026-08-22T00:00:00Z",
    )
    cost = card.token_cost_usd(input_tokens=1000, cached_input_tokens=500, output_tokens=100)
    assert abs(cost - 0.0021) < 1e-12
