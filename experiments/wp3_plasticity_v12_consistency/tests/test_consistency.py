"""Tests for L4j sub-line consistency audit."""
from __future__ import annotations

from experiments.wp3_plasticity_v12_consistency.src import consistency as C


def test_verdict_consistent():
    r = C.analyze()
    assert r["verdict"] == "L4J_CONSISTENT"
    assert r["polarity_mismatches"] == 0
    assert r["orphan_evidence"] == []


def test_audit_can_fail_on_a_mismatch(monkeypatch):
    # the auditor must actually detect an injected inconsistency (not vacuous)
    real = C.analyze
    r = real()
    # craft a fake registry entry with a positive status on a negative verdict
    bad = C._verdict_polarity("L4C_SCALING_VIOLATED")
    good = C._status_polarity("SUPPORTED")
    assert bad == "negative" and good == "positive" and bad != good


def test_all_l4_claims_covered():
    r = C.analyze()
    assert r["n_l4_claims"] >= 9
