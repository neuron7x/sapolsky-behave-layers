from __future__ import annotations

import json
from pathlib import Path

import pytest

from cwc.governance.execution_manifest_freeze import (
    ExecutionManifestError,
    freeze_execution_manifests,
    verify_execution_manifest_freeze_document,
)
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes

COMMIT = "a" * 40
TREE = "b" * 40
FAMILY = "SWE_BENCH_VERIFIED"


def _h(char: str) -> str:
    return char * 64


def _write(path: Path, payload: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path.relative_to(path.parents[1]).as_posix() if False else str(path)


def _reference(repo: Path) -> Path:
    payload = {
        "schema": "DGC_EXTERNAL_EVIDENCE_REFERENCE_V2",
        "subject_type": "DGC_EXTERNAL_MATERIALIZATION_GENERATION_V2",
        "publication_manifest_sha256": _h("1"),
        "payload_manifest_sha256": _h("2"),
        "materialization_receipt_sha256": _h("3"),
        "materialization_provenance_sha256": _h("4"),
        "source_registry_sha256": _h("5"),
        "materializer_sha256": _h("6"),
        "repository_commit": COMMIT,
        "repository_tree": TREE,
        "family_bindings": [
            {
                "family_id": FAMILY,
                "source_authority_digest": _h("7"),
                "materialized_authority_digest": _h("8"),
                "materialized_tree_sha256": _h("9"),
                "materialized_task_manifest_sha256": _h("a"),
                "expected_task_count": 500,
                "semantic_verification_digest": _h("b"),
            },
            {
                "family_id": "TERMINAL_BENCH_2_1",
                "source_authority_digest": _h("c"),
                "materialized_authority_digest": _h("d"),
                "materialized_tree_sha256": _h("e"),
                "materialized_task_manifest_sha256": _h("f"),
                "expected_task_count": 89,
                "semantic_verification_digest": _h("0"),
            },
        ],
        "file_count": 10,
    }
    payload["reference_digest"] = sha256_bytes(canonical_json_bytes(payload))
    path = repo / "eval_bundle" / "materialization-reference.json"
    _write(path, payload)
    return path


def _manifests(repo: Path) -> tuple[dict[str, str], dict[str, str]]:
    base = repo / "eval_bundle" / "manifests"
    paths = {
        "model_manifest": base / "model.json",
        "prompt_policy": base / "prompt.json",
        "tool_manifest": base / "tools.json",
        "environment": base / "environment.json",
        "budget": base / "budget.json",
        "pricing_snapshot": base / "pricing.json",
        "scorer": base / "scorer.json",
    }
    _write(paths["model_manifest"], {
        "schema": "DGC_MODEL_MANIFEST_V1",
        "models": [{"provider": "provider", "model_id": "model", "model_version": "2026-08-23-r1"}],
    })
    _write(paths["prompt_policy"], {
        "schema": "DGC_PROMPT_POLICY_V1",
        "system_prompt_sha256": _h("1"),
        "template_sha256": _h("2"),
    })
    _write(paths["tool_manifest"], {
        "schema": "DGC_TOOL_MANIFEST_V1",
        "tools": [{"name": "shell", "version": "1", "contract_sha256": _h("3")}],
    })
    _write(paths["environment"], {
        "schema": "DGC_ENVIRONMENT_MANIFEST_V1",
        "container_image_digest": "sha256:" + _h("4"),
        "runtime": "linux-amd64",
    })
    _write(paths["budget"], {
        "schema": "DGC_BUDGET_MANIFEST_V1",
        "max_tokens": 1000,
        "max_cost_usd": 2.0,
        "max_wall_time_s": 120,
        "max_steps": 20,
    })
    _write(paths["pricing_snapshot"], {
        "schema": "DGC_PRICING_SNAPSHOT_V1",
        "captured_at": "2026-08-23T00:00:00Z",
        "entries": [{
            "provider": "provider", "model_id": "model", "currency": "USD",
            "input_per_million": 1.0, "output_per_million": 2.0,
        }],
    })
    _write(paths["scorer"], {
        "schema": "DGC_SCORER_MANIFEST_V1",
        "version": "v1",
        "implementation_sha256": _h("5"),
    })
    policies: dict[str, str] = {}
    for index, policy_id in enumerate(("B0", "DGC"), start=6):
        path = base / f"policy-{policy_id}.json"
        _write(path, {
            "schema": "DGC_GOVERNANCE_POLICY_MANIFEST_V1",
            "policy_id": policy_id,
            "implementation_sha256": _h(str(index)),
            "config_sha256": _h(str(index + 1)),
        })
        policies[policy_id] = path.relative_to(repo).as_posix()
    return {key: path.relative_to(repo).as_posix() for key, path in paths.items()}, policies


def _freeze(repo: Path):
    reference = _reference(repo)
    components, policies = _manifests(repo)
    return freeze_execution_manifests(
        repository_root=repo,
        repository_commit=COMMIT,
        repository_tree=TREE,
        family_id=FAMILY,
        materialization_reference_path=reference.relative_to(repo),
        component_paths=components,
        governance_policy_paths=policies,
    )


def test_valid_execution_freeze_binds_actual_manifest_bytes(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    frozen = _freeze(repo)
    assert frozen.family_id == FAMILY
    assert len(frozen.components) == 7
    assert len(frozen.governance_policies) == 2
    assert frozen.task_manifest_digest == _h("a")
    assert frozen.statistical_plan_digest
    assert frozen.prebaseline_comparison_digest
    assert frozen.document["harness_frozen"] is False


def test_mutable_model_alias_is_rejected(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    reference = _reference(repo)
    components, policies = _manifests(repo)
    model = repo / components["model_manifest"]
    _write(model, {
        "schema": "DGC_MODEL_MANIFEST_V1",
        "models": [{"provider": "p", "model_id": "m", "model_version": "latest"}],
    })
    with pytest.raises(ExecutionManifestError, match="mutable model version alias"):
        freeze_execution_manifests(
            repository_root=repo, repository_commit=COMMIT, repository_tree=TREE,
            family_id=FAMILY, materialization_reference_path=reference.relative_to(repo),
            component_paths=components, governance_policy_paths=policies,
        )


def test_mutable_container_tag_is_rejected(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    reference = _reference(repo)
    components, policies = _manifests(repo)
    environment = repo / components["environment"]
    _write(environment, {
        "schema": "DGC_ENVIRONMENT_MANIFEST_V1",
        "container_image_digest": "ubuntu:latest",
        "runtime": "linux-amd64",
    })
    with pytest.raises(ExecutionManifestError, match="immutable OCI"):
        freeze_execution_manifests(
            repository_root=repo, repository_commit=COMMIT, repository_tree=TREE,
            family_id=FAMILY, materialization_reference_path=reference.relative_to(repo),
            component_paths=components, governance_policy_paths=policies,
        )


def test_freeze_digest_detects_post_freeze_tampering(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    frozen = _freeze(repo)
    path = repo / "eval_bundle" / "freeze.json"
    _write(path, frozen.document)
    assert verify_execution_manifest_freeze_document(path)["freeze_digest"] == frozen.freeze_digest
    doc = json.loads(path.read_text())
    doc["task_manifest_digest"] = _h("f")
    _write(path, doc)
    with pytest.raises(ExecutionManifestError, match="freeze digest mismatch"):
        verify_execution_manifest_freeze_document(path)
