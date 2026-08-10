from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_csca06a_gate_passes():
    p=subprocess.run([sys.executable,'scripts/csca06a_gate.py'],cwd=ROOT,capture_output=True,text=True)
    assert p.returncode==0, p.stdout+p.stderr
