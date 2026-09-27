from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from cwc.governance.openai_snapshot_panel import (
    PANEL_ID,
    SnapshotPanelError,
    verify_openai_snapshot_panel,
)

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "artifacts" / "dgc-product-v1" / "execution-candidates"


def _verify(root: Path):
    return verify_openai_snapshot_panel(
        model_manifest_path=root / "openai_5_4_model_manifest_v1.json",
        action_catalog_path=root / "openai_5_4_action_catalog_v1.json",
        pricing_snapshot_path=root / "openai_5_4_pricing_snapshot_v1.json",
    )


def _copy(tmp_path: Path) -> Path:
    root = tmp_path / "panel"
    shutil.copytree(CANONICAL, root)
    return root


def test_canonical_openai_snapshot_panel_is_closed_and_non_promotional():
    authority = _verify(CANONICAL)
    assert authority.panel_id == PANEL_ID
    assert authority.agent == "codex"
    assert authority.agent_version == "0.157.1"
    assert authority.action_ids == ("DEEP", "STANDARD")
    assert authority.model_ids == (
        "gpt-5.4-mini-2026-03-17",
        "gpt-5.4-nano-2026-03-17",
    )
    assert len(authority.authority_digest) == 64
    assert authority.executable_evidence_observed is False
    assert authority.product_promotion_authorized is False


def test_mutable_model_alias_is_rejected(tmp_path: Path):
    root = _copy(tmp_path)
    path = root / "openai_5_4_model_manifest_v1.json"
    doc = json.loads(path.read_text())
    doc["models"][0]["model_id"] = "gpt-5.4-mini"
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(SnapshotPanelError, match="snapshot date"):
        _verify(root)


def test_action_model_substitution_is_rejected(tmp_path: Path):
    root = _copy(tmp_path)
    path = root / "openai_5_4_action_catalog_v1.json"
    doc = json.loads(path.read_text())
    doc["actions"][0]["model_id"] = "gpt-5.4-nano-2026-03-17"
    doc["actions"][0]["harbor_model_argument"] = "openai/gpt-5.4-nano-2026-03-17"
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(SnapshotPanelError, match="DEEP model snapshot"):
        _verify(root)


def test_non_monotone_tier_pricing_is_rejected(tmp_path: Path):
    root = _copy(tmp_path)
    path = root / "openai_5_4_pricing_snapshot_v1.json"
    doc = json.loads(path.read_text())
    for row in doc["entries"]:
        if row["model_id"] == "gpt-5.4-mini-2026-03-17":
            row["input_per_million"] = 0.10
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(SnapshotPanelError, match="strictly more expensive"):
        _verify(root)


def test_candidate_manifest_cannot_grant_product_promotion(tmp_path: Path):
    root = _copy(tmp_path)
    path = root / "openai_5_4_action_catalog_v1.json"
    doc = json.loads(path.read_text())
    doc["product_promotion_authorized"] = True
    path.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(SnapshotPanelError, match="cannot grant product promotion"):
        _verify(root)
