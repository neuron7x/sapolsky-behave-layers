from __future__ import annotations

import json
from pathlib import Path

from scripts import cog_countermodel01_gate as gate

ROOT = Path(__file__).resolve().parents[1]


def _load():
    return (
        json.loads((ROOT / "research/results/COG-COUNTERMODEL-01/verdict.json").read_text()),
        json.loads((ROOT / "research/results/COG-COUNTERMODEL-01R/verdict.json").read_text()),
    )


def test_current_verdict_pair_validates():
    p, r = _load()
    assert gate._validate(p, r) == []


def test_parent_negative_cannot_be_rewritten_positive():
    p, r = _load()
    p["scientific_pass"] = True
    assert gate._validate(p, r)


def test_truth_selection_cannot_be_promoted():
    p, r = _load()
    r["epistemic_boundary"]["hidden_true_beta_recovery_used_for_qualification"] = True
    assert gate._validate(p, r)


def test_active_authority_cannot_be_promoted():
    p, r = _load()
    r["epistemic_boundary"]["active_control"] = True
    assert gate._validate(p, r)
