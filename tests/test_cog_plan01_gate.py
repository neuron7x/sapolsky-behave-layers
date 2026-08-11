from __future__ import annotations
import json
from experiments.cog_plan_01.run import run
from scripts.cog_plan01_gate import _validate

def test_in_memory_confirmatory_payload_passes_gate_contract():
    v=run(); v.pop("rows")
    assert _validate(v)==[]

def test_hidden_averaging_mutation_is_detected():
    v=run(); v.pop("rows"); v=json.loads(json.dumps(v)); v["planner_policy"]["world_averaging_can_create_robust_action"]=True
    assert _validate(v)
