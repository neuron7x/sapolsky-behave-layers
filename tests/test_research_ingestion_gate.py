from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_research_ingestion_gate_passes() -> None:
    proc = subprocess.run(
        [sys.executable, "scripts/research_ingestion_gate.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "RESEARCH-INGESTION-GATE: PASS" in proc.stdout


def test_all_hypotheses_have_fail_closed_fields() -> None:
    hypotheses = json.loads((ROOT / "research/06_EXECUTABLE_HYPOTHESES.yaml").read_text())
    for item in hypotheses:
        assert item["failure_condition"].strip()
        assert item["null_model"].strip()
        assert item["decision_rule"].strip()
        assert item["promotion_status"] == "CLAIM_EXTRACTED"
