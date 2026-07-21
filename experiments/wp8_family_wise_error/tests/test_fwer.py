"""Tests for WP8 family-wise error meta-audit."""
from __future__ import annotations

import pytest

from experiments.wp8_family_wise_error.src import fwer as F


@pytest.fixture(scope="module")
def result():
    return F.analyze()


def test_verdict_fwer_controlled(result):
    assert result["verdict"] == "WP8_FWER_CONTROLLED"


def test_positives_survive_bonferroni_family(result):
    assert result["bonferroni_family_all_survive"] is True
    for row in result["per_member"].values():
        assert row["bonferroni_family"]["g_lo_corrected"] > 0.0


def test_positives_survive_ultra_conservative_all_claims(result):
    # worst case: all 29 claims as one family
    assert result["bonferroni_all_claims_all_survive"] is True
    for row in result["per_member"].values():
        assert row["bonferroni_all_claims"]["g_lo_corrected"] > 0.0


def test_holm_and_monotone_conservatism(result):
    assert result["holm_all_survive"] is True
    for row in result["per_member"].values():
        # more correction -> smaller bound
        assert row["bonferroni_all_claims"]["g_lo_corrected"] <= row["uncorrected"]["g_lo_corrected"]
