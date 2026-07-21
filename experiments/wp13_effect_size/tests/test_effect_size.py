"""Tests for WP13 effect sizes / bootstrap CIs."""
from __future__ import annotations

from experiments.wp13_effect_size.src import effect_size as E


def test_verdict_ci_positive():
    r = E.analyze()
    assert r["verdict"] == "EFFECT_SIZES_CI_POSITIVE"
    assert r["all_bootstrap_ci_lower_positive"] is True


def test_each_positive_ci_lower_above_zero_and_powered():
    r = E.analyze()
    for m in r["members"]:
        assert m["bootstrap_ci95"][0] > 0.0
        assert m["ci_lower_positive"] is True
        assert m["n_exceeds_nstar"] is True
