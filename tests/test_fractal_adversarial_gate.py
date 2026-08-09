from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "fractal_adversarial_gate.py"
spec = importlib.util.spec_from_file_location("fractal_adversarial_gate", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_real_frozen_adversarial_evidence_is_fail_closed() -> None:
    payload = module.derive(ROOT / "artifacts" / "fractal-adversarial-v1")
    assert module.audit(payload) == []
    assert payload["claims"]["multiscale_replication_supported"] is False
    assert payload["claims"]["physical_conditional_execution_supported"] is False
    assert payload["claims"]["graph_distance_fractality_supported"] is False
    assert payload["scientific_ascension_authority"] is False
    assert payload["via_authority"] is False
