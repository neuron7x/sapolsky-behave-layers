"""Tests for the L4b inferred-context boundary.

Assert the preregistered boundary is mapped AND that the instrument can fail: zero
information must yield ~0 recovery (no manufactured gap), and the curve must be monotone.
"""
from __future__ import annotations

from experiments.wp3_plasticity_v4_inferred.src import inferred as I


def _r():
    return I.analyze()


def test_verdict_boundary_mapped_and_deterministic():
    r1, r2 = _r(), _r()
    assert r1 == r2
    assert r1["verdict"] == "L4B_BOUNDARY_MAPPED"


def test_full_information_reproduces_l4a():
    assert _r()["recovery_at_full_info"] >= 0.9


def test_zero_information_realises_no_gap():
    # the falsifier: with I(C;Z)=0 the governor must NOT manufacture a gap
    assert _r()["recovery_at_zero_info"] <= 0.10


def test_recovery_monotone_in_information():
    assert _r()["monotone_in_information"] is True


def test_tracks_grounded_prediction():
    # measured recovery must match the theory curve (not fit) for p <= 0.3
    r = _r()
    for s in r["sweep"]:
        if s["flip_p"] <= 0.3:
            assert abs(s["recovery_mean"] - s["predicted_commit_recovery"]) <= 0.15


def test_governor_abstains_at_zero_information():
    # at p=0.5 the rational move is to ignore the useless observation
    r = _r()
    assert r["sweep"][-1]["flip_p"] == 0.5
    assert r["sweep"][-1]["abstain_fraction"] >= 0.5
