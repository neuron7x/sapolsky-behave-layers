from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

import cwc.governance.execution_evidence_bundle as bundle_module
import cwc.governance.frozen_panel_executor as executor_module
from cwc.governance.distributed_eval_control import DistributedEvalSpec
from cwc.governance.execution_evidence_bundle import verify_execution_bundle
from cwc.governance.frozen_panel_executor import FrozenPanelExecutionError, execute_frozen_panel
from cwc.governance.materialization_transaction import sha256_file


def h(char: str) -> str:
    return char * 64


class _Binding:
    materialized_task_manifest_sha256 = h("4")


class _Reference:
    digest = h("3")

    def binding(self, family_id: str):
        assert family_id == "FAM"
        return _Binding()


def _adapter_source(*, valid: bool = True) -> str:
    trace = '{"provider_request_id":"req-" + req["unit"]["policy_id"]}' if valid else "{}"
    return f"""
import json
import sys
req = json.load(sys.stdin)
response = {{
    "schema": "DGC_UNIT_EXECUTION_RESPONSE_V1",
    "unit": req["unit"],
    "attempt": req["attempt"],
    "quality": 0.8,
    "catastrophic_regret": 0.1,
    "actual_cost_usd": 0.25,
    "trace": {trace},
}}
sys.stdout.write(json.dumps(response, sort_keys=True))
"""


def _subjects(tmp_path: Path, *, valid_adapter: bool = True):
    repo = tmp_path / "repo"
    repo.mkdir()
    scripts = repo / "scripts"
    scripts.mkdir()
    adapter = scripts / "fixture_adapter.py"
    adapter.write_text(_adapter_source(valid=valid_adapter), encoding="utf-8")

    manifest_dir = repo / "manifests"
    manifest_dir.mkdir()
    executor_manifest = manifest_dir / "executor.json"
    executor_doc = {
        "schema": "DGC_EXECUTOR_MANIFEST_V1",
        "protocol": "DGC_FROZEN_UNIT_EXECUTOR_PROTOCOL_V1",
        "request_schema": "DGC_UNIT_EXECUTION_REQUEST_V1",
        "response_schema": "DGC_UNIT_EXECUTION_RESPONSE_V1",
        "entrypoint_path": "scripts/fixture_adapter.py",
        "entrypoint_sha256": sha256_file(adapter),
        "argv": [sys.executable, "scripts/fixture_adapter.py"],
        "timeout_seconds": 10,
        "allowed_environment_variables": [],
    }
    executor_manifest.write_text(json.dumps(executor_doc), encoding="utf-8")

    spec = DistributedEvalSpec(
        experiment_id="exec-fixture",
        task_ids=("task-1",),
        policy_ids=("B0", "DGC"),
        replicates=1,
        max_attempts_per_unit=1,
        lease_ttl_ticks=10,
        max_cost_per_unit_usd=1.0,
        global_budget_usd=2.0,
        harness_digest=h("1"),
        statistical_plan_digest=h("2"),
    )
    policy_rows = []
    policy_dir = repo / "policies"
    policy_dir.mkdir()
    for policy_id in ("B0", "DGC"):
        implementation = policy_dir / f"{policy_id}.py"
        implementation.write_text(f"POLICY_ID = {policy_id!r}\n", encoding="utf-8")
        config = policy_dir / f"{policy_id}.config.json"
        config.write_text(json.dumps({"policy_id": policy_id}, sort_keys=True) + "\n", encoding="utf-8")
        manifest = policy_dir / f"{policy_id}.manifest.json"
        manifest_doc = {
            "schema": "DGC_GOVERNANCE_POLICY_MANIFEST_V1",
            "policy_id": policy_id,
            "implementation_path": implementation.relative_to(repo).as_posix(),
            "implementation_sha256": sha256_file(implementation),
            "config_path": config.relative_to(repo).as_posix(),
            "config_sha256": sha256_file(config),
        }
        manifest.write_text(json.dumps(manifest_doc, sort_keys=True), encoding="utf-8")
        policy_rows.append({
            "policy_id": policy_id,
            "path": manifest.relative_to(repo).as_posix(),
            "sha256": sha256_file(manifest),
            "implementation_path": implementation.relative_to(repo).as_posix(),
            "implementation_sha256": sha256_file(implementation),
            "config_path": config.relative_to(repo).as_posix(),
            "config_sha256": sha256_file(config),
        })

    execution = {
        "family_id": "FAM",
        "repository_commit": "a" * 40,
        "repository_tree": "b" * 40,
        "materialization_reference_digest": h("3"),
        "task_manifest_digest": h("4"),
        "freeze_digest": h("7"),
        "components": [{
            "component": "executor_manifest",
            "path": "manifests/executor.json",
            "sha256": sha256_file(executor_manifest),
            "bytes": executor_manifest.stat().st_size,
            "schema": "DGC_EXECUTOR_MANIFEST_V1",
        }],
        "governance_policies": policy_rows,
    }
    harness = {
        "family_id": "FAM",
        "execution_manifest_freeze_digest": h("7"),
        "harness_freeze_digest": h("a"),
    }
    authority = {
        "family_id": "FAM",
        "generation_id": "gen-1",
        "authority_digest": h("5"),
        "root_digest": h("6"),
        "execution_manifest_freeze_digest": h("7"),
        "harness_freeze_digest": h("a"),
        "distributed_spec_digest": spec.digest,
        "distributed_spec": {
            "experiment_id": spec.experiment_id,
            "task_ids": list(spec.task_ids),
            "policy_ids": list(spec.policy_ids),
            "replicates": spec.replicates,
            "max_attempts_per_unit": spec.max_attempts_per_unit,
            "lease_ttl_ticks": spec.lease_ttl_ticks,
            "max_cost_per_unit_usd": spec.max_cost_per_unit_usd,
            "global_budget_usd": spec.global_budget_usd,
            "harness_digest": spec.harness_digest,
            "statistical_plan_digest": spec.statistical_plan_digest,
        },
        "root": {"root_digest": h("6")},
    }
    materialization = tmp_path / "materialization"
    materialization.mkdir()
    return repo, adapter, execution, harness, authority, materialization


