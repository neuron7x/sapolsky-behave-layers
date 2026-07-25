"""WP19 tests: the decision rule must be able to reach the outcome that hurts the author."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
VERDICT = ROOT / "artifacts/wp19-negative-robustness/verdict.json"
WP18_VERDICT = ROOT / "artifacts/wp18-real-workload-pilot/verdict.json"


def test_verdict_follows_the_frozen_rule_not_the_narrative() -> None:
    assert VERDICT.is_file(), "required frozen verdict is missing"
    v = json.loads(VERDICT.read_text())
    interaction = any(w["certifies"] or not w["single_best_depth_for_all_buckets"]
                      for w in v["workloads"].values())
    expected = "NEGATIVE_IS_MECHANISM_SPECIFIC" if interaction else "NEGATIVE_ROBUST_ACROSS_COMPUTE_AXES"
    assert v["verdict"] == expected


def test_positive_control_certifies_else_nothing_concludes() -> None:
    assert VERDICT.is_file(), "required frozen verdict is missing"
    v = json.loads(VERDICT.read_text())
    assert v["positive_control_synthetic_ac1_g_lo"] > 0.0
    assert v["verdict"] != "WP19_VOID"


def test_the_g3_decision_is_unchanged_on_the_new_axis() -> None:
    """The narrowing touches the EXPLANATION, never the decision: G_lo must still fail c_route."""
    assert VERDICT.is_file(), "required WP19 frozen verdict is missing"
    assert WP18_VERDICT.is_file(), "required WP18 frozen verdict is missing"
    v = json.loads(VERDICT.read_text())
    w18 = json.loads(WP18_VERDICT.read_text())
    for fam, w in v["workloads"].items():
        assert w["certifies"] is False, f"{fam} unexpectedly certifies on the untied axis"
        assert w["best_g_lo"] <= w["c_route"]
    assert w18["decision"]["kill_rule_triggered"] is True


def test_a_robustness_wp_may_never_manufacture_a_positive() -> None:
    assert VERDICT.is_file(), "required frozen verdict is missing"
    v = json.loads(VERDICT.read_text())
    assert "any architecture claim" in v["prohibited_extrapolations"]
    assert "cannot create a positive" in v["class_ceiling"]
