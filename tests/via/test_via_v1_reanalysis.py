from __future__ import annotations

from pathlib import Path

from experiments.via_v1_causal_surface.analyze import analyze
from experiments.via_v1_causal_surface.run import build
from scripts.via_gate import validate

ROOT = Path(__file__).resolve().parents[2]


def test_normalized_input_binds_prior_kill_rule_and_contains_only_frozen_bundles() -> None:
    payload = build()
    assert payload["ascension_authority"] is False
    assert payload["prior_kill_rule"] == "WP18_KILL_RULE_TRIGGERED_NO_REAL_IDENTIFIABILITY"
    assert payload["prior_robustness_verdict"] == "NEGATIVE_IS_MECHANISM_SPECIFIC"
    assert len(payload["bundles"]) == 5
    assert {b["tier"] for b in payload["bundles"]} == {
        "REAL_RETROSPECTIVE", "SYNTHETIC_POSITIVE_CONTROL"
    }


def test_reanalysis_reproduces_sealed_direction_without_authorizing_ascension() -> None:
    result = analyze()
    assert result["verdict"] == "VIA_V1_METHOD_VALIDATED_ASCENSION_BLOCKED"
    assert result["ascension_authorized"] is False
    assert result["next_scientific_level_authorized"] is False
    assert all(result["method_checks"].values())
    real = [b for b in result["bundles"] if b["tier"] == "REAL_RETROSPECTIVE"]
    assert real and all(b["frozen_g_lo_matches"] for b in real)
    assert all(not b["retrospective_routable_by_frozen_rule"] for b in real)
    positive = next(b for b in result["bundles"] if b["tier"] == "SYNTHETIC_POSITIVE_CONTROL")
    assert positive["corrected_g_lo"] > 0


def test_via_gate_accepts_blocked_state_as_fail_closed_success() -> None:
    assert validate(ROOT) == []
