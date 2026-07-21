"""Tests for WP15 compute-equivalent Pareto (synthetic L7 precursor)."""
from __future__ import annotations

from experiments.wp15_compute_pareto.src import pareto as P


def test_verdict_pareto_dominates():
    r = P.analyze()
    assert r["verdict"] == "SYNTHETIC_COMPUTE_PARETO_DOMINATES"
    assert r["pareto_dominates"] is True


def test_adaptive_dominates_at_matched_compute():
    r = P.analyze()
    assert r["adaptive_advantage_at_matched_compute"] > 0.05
    # every fixed policy at >= adaptive's compute is no better than adaptive
    a = r["adaptive_oracle"]
    for f in r["fixed_frontier"]:
        if f["avg_compute"] >= a["avg_compute"]:
            assert a["accuracy"] >= f["accuracy"] - 1e-9


def test_distinct_from_identifiability():
    # a Pareto-frontier claim, not a certificate gap: fixed policies are near chance at every compute
    r = P.analyze()
    assert all(f["accuracy"] < 0.5 for f in r["fixed_frontier"])
    assert r["adaptive_oracle"]["accuracy"] > 0.9
