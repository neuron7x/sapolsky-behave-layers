from __future__ import annotations

import json
from pathlib import Path

from experiments.via_v1_attention_horizon_qualification.run import build_rows
from cwc.causal.opportunity import opportunity_at_lambda, summarize_opportunity

ROOT = Path(__file__).resolve().parents[2]


def test_exact_control_has_expected_information_surface() -> None:
    rows = build_rows()
    assert len({r.unit_id for r in rows}) == 512
    s = summarize_opportunity(rows, actions=("short", "full"))
    assert s.positive_regime_interval_found
    assert s.max_controller_compute_allowance > 0.0


def test_controlled_qualification_never_authorizes_scientific_ascension() -> None:
    path = ROOT / "artifacts/via-v1-attention-horizon-qualification/verdict.json"
    if not path.is_file():
        return  # protocol may be tested before the prospective controlled run
    verdict = json.loads(path.read_text())
    assert verdict["scientific_pass"] is False
    assert verdict["ascension_authorized"] is False
    assert verdict["via_v2_authorized"] is False


def test_controller_allowance_boundary_is_exact() -> None:
    rows = build_rows()
    # At lambda=.04 the gross regime gap is .12; controller compute 3 costs .12.
    p = opportunity_at_lambda(rows, lambda_compute=0.04, controller_compute=3.0)
    assert abs(p.regime_net_gap) <= 1e-12
