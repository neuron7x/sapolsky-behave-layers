from __future__ import annotations
import subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def test_csca03r_gate_current_tree():
    p=subprocess.run([sys.executable,'scripts/csca03r_gate.py'],cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,p.stdout+p.stderr

def test_csca03r_gate_self_attack():
    p=subprocess.run([sys.executable,'scripts/csca03r_gate.py','--self-test'],cwd=ROOT,text=True,capture_output=True)
    assert p.returncode==0,p.stdout+p.stderr
    assert '5/5' in p.stdout
