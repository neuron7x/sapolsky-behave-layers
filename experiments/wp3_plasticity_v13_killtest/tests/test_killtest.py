"""Tests for L4k falsification boundary."""
from __future__ import annotations

import pytest

from experiments.wp3_plasticity_v13_killtest.src import killtest as K


@pytest.fixture(scope="module")
def result():
    return K.analyze()


def test_verdict_line_survives(result):
    assert result["verdict"] == "L4K_LINE_SURVIVES"


def test_real_shows_gap(result):
    c = result["conditions"]["real"]
    assert c["gap_lower_bound"] > 0.0
    assert c["governor_recovery"] >= 0.8


def test_every_null_vanishes(result):
    for kind in ("additive", "collapsed", "aligned_best"):
        c = result["conditions"][kind]
        assert c["gap_lower_bound"] <= 0.0        # interaction destroyed -> no identifiable gap
        assert c["governor_recovery"] <= 0.10     # governor cannot recover a gap that isn't there


def test_nulls_are_not_vacuous(result):
    # the nulls must actually differ from real (a null that equals real would be a broken test)
    real = result["conditions"]["real"]["gap_lower_bound"]
    for kind in ("additive", "collapsed", "aligned_best"):
        assert result["conditions"][kind]["gap_lower_bound"] < real - 0.05
