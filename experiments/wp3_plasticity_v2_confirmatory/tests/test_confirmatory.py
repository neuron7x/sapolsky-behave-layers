"""Tests for the L4 plasticity cost-budget confirmatory analysis.

Assert the preregistered decision on the committed held-out raw runs, and that the
instrument can fail (controls) and actually debiases.
"""
from __future__ import annotations

import math

from experiments.wp3_plasticity_v2_confirmatory.src import analyze as A

SEEDS = list(range(5, 21))


def _r():
    return A.analyze(SEEDS)


def test_verdict_confirmed_and_deterministic():
    r1, r2 = _r(), _r()
    assert r1 == r2
    assert r1["verdict"] == "L4_IDENTIFIABLE_CONFIRMED_SYNTHETIC"
    assert r1["n_seeds"] == 16
    assert r1["lambda_frozen"] == 1.0


def test_certificate_debiases_and_stays_positive():
    p = _r()["primary"]
    assert p["gap_lower_bound"] < p["gap_hat"]          # debiasing subtracts
    assert p["gap_lower_bound"] > 0.0                    # still certifies
    assert math.isclose(p["gap_hat"], 0.1909, abs_tol=6e-3)


def test_effect_in_every_held_out_seed():
    r = _r()
    assert r["fraction_seeds_positive"] == 1.0
    assert r["worst_seed_gap"] > 0.0
    assert len(r["per_seed_gaps"]) == 16


def test_controls_behave():
    c = _r()["controls"]
    assert c["negative_A"]["identifiable"] is False
    assert c["negative_B"]["identifiable"] is False
    assert c["positive"]["identifiable"] is True
    assert c["controls_ok"] is True


def test_no_selection_correction_delta_is_direct():
    # lambda frozen a priori => delta applied directly at 0.05 (no Bonferroni here).
    assert _r()["delta"] == 0.05


def test_certificate_self_falsification():
    assert _r()["certificate_self_falsification"]["all_ok"] is True
