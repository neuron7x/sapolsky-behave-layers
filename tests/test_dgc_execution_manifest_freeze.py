from __future__ import annotations

import json
from pathlib import Path

import pytest

from cwc.governance.execution_manifest_freeze import (
    ExecutionManifestError,
    freeze_execution_manifests,
    policy_action_catalog_digest,
    policy_observation_contract_digest,
    verify_execution_manifest_freeze_document,
)
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file

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
    adapter = repo / "scripts" / "test-dgc-unit-adapter.py"
    adapter.parent.mkdir(parents=True, exist_ok=True)
    adapter.write_text("print('adapter')\n", encoding="utf-8")
    paths = {
        "action_catalog_manifest": base / "actions.json",
        "executor_manifest": base / "executor.json",
        "model_manifest": base / "model.json",
        "observation_provider_manifest": base / "observations.json",
        "prompt_policy": base / "prompt.json",
        "tool_manifest": base / "tools.json",
        "environment": base / "environment.json",
        "budget": base / "budget.json",
        "pricing_snapshot": base / "pricing.json",
        "risk_endpoint_manifest": base / "risk-endpoint.json",
        "scorer": base / "scorer.json",
    }
    _write(paths["action_catalog_manifest"], {
        "schema": "DGC_ACTION_CATALOG_MANIFEST_V1",
        "actions": [
            {
                "action_id": "DEEP",
                "harbor_agent": "agent-deep",
                "agent_version": "1.0.0",
                "provider": "provider",
                "model_id": "model",
                "model_version": "2026-08-23-r1",
            },
            {
                "action_id": "STANDARD",
                "harbor_agent": "agent-standard",
                "agent_version": "1.0.0",
                "provider": "provider",
                "model_id": "model",
                "model_version": "2026-08-23-r1",
            },
        ],
    })
    _write(paths["executor_manifest"], {
        "schema": "DGC_EXECUTOR_MANIFEST_V1",
        "protocol": "DGC_FROZEN_UNIT_EXECUTOR_PROTOCOL_V1",
        "request_schema": "DGC_UNIT_EXECUTION_REQUEST_V1",
        "response_schema": "DGC_UNIT_EXECUTION_RESPONSE_V1",
        "entrypoint_path": adapter.relative_to(repo).as_posix(),
        "entrypoint_sha256": sha256_file(adapter),
        "argv": ["python", adapter.relative_to(repo).as_posix()],
        "timeout_seconds": 30,
        "allowed_environment_variables": [],
    })
    _write(paths["model_manifest"], {
        "schema": "DGC_MODEL_MANIFEST_V1",
        "models": [{"provider": "provider", "model_id": "model", "model_version": "2026-08-23-r1"}],
    })
    observation_impl = repo / "features" / "terminal_observations.py"
    observation_impl.parent.mkdir(parents=True, exist_ok=True)
    observation_impl.write_text("print('observations')\n", encoding="utf-8")
    _write(paths["observation_provider_manifest"], {
        "schema": "DGC_OBSERVATION_PROVIDER_MANIFEST_V1",
        "protocol": "DGC_PREOUTCOME_OBSERVATION_PROTOCOL_V1",
        "request_schema": "DGC_PREOUTCOME_OBSERVATION_REQUEST_V1",
        "response_schema": "DGC_PREOUTCOME_OBSERVATION_RESPONSE_V1",
        "implementation_path": observation_impl.relative_to(repo).as_posix(),
        "implementation_sha256": sha256_file(observation_impl),
        "argv": ["python", observation_impl.relative_to(repo).as_posix()],
        "timeout_seconds": 5,
        "output_fields": ["budget_remaining", "initial_uncertainty", "step_index"],
        "network_access_allowed": False,
        "confirmatory_label_access": False,
        "post_outcome_access_allowed": False,
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
            "provider": "provider",
            "model_id": "model",
            "model_version": "2026-08-23-r1",
            "currency": "USD",
            "source_uri": "https://example.invalid/provider/model/pricing",
            "input_per_million": 1.0,
            "cached_input_per_million": 0.1,
            "cache_write_per_million": 1.25,
            "long_cache_write_per_million": 1.25,
            "output_per_million": 2.0,
        }],
    })
    risk_impl = repo / "metrics" / "catastrophic_regret.py"
    risk_impl.parent.mkdir(parents=True, exist_ok=True)
    risk_impl.write_text("def catastrophic_regret(row):\n    return float(row['risk'])\n", encoding="utf-8")
    _write(paths["risk_endpoint_manifest"], {
        "schema": "DGC_RISK_ENDPOINT_MANIFEST_V1",
        "endpoint_name": "catastrophic_regret",
        "scale": "[0,1]",
        "semantics_version": "test-v1",
        "protocol": "DGC_RISK_ENDPOINT_EXECUTION_PROTOCOL_V1",
        "request_schema": "DGC_RISK_ENDPOINT_REQUEST_V1",
        "response_schema": "DGC_RISK_ENDPOINT_RESPONSE_V1",
        "implementation_path": risk_impl.relative_to(repo).as_posix(),
        "implementation_sha256": sha256_file(risk_impl),
        "argv": ["python", risk_impl.relative_to(repo).as_posix()],
        "timeout_seconds": 5,
        "source_fields": ["risk"],
        "policy_outcome_independent_definition": True,
        "post_outcome_relabeling_allowed": False,
        "network_access_allowed": False,
    })
    _write(paths["scorer"], {
        "schema": "DGC_SCORER_MANIFEST_V1",
        "version": "v1",
        "implementation_sha256": _h("5"),
    })
    policies: dict[str, str] = {}
    for index, policy_id in enumerate(("B0", "DGC"), start=6):
        implementation = repo / "policies" / f"{policy_id}.py"
        implementation.parent.mkdir(parents=True, exist_ok=True)
        implementation.write_text(f"POLICY_ID = {policy_id!r}\n", encoding="utf-8")
        config = repo / "policies" / f"{policy_id}.json"
        config_doc = {
            "schema": "DGC_GOVERNANCE_POLICY_CONFIG_V1",
            "policy_id": policy_id,
            "action_ids": ["DEEP", "STANDARD"],
            "observation_fields": ["budget_remaining", "initial_uncertainty", "step_index"],
        }
        config.write_text(json.dumps(config_doc, sort_keys=True) + "\n", encoding="utf-8")
        path = base / f"policy-{policy_id}.json"
        _write(path, {
            "schema": "DGC_GOVERNANCE_POLICY_MANIFEST_V1",
            "policy_id": policy_id,
            "protocol": "DGC_GOVERNANCE_POLICY_EXECUTION_PROTOCOL_V1",
            "request_schema": "DGC_POLICY_DECISION_REQUEST_V1",
            "response_schema": "DGC_POLICY_DECISION_RESPONSE_V1",
            "state_protocol": "STATE_IN_REQUEST_ONLY",
            "network_access_allowed": False,
            "confirmatory_label_access": False,
            "implementation_path": implementation.relative_to(repo).as_posix(),
            "implementation_sha256": sha256_file(implementation),
            "config_path": config.relative_to(repo).as_posix(),
            "config_sha256": sha256_file(config),
            "argv": [
                "python",
                implementation.relative_to(repo).as_posix(),
                "--config",
                config.relative_to(repo).as_posix(),
            ],
            "timeout_seconds": 5,
            "action_catalog_digest": policy_action_catalog_digest(config_doc["action_ids"]),
            "observation_contract_digest": policy_observation_contract_digest(
                config_doc["observation_fields"]
            ),
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
    assert len(frozen.components) == 11
    assert len(frozen.governance_policies) == 2
    assert frozen.task_manifest_digest == _h("a")
    assert frozen.statistical_plan_digest
    assert frozen.prebaseline_comparison_digest
    assert frozen.document["harness_frozen"] is False


def test_observation_provider_implementation_tamper_is_rejected(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    reference = _reference(repo)
    components, policies = _manifests(repo)
    implementation = repo / "features" / "terminal_observations.py"
    implementation.write_text("print('tampered')\n", encoding="utf-8")
    with pytest.raises(ExecutionManifestError, match="observation provider implementation bytes differ"):
        freeze_execution_manifests(
            repository_root=repo, repository_commit=COMMIT, repository_tree=TREE,
            family_id=FAMILY, materialization_reference_path=reference.relative_to(repo),
            component_paths=components, governance_policy_paths=policies,
        )


def test_observation_provider_contract_must_match_all_policies(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    reference = _reference(repo)
    components, policies = _manifests(repo)
    provider = repo / components["observation_provider_manifest"]
    doc = json.loads(provider.read_text())
    doc["output_fields"] = ["budget_remaining", "step_index"]
    _write(provider, doc)
    with pytest.raises(ExecutionManifestError, match="output fields differ"):
        freeze_execution_manifests(
            repository_root=repo, repository_commit=COMMIT, repository_tree=TREE,
            family_id=FAMILY, materialization_reference_path=reference.relative_to(repo),
            component_paths=components, governance_policy_paths=policies,
        )


def test_observation_provider_network_access_is_rejected(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    reference = _reference(repo)
    components, policies = _manifests(repo)
    provider = repo / components["observation_provider_manifest"]
    doc = json.loads(provider.read_text())
    doc["network_access_allowed"] = True
    _write(provider, doc)
    with pytest.raises(ExecutionManifestError, match="network access must be prohibited"):
        freeze_execution_manifests(
            repository_root=repo, repository_commit=COMMIT, repository_tree=TREE,
            family_id=FAMILY, materialization_reference_path=reference.relative_to(repo),
            component_paths=components, governance_policy_paths=policies,
        )


def test_executor_entrypoint_tamper_is_rejected(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    reference = _reference(repo)
    components, policies = _manifests(repo)
    adapter = repo / "scripts" / "test-dgc-unit-adapter.py"
    adapter.write_text("print('tampered')\n", encoding="utf-8")
    with pytest.raises(ExecutionManifestError, match="entrypoint bytes differ"):
        freeze_execution_manifests(
            repository_root=repo, repository_commit=COMMIT, repository_tree=TREE,
            family_id=FAMILY, materialization_reference_path=reference.relative_to(repo),
            component_paths=components, governance_policy_paths=policies,
        )


def test_executor_environment_allowlist_must_be_canonical(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    reference = _reference(repo)
    components, policies = _manifests(repo)
    manifest = repo / components["executor_manifest"]
    doc = json.loads(manifest.read_text())
    doc["allowed_environment_variables"] = ["Z_KEY", "A_KEY"]
    _write(manifest, doc)
    with pytest.raises(ExecutionManifestError, match="sorted and unique"):
        freeze_execution_manifests(
            repository_root=repo, repository_commit=COMMIT, repository_tree=TREE,
            family_id=FAMILY, materialization_reference_path=reference.relative_to(repo),
            component_paths=components, governance_policy_paths=policies,
        )


def test_governance_action_catalog_drift_is_rejected(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    reference = _reference(repo)
    components, policies = _manifests(repo)
    manifest = repo / policies["DGC"]
    doc = json.loads(manifest.read_text())
    config = repo / doc["config_path"]
    config_doc = json.loads(config.read_text())
    config_doc["action_ids"] = ["DEEP", "STANDARD", "ULTRA"]
    _write(config, config_doc)
    doc["config_sha256"] = sha256_file(config)
    doc["action_catalog_digest"] = policy_action_catalog_digest(config_doc["action_ids"])
    _write(manifest, doc)
    with pytest.raises(ExecutionManifestError, match="share one frozen action catalog"):
        freeze_execution_manifests(
            repository_root=repo, repository_commit=COMMIT, repository_tree=TREE,
            family_id=FAMILY, materialization_reference_path=reference.relative_to(repo),
            component_paths=components, governance_policy_paths=policies,
        )


def test_governance_observation_contract_drift_is_rejected(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    reference = _reference(repo)
    components, policies = _manifests(repo)
    manifest = repo / policies["DGC"]
    doc = json.loads(manifest.read_text())
    config = repo / doc["config_path"]
    config_doc = json.loads(config.read_text())
    config_doc["observation_fields"] = [
        "budget_remaining",
        "initial_uncertainty",
        "model_disagreement",
        "step_index",
    ]
    _write(config, config_doc)
    doc["config_sha256"] = sha256_file(config)
    doc["observation_contract_digest"] = policy_observation_contract_digest(
        config_doc["observation_fields"]
    )
    _write(manifest, doc)
    with pytest.raises(ExecutionManifestError, match="share one admissible observation contract"):
        freeze_execution_manifests(
            repository_root=repo, repository_commit=COMMIT, repository_tree=TREE,
            family_id=FAMILY, materialization_reference_path=reference.relative_to(repo),
            component_paths=components, governance_policy_paths=policies,
        )


def test_governance_observation_contract_cannot_include_confirmatory_label(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    reference = _reference(repo)
    components, policies = _manifests(repo)
    manifest = repo / policies["DGC"]
    doc = json.loads(manifest.read_text())
    config = repo / doc["config_path"]
    config_doc = json.loads(config.read_text())
    config_doc["observation_fields"] = [
        "budget_remaining",
        "ground_truth",
        "initial_uncertainty",
        "step_index",
    ]
    _write(config, config_doc)
    doc["config_sha256"] = sha256_file(config)
    _write(manifest, doc)
    with pytest.raises(ExecutionManifestError, match="leaks confirmatory outcomes"):
        freeze_execution_manifests(
            repository_root=repo, repository_commit=COMMIT, repository_tree=TREE,
            family_id=FAMILY, materialization_reference_path=reference.relative_to(repo),
            component_paths=components, governance_policy_paths=policies,
        )


def test_governance_network_access_is_rejected(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    reference = _reference(repo)
    components, policies = _manifests(repo)
    manifest = repo / policies["B0"]
    doc = json.loads(manifest.read_text())
    doc["network_access_allowed"] = True
    _write(manifest, doc)
    with pytest.raises(ExecutionManifestError, match="network access prohibited"):
        freeze_execution_manifests(
            repository_root=repo, repository_commit=COMMIT, repository_tree=TREE,
            family_id=FAMILY, materialization_reference_path=reference.relative_to(repo),
            component_paths=components, governance_policy_paths=policies,
        )


def test_governance_policy_implementation_tamper_is_rejected(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    reference = _reference(repo)
    components, policies = _manifests(repo)
    implementation = repo / "policies" / "B0.py"
    implementation.write_text("POLICY_ID = 'tampered'\n", encoding="utf-8")
    with pytest.raises(ExecutionManifestError, match="implementation bytes differ"):
        freeze_execution_manifests(
            repository_root=repo, repository_commit=COMMIT, repository_tree=TREE,
            family_id=FAMILY, materialization_reference_path=reference.relative_to(repo),
            component_paths=components, governance_policy_paths=policies,
        )


def test_governance_policy_config_tamper_is_rejected(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    reference = _reference(repo)
    components, policies = _manifests(repo)
    config = repo / "policies" / "DGC.json"
    config.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ExecutionManifestError, match="config bytes differ"):
        freeze_execution_manifests(
            repository_root=repo, repository_commit=COMMIT, repository_tree=TREE,
            family_id=FAMILY, materialization_reference_path=reference.relative_to(repo),
            component_paths=components, governance_policy_paths=policies,
        )


def test_risk_endpoint_implementation_tamper_is_rejected(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    reference = _reference(repo)
    components, policies = _manifests(repo)
    implementation = repo / "metrics" / "catastrophic_regret.py"
    implementation.write_text("def catastrophic_regret(row):\n    return 0.0\n", encoding="utf-8")
    with pytest.raises(ExecutionManifestError, match="risk endpoint implementation bytes differ"):
        freeze_execution_manifests(
            repository_root=repo, repository_commit=COMMIT, repository_tree=TREE,
            family_id=FAMILY, materialization_reference_path=reference.relative_to(repo),
            component_paths=components, governance_policy_paths=policies,
        )


def test_risk_endpoint_post_outcome_relabeling_is_rejected(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    reference = _reference(repo)
    components, policies = _manifests(repo)
    manifest = repo / components["risk_endpoint_manifest"]
    doc = json.loads(manifest.read_text())
    doc["post_outcome_relabeling_allowed"] = True
    _write(manifest, doc)
    with pytest.raises(ExecutionManifestError, match="post-outcome risk relabeling"):
        freeze_execution_manifests(
            repository_root=repo, repository_commit=COMMIT, repository_tree=TREE,
            family_id=FAMILY, materialization_reference_path=reference.relative_to(repo),
            component_paths=components, governance_policy_paths=policies,
        )


def test_risk_endpoint_network_access_is_rejected(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    reference = _reference(repo)
    components, policies = _manifests(repo)
    manifest = repo / components["risk_endpoint_manifest"]
    doc = json.loads(manifest.read_text())
    doc["network_access_allowed"] = True
    _write(manifest, doc)
    with pytest.raises(ExecutionManifestError, match="prohibit network access"):
        freeze_execution_manifests(
            repository_root=repo, repository_commit=COMMIT, repository_tree=TREE,
            family_id=FAMILY, materialization_reference_path=reference.relative_to(repo),
            component_paths=components, governance_policy_paths=policies,
        )


def test_pricing_model_identity_drift_is_rejected(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    reference = _reference(repo)
    components, policies = _manifests(repo)
    pricing = repo / components["pricing_snapshot"]
    doc = json.loads(pricing.read_text())
    doc["entries"][0]["model_version"] = "different-version"
    _write(pricing, doc)
    with pytest.raises(ExecutionManifestError, match="pricing snapshot must bind exactly"):
        freeze_execution_manifests(
            repository_root=repo, repository_commit=COMMIT, repository_tree=TREE,
            family_id=FAMILY, materialization_reference_path=reference.relative_to(repo),
            component_paths=components, governance_policy_paths=policies,
        )


def test_non_usd_pricing_is_rejected(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    reference = _reference(repo)
    components, policies = _manifests(repo)
    pricing = repo / components["pricing_snapshot"]
    doc = json.loads(pricing.read_text())
    doc["entries"][0]["currency"] = "EUR"
    _write(pricing, doc)
    with pytest.raises(ExecutionManifestError, match="currency must be USD"):
        freeze_execution_manifests(
            repository_root=repo, repository_commit=COMMIT, repository_tree=TREE,
            family_id=FAMILY, materialization_reference_path=reference.relative_to(repo),
            component_paths=components, governance_policy_paths=policies,
        )


def test_action_catalog_model_outside_frozen_model_manifest_is_rejected(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    reference = _reference(repo)
    components, policies = _manifests(repo)
    catalog = repo / components["action_catalog_manifest"]
    doc = json.loads(catalog.read_text())
    doc["actions"][0]["model_id"] = "unfrozen-model"
    _write(catalog, doc)
    with pytest.raises(ExecutionManifestError, match="outside the frozen model manifest"):
        freeze_execution_manifests(
            repository_root=repo, repository_commit=COMMIT, repository_tree=TREE,
            family_id=FAMILY, materialization_reference_path=reference.relative_to(repo),
            component_paths=components, governance_policy_paths=policies,
        )


def test_mutable_action_agent_version_is_rejected(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    reference = _reference(repo)
    components, policies = _manifests(repo)
    catalog = repo / components["action_catalog_manifest"]
    doc = json.loads(catalog.read_text())
    doc["actions"][0]["agent_version"] = "latest"
    _write(catalog, doc)
    with pytest.raises(ExecutionManifestError, match="mutable agent version alias"):
        freeze_execution_manifests(
            repository_root=repo, repository_commit=COMMIT, repository_tree=TREE,
            family_id=FAMILY, materialization_reference_path=reference.relative_to(repo),
            component_paths=components, governance_policy_paths=policies,
        )


def test_policy_action_catalog_must_equal_global_catalog(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    reference = _reference(repo)
    components, policies = _manifests(repo)
    config = repo / "policies" / "DGC.json"
    config_doc = json.loads(config.read_text())
    config_doc["action_ids"] = ["DEEP", "STANDARD", "ULTRA"]
    _write(config, config_doc)
    manifest = repo / policies["DGC"]
    manifest_doc = json.loads(manifest.read_text())
    manifest_doc["config_sha256"] = sha256_file(config)
    manifest_doc["action_catalog_digest"] = policy_action_catalog_digest(config_doc["action_ids"])
    _write(manifest, manifest_doc)
    with pytest.raises(ExecutionManifestError, match="global frozen action catalog"):
        freeze_execution_manifests(
            repository_root=repo, repository_commit=COMMIT, repository_tree=TREE,
            family_id=FAMILY, materialization_reference_path=reference.relative_to(repo),
            component_paths=components, governance_policy_paths=policies,
        )


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


def test_symlinked_manifest_file_is_rejected(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    reference = _reference(repo)
    components, policies = _manifests(repo)
    model = repo / components["model_manifest"]
    real = model.with_name("model-real.json")
    model.rename(real)
    model.symlink_to(real)
    with pytest.raises(ExecutionManifestError, match="manifest symlink path rejected"):
        freeze_execution_manifests(
            repository_root=repo, repository_commit=COMMIT, repository_tree=TREE,
            family_id=FAMILY, materialization_reference_path=reference.relative_to(repo),
            component_paths=components, governance_policy_paths=policies,
        )


def test_symlinked_manifest_parent_is_rejected(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    reference = _reference(repo)
    components, policies = _manifests(repo)
    manifests = repo / "eval_bundle" / "manifests"
    real = repo / "eval_bundle" / "manifests-real"
    manifests.rename(real)
    manifests.symlink_to(real, target_is_directory=True)
    with pytest.raises(ExecutionManifestError, match="manifest symlink path rejected"):
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
