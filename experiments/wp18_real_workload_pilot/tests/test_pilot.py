"""WP18 pilot tests: contamination control, the frozen decision rule, and instrument sensitivity."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from experiments.wp18_real_workload_pilot.src.analyze import C_ROUTE, _cert, _prospective

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "artifacts/wp18-real-workload-pilot"
VERDICT = DATA / "verdict.json"
CARD = DATA / "dataset_card.json"


@pytest.mark.skipif(not CARD.is_file(), reason="corpora not built in this checkout")
def test_contamination_control_is_clean_for_both_workloads() -> None:
    card = json.loads(CARD.read_text())
    for fam in ("prose", "code"):
        w = card["workloads"][fam]
        assert w["contamination_clean"] is True
        assert w["file_partition_overlap"] is False
        assert w["leaked_eval_files"] == []
        assert len(w["eval_shard_bytes"]) == 5


def test_certificate_detects_a_planted_interaction() -> None:
    """Instrument sensitivity: the certificate MUST certify a real context x resource interaction.

    Without this, a negative result could just mean the estimator is dead.
    """
    # context 0 prefers action 0, context 1 prefers action 1 -- a strong planted interaction
    mats = [[[1.0, 0.0], [0.0, 1.0]] for _ in range(8)]
    assert _cert(mats, +1, [1, 2], 0.0) > 0.0


def test_certificate_refuses_a_flat_benchmark() -> None:
    """No interaction -> no certified gap. The null must actually be refused."""
    mats = [[[0.5, 0.5], [0.5, 0.5]] for _ in range(8)]
    assert _cert(mats, +1, [1, 2], 0.0) <= 0.0


def test_prospective_power_math_is_monotone_in_noise() -> None:
    tight = _prospective([0.10, 0.11, 0.10, 0.09, 0.10, 0.11])
    loose = _prospective([0.10, 0.50, -0.30, 0.40, -0.10, 0.30])
    assert loose["sd"] > tight["sd"]
    assert loose["mde_at_pilot_n"] > tight["mde_at_pilot_n"]


@pytest.mark.skipif(not VERDICT.is_file(), reason="verdict not generated in this checkout")
def test_recorded_verdict_is_internally_consistent() -> None:
    v = json.loads(VERDICT.read_text())
    # the positive control MUST certify, else nothing may be concluded
    assert v["positive_control_synthetic_ac1_g_lo"] > 0.0
    assert v["verdict"] != "WP18_VOID"
    # the decision must follow the frozen rule, not narrative
    for fam, w in v["workloads"].items():
        assert w["passes_g3"] == (w["best_g_lo"] > C_ROUTE), fam
    assert v["decision"]["kill_rule_triggered"] == (
        not any(w["passes_g3"] for w in v["workloads"].values()))
    # a pilot may never carry an architecture claim
    assert "any architecture claim" in v["prohibited_extrapolations"]
