"""Tests for WP12 preregistration-integrity audit."""
from __future__ import annotations

from experiments.wp12_prereg_integrity.src import prereg_integrity as W


def test_verdict_clean():
    r = W.analyze()
    assert r["verdict"] == "PREREG_INTEGRITY_CLEAN"
    assert r["violations"] == 0


def test_mechanism_experiments_are_strict_ancestor():
    r = W.analyze()
    assert r["strict_ancestor"] >= 12          # the genuine mechanism/rigor arcs, prereg-before-results
    # every same-commit case must be disclosed
    for c in r["checks"]:
        if c.get("classification") == "SAME_COMMIT_RETROSPECTIVE":
            assert c["disclosed"] is True
