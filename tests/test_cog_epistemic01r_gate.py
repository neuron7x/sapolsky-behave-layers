from __future__ import annotations

import json
from pathlib import Path

from scripts.cog_epistemic01r_gate import _validate


ROOT = Path(__file__).resolve().parents[1]


def test_r1_gate_validates_when_result_exists():
    p = ROOT / "research/results/COG-EPISTEMIC-01/verdict.json"
    r = ROOT / "research/results/COG-EPISTEMIC-01R/verdict.json"
    if not r.exists():
        return
    assert _validate(json.loads(p.read_text()), json.loads(r.read_text())) == []


def test_r1_gate_kills_terminal_resurrection_mutation_when_result_exists():
    p = ROOT / "research/results/COG-EPISTEMIC-01/verdict.json"
    r = ROOT / "research/results/COG-EPISTEMIC-01R/verdict.json"
    if not r.exists():
        return
    pv, rv = json.loads(p.read_text()), json.loads(r.read_text())
    rv["epistemic_boundary"]["terminal_record_resurrection_allowed"] = True
    assert _validate(pv, rv)
