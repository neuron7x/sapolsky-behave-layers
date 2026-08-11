from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_parent_raw_run_is_preserved_as_nonpassing_harness_failure():
    path = ROOT / "research/results/COG-EPISTEMIC-01/verdict.json"
    if not path.exists():
        return
    v = json.loads(path.read_text())
    assert v["verdict"] == "TYPED_EPISTEMIC_LATTICE_NOT_QUALIFIED"
    assert v["scientific_pass"] is False
    assert any("F11_LEGACY_COUNTERMODEL_COLLAPSE" in e for e in v["errors"])
