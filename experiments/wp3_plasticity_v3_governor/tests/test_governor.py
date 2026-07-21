"""Tests for the L4a learned-governor study.

Assert the preregistered decision AND that the instrument can fail: the NULL falsifier
must return ~0 recovery, and the random baseline must trail the best fixed arm.
"""
from __future__ import annotations

from experiments.wp3_plasticity_v3_governor.src import governor as G


def _r():
    return G.run()


def test_verdict_supported_and_deterministic():
    r1, r2 = _r(), _r()
    assert r1 == r2  # deterministic PRNG
    assert r1["verdict"] == "L4A_SUPPORTED"


def test_learned_recovers_gap_out_of_sample():
    real = _r()["real"]
    assert real["learned_beats_fixed_worst"] is True
    assert real["worst_recovery"] >= 0.80
    assert real["worst_learned"] > real["best_fixed"] > real["random"]


def test_null_falsifier_reports_no_gap():
    r = _r()
    # collapsed benchmark: a working governor+metric must NOT manufacture a gap
    assert r["null_falsifier"]["worst_recovery"] <= 0.10


def test_baselines_ordered():
    real = _r()["real"]
    assert real["random_below_fixed"] is True
    assert real["oracle"] >= real["best_fixed"]


def test_reward_only_every_controller_seed_recovers():
    # robustness: the WORST of 8 independent inits still clears threshold
    real = _r()["real"]
    assert len(real["learned_per_seed"]) == 8
    assert min(real["learned_per_seed"]) > real["best_fixed"]
