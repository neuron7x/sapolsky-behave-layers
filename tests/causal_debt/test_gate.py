from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.causal_debt_gate import ROOT, audit_documents, validate


def _verdict(name: str) -> dict:
    return json.loads((ROOT / "artifacts" / name / "verdict.json").read_text())


def test_current_causal_debt_gate_passes() -> None:
    assert validate() == []


def test_gate_rejects_v2_ascension_escalation() -> None:
    v1 = _verdict("causal-debt-v1")
    v2 = copy.deepcopy(_verdict("causal-debt-v2"))
    v2["via_ascension_authorized"] = True
    assert any("VIA ascension" in error for error in audit_documents(v1, v2))


def test_gate_rejects_rewriting_v1_negative() -> None:
    v1 = copy.deepcopy(_verdict("causal-debt-v1"))
    v2 = _verdict("causal-debt-v2")
    v1["verdict"] = "CAUSAL_DEBT_CONTROL_QUALIFIED"
    errors = audit_documents(v1, v2)
    assert any("V1 negative verdict" in error for error in errors)
    assert any("not bound" in error for error in errors)
