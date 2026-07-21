"""Tests for L4h context-scaling generalization."""
from __future__ import annotations

import pytest

from experiments.wp3_plasticity_v10_contexts.src import contexts as C


@pytest.fixture(scope="module")
def result():
    return C.analyze()


def test_verdict_generalizes(result):
    assert result["verdict"] == "L4H_GENERALIZES"


def test_identifiable_at_every_context_count(result):
    for nc in C.CONTEXTS:
        p = result["per_context_count"][str(nc)]
        assert p["identifiable"] is True
        assert p["gap_lower_bound"] > 0.0


def test_governor_recovers_at_every_context_count(result):
    for nc in C.CONTEXTS:
        assert result["per_context_count"][str(nc)]["worst_governor_recovery"] >= 0.8


def test_identifiability_strengthens_with_contexts(result):
    glo = [result["per_context_count"][str(nc)]["gap_lower_bound"] for nc in C.CONTEXTS]
    assert glo[-1] > glo[0]   # G_lo grows with more contexts
