from __future__ import annotations

import math
import pytest

from cwc.causal.opportunity import (
    QualityComputeOutcome,
    capture_fraction,
    critical_lambdas,
    opportunity_at_lambda,
    summarize_opportunity,
    validate_quality_compute_replay,
)


def _rows() -> list[QualityComputeOutcome]:
    # Two regimes. Short and full are tied on local dependencies; full alone can
    # resolve long dependencies, but costs four times more resource.
    rows: list[QualityComputeOutcome] = []
    for i in range(4):
        regime = "local" if i < 2 else "long"
        q_short = 1.0 if regime == "local" else 0.5
        rows.extend([
            QualityComputeOutcome(f"u{i}", regime, "short", q_short, 2.0),
            QualityComputeOutcome(f"u{i}", regime, "full", 1.0, 8.0),
        ])
    return rows


def test_replay_contract_rejects_missing_action() -> None:
    rows = _rows()[:-1]
    with pytest.raises(ValueError, match="not exhaustive"):
        validate_quality_compute_replay(rows)


def test_information_order_fixed_le_regime_le_instance() -> None:
    rows = _rows()
    for lam in (0.0, 0.01, 0.04, 0.08, 0.2):
        p = opportunity_at_lambda(rows, lambda_compute=lam)
        assert p.fixed_value <= p.regime_oracle_value + 1e-12
        assert p.regime_oracle_value <= p.instance_oracle_value + 1e-12
        assert p.regime_gap <= p.instance_gap + 1e-12


def test_attention_horizon_has_nonzero_cost_sensitive_opportunity() -> None:
    p = opportunity_at_lambda(_rows(), lambda_compute=0.04)
    assert p.regime_gap == pytest.approx(0.12)
    assert p.instance_gap == pytest.approx(0.12)


def test_controller_cost_is_charged_in_compute_units() -> None:
    rows = _rows()
    p = opportunity_at_lambda(rows, lambda_compute=0.04, controller_compute=3.0)
    assert p.regime_gap == pytest.approx(0.12)
    assert p.regime_net_gap == pytest.approx(0.0, abs=1e-12)


def test_critical_lambdas_include_regime_and_fixed_policy_crossings() -> None:
    crit = critical_lambdas(_rows())
    # long-regime short/full crossing: (.5-1)/(2-8) = 1/12
    assert any(math.isclose(x, 1 / 12, rel_tol=0.0, abs_tol=1e-12) for x in crit)
    # global fixed short/full crossing: (.75-1)/(2-8) = 1/24
    assert any(math.isclose(x, 1 / 24, rel_tol=0.0, abs_tol=1e-12) for x in crit)


def test_summary_finds_exact_region_without_grid_search() -> None:
    s = summarize_opportunity(_rows())
    assert s.positive_regime_interval_found is True
    assert s.max_regime_gap > 0.0
    assert s.max_controller_compute_allowance == pytest.approx(3.0)


def test_capture_fraction_is_fail_closed() -> None:
    assert capture_fraction(0.2, 0.5) == pytest.approx(0.4)
    assert capture_fraction(0.0, 0.0) is None
    with pytest.raises(ValueError, match="cannot exceed"):
        capture_fraction(0.6, 0.5)
