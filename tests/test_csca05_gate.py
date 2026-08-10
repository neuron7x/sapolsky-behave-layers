from __future__ import annotations
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_csca05_gate_passes():
    result = subprocess.run([sys.executable, str(ROOT / "scripts/csca05_gate.py")], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
