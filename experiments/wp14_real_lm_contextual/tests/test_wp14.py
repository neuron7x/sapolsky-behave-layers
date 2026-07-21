"""Tests for WP14 real-LM boundary robustness (contextual difficulty)."""
from __future__ import annotations

from experiments.wp14_real_lm_contextual.src import analyze as A


def test_verdict_not_identifiable_robust():
    r = A.analyze()
    assert r["verdict"] == "WP14_REAL_LM_NOT_IDENTIFIABLE_ROBUST"


def test_real_lm_gap_negative_at_every_lambda(r=None):
    r = A.analyze()
    for lam in A.LAMBDAS:
        assert r["real_lm_g_lo"][str(lam)] <= 0.0


def test_positive_control_detects_synthetic_gap():
    r = A.analyze()
    assert r["positive_control_synthetic_ac1"] > 0.0
