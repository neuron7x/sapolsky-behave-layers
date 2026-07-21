"""Tests for WP7 certificate hardening."""
from __future__ import annotations

import pytest

from experiments.wp7_certificate_hardening.src import hardening as H


@pytest.fixture(scope="module")
def result():
    return H.analyze()


def test_verdict_gap_closed(result):
    assert result["verdict"] == "WP7_GAP_CLOSED_POSITIVES_ROBUST"


def test_corrected_bound_fpr_within_delta(result):
    assert result["corrected_bound_valid_all_nulls"] is True
    for c in result["coverage_montecarlo"]:
        assert c["fpr_corrected"] <= result["mc_delta"]


def test_positives_survive_corrected(result):
    assert result["all_positives_survive_corrected"] is True
    for p in result["positives_recertified"].values():
        assert p["g_lo_corrected"] > 0.0
        assert p["g_lo_corrected"] <= p["g_lo_original"]   # strictly more conservative
