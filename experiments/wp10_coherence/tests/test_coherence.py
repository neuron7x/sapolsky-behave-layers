"""Tests for WP10 de-circularized coherence audit."""
from __future__ import annotations

from experiments.wp10_coherence.src import coherence as C


def test_zero_contradictions():
    r = C.analyze()
    assert r["verdict"] == "COHERENCE_DECIRCULARIZED_0_CONTRADICTIONS"
    assert r["contradictions"] == 0


def test_both_directions_present_and_agree():
    r = C.analyze()
    signs = {c["expected_sign"] for c in r["checks"]}
    assert {"positive", "negative"} <= signs      # a real negative is checked, not just positives
    for c in r["checks"]:
        assert c["agrees"] is True
        assert c["status_positive"] == (c["g_lo_from_real_artifact"] > 0.0)
