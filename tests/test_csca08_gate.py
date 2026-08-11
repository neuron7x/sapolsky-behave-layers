from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def test_csca08_gate_and_self_test():
    out=subprocess.run([sys.executable,str(ROOT/'scripts/csca08_gate.py'),'--self-test'],cwd=ROOT,text=True,capture_output=True)
    assert out.returncode == 0, out.stdout + out.stderr
    assert '5/5' in out.stdout
    assert 'CSCA08-GATE PASS' in out.stdout
