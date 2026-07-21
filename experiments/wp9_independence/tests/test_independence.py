"""Tests for WP9 independence-assumption robustness."""
from __future__ import annotations

from experiments.wp9_independence.src import independence as I


def test_verdict_independence_robust():
    r = I.analyze()
    assert r["verdict"] == "INDEPENDENCE_ROBUST"
    assert r["independence_robust"] is True


def test_fpr_within_delta_under_strong_correlation():
    r = I.analyze()
    assert r["max_fpr_over_all"] <= r["mc_delta"]
    for row in r["fpr_grid"]:
        assert row["rho_0.9"] <= r["mc_delta"]   # holds even at rho=0.9
