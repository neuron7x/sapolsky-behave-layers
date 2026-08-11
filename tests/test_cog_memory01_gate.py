from __future__ import annotations
import json
from pathlib import Path
from scripts.cog_memory01_gate import _validate
ROOT=Path(__file__).resolve().parents[1]

def test_memory_gate_when_result_exists():
    p=ROOT/"research/results/COG-MEMORY-01/verdict.json"
    if p.exists(): assert _validate(json.loads(p.read_text()))==[]

def test_memory_gate_kills_assumption_causal_mutation_when_result_exists():
    p=ROOT/"research/results/COG-MEMORY-01/verdict.json"
    if not p.exists(): return
    v=json.loads(p.read_text()); v["memory_policy"]["assumption_conditional_causal_consolidation_allowed"]=True
    assert _validate(v)
