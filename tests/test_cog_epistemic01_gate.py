from __future__ import annotations

import json
from pathlib import Path

from scripts.cog_epistemic01_gate import _validate


ROOT = Path(__file__).resolve().parents[1]


def test_parent_raw_run_is_preserved_as_nonpassing_harness_failure():
    path = ROOT / "research/results/COG-EPISTEMIC-01/verdict.json"
    if not path.exists():
        return
    v = json.loads(path.read_text())
    assert v["verdict"] == "TYPED_EPISTEMIC_LATTICE_NOT_QUALIFIED"
    assert v["scientific_pass"] is False
    assert any("F11_LEGACY_COUNTERMODEL_COLLAPSE" in e for e in v["errors"])


def test_cog_epistemic_r1_verdict_validates_when_present():
    path = ROOT / "research/results/COG-EPISTEMIC-01R/verdict.json"
    if not path.exists():
        return
    assert _validate(json.loads(path.read_text())) == []


def test_gate_rejects_r1_authority_mutation_when_present():
    path = ROOT / "research/results/COG-EPISTEMIC-01R/verdict.json"
    if not path.exists():
        return
    v = json.loads(path.read_text())
    v["epistemic_boundary"]["surrogate_or_replay_can_mint_direct_intervention_authority"] = True
    assert _validate(v)
