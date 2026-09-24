from __future__ import annotations

import json
from pathlib import Path

import pytest

from cwc.governance.frozen_action_catalog import (
    FrozenActionCatalogError,
    load_frozen_action_catalog,
)
from cwc.governance.materialization_transaction import sha256_file


def _fixture(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    manifest = repo / "actions.json"
    doc = {
        "schema": "DGC_ACTION_CATALOG_MANIFEST_V1",
        "actions": [
            {
                "action_id": "DEEP",
                "harbor_agent": "agent-deep",
                "harbor_model": "provider/model-deep",
                "agent_version": "1.0.0",
                "provider": "provider",
                "model_id": "model-deep",
                "model_version": "2026-09-01-r1",
            },
            {
                "action_id": "STANDARD",
                "harbor_agent": "agent-standard",
                "harbor_model": "provider/model-standard",
                "agent_version": "1.0.0",
                "provider": "provider",
                "model_id": "model-standard",
                "model_version": "2026-09-01-r1",
            },
        ],
    }
    manifest.write_text(json.dumps(doc, sort_keys=True) + "\n", encoding="utf-8")
    execution = {
        "components": [{
            "component": "action_catalog_manifest",
            "path": "actions.json",
            "sha256": sha256_file(manifest),
        }]
    }
    return repo, manifest, execution


def test_runtime_resolves_exact_frozen_action(tmp_path: Path):
    repo, _, execution = _fixture(tmp_path)
    catalog = load_frozen_action_catalog(repository_root=repo, execution_freeze=execution)
    deep = catalog.resolve("DEEP")
    assert deep.harbor_agent == "agent-deep"
    assert deep.harbor_model == "provider/model-deep"
    assert deep.model_id == "model-deep"
    assert deep.model_version == "2026-09-01-r1"
    assert len(catalog.component_sha256) == 64


def test_action_catalog_byte_drift_is_rejected(tmp_path: Path):
    repo, manifest, execution = _fixture(tmp_path)
    doc = json.loads(manifest.read_text())
    doc["actions"][0]["model_id"] = "tampered"
    manifest.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(FrozenActionCatalogError, match="bytes differ"):
        load_frozen_action_catalog(repository_root=repo, execution_freeze=execution)


def test_unknown_action_is_rejected(tmp_path: Path):
    repo, _, execution = _fixture(tmp_path)
    catalog = load_frozen_action_catalog(repository_root=repo, execution_freeze=execution)
    with pytest.raises(FrozenActionCatalogError, match="unknown frozen action_id"):
        catalog.resolve("ULTRA")


def test_symlinked_catalog_is_rejected(tmp_path: Path):
    repo, manifest, execution = _fixture(tmp_path)
    real = repo / "actions-real.json"
    manifest.rename(real)
    manifest.symlink_to(real)
    with pytest.raises(FrozenActionCatalogError, match="symlink path rejected"):
        load_frozen_action_catalog(repository_root=repo, execution_freeze=execution)


def test_duplicate_or_unsorted_action_ids_are_rejected(tmp_path: Path):
    repo, manifest, execution = _fixture(tmp_path)
    doc = json.loads(manifest.read_text())
    doc["actions"] = list(reversed(doc["actions"]))
    manifest.write_text(json.dumps(doc), encoding="utf-8")
    execution["components"][0]["sha256"] = sha256_file(manifest)
    with pytest.raises(FrozenActionCatalogError, match="sorted and unique"):
        load_frozen_action_catalog(repository_root=repo, execution_freeze=execution)