def _patch(monkeypatch: pytest.MonkeyPatch, execution: dict, harness: dict, authority: dict):
    monkeypatch.setattr(executor_module, "verify_execution_manifest_freeze_document", lambda _: execution)
    monkeypatch.setattr(executor_module, "verify_harness_freeze_document", lambda _: harness)
    monkeypatch.setattr(executor_module, "verify_confirmatory_root_authority_document", lambda _: authority)
    monkeypatch.setattr(executor_module, "_assert_git_identity", lambda *_: None)
    monkeypatch.setattr(executor_module, "verify_materialization_generation", lambda *_, **__: _Reference())
    monkeypatch.setattr(bundle_module, "verify_confirmatory_root_authority_document", lambda _: authority)


def test_frozen_panel_executor_builds_self_replayable_complete_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, _, execution, harness, authority, materialization = _subjects(tmp_path)
    _patch(monkeypatch, execution, harness, authority)
    output = tmp_path / "bundle"
    result = execute_frozen_panel(
        repository_root=repo,
        execution_manifest_freeze_path=tmp_path / "execution.json",
        harness_freeze_path=tmp_path / "harness.json",
        confirmatory_root_authority_path=tmp_path / "root.json",
        materialization_generation_root=materialization,
        source_registry_path=tmp_path / "registry.json",
        output_root=output,
    )
    assert result == output
    verified = verify_execution_bundle(output, confirmatory_root_authority_path=tmp_path / "root.json")
    assert verified.completion.complete is True
    assert verified.completion.expected_units == 2
    assert verified.completion.committed_units == 2
    assert len(verified.results) == 2
    assert all(row.actual_cost_usd == 0.25 for row in verified.results)
    assert (output / "AUDIT_LOG.json").is_file()
    assert (output / "EXECUTION_BUNDLE.json").is_file()


def test_entrypoint_byte_drift_is_rejected_before_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, adapter, execution, harness, authority, materialization = _subjects(tmp_path)
    _patch(monkeypatch, execution, harness, authority)
    adapter.write_text("raise SystemExit(99)\n", encoding="utf-8")
    with pytest.raises(FrozenPanelExecutionError, match="entrypoint bytes differ"):
        execute_frozen_panel(
            repository_root=repo,
            execution_manifest_freeze_path=tmp_path / "execution.json",
            harness_freeze_path=tmp_path / "harness.json",
            confirmatory_root_authority_path=tmp_path / "root.json",
            materialization_generation_root=materialization,
            source_registry_path=tmp_path / "registry.json",
            output_root=tmp_path / "bundle",
        )


def test_policy_implementation_byte_drift_is_rejected_before_unit_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, _, execution, harness, authority, materialization = _subjects(tmp_path)
    _patch(monkeypatch, execution, harness, authority)
    (repo / "policies" / "B0.py").write_text("POLICY_ID = 'tampered'\n", encoding="utf-8")
    with pytest.raises(FrozenPanelExecutionError, match="governance implementation bytes differ"):
        execute_frozen_panel(
            repository_root=repo,
            execution_manifest_freeze_path=tmp_path / "execution.json",
            harness_freeze_path=tmp_path / "harness.json",
            confirmatory_root_authority_path=tmp_path / "root.json",
            materialization_generation_root=materialization,
            source_registry_path=tmp_path / "registry.json",
            output_root=tmp_path / "bundle",
        )


def test_invalid_adapter_evidence_fails_closed_without_publishing_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, _, execution, harness, authority, materialization = _subjects(tmp_path, valid_adapter=False)
    _patch(monkeypatch, execution, harness, authority)
    output = tmp_path / "bundle"
    with pytest.raises(FrozenPanelExecutionError, match="cannot claim remaining frozen units"):
        execute_frozen_panel(
            repository_root=repo,
            execution_manifest_freeze_path=tmp_path / "execution.json",
            harness_freeze_path=tmp_path / "harness.json",
            confirmatory_root_authority_path=tmp_path / "root.json",
            materialization_generation_root=materialization,
            source_registry_path=tmp_path / "registry.json",
            output_root=output,
        )
    assert not output.exists()
