from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

import cwc.governance.execution_evidence_bundle as bundle_module
import cwc.governance.frozen_panel_executor as executor_module
from cwc.governance.distributed_eval_control import DistributedEvalSpec
from cwc.governance.cost_accounting import ProviderRateCard
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


def _adapter_source(
    *,
    rate_card_digest: str,
    valid: bool = True,
    incomplete_cost: bool = False,
    mismatched_cost: bool = False,
    bad_rate_card: bool = False,
) -> str:
    trace = '{"provider_request_id":"req-" + req["unit"]["policy_id"]}' if valid else "{}"
    components = [
        "router_usd", "countermodel_usd", "retrieval_usd", "tools_usd",
        "verification_usd", "human_review_usd", "infra_usd", "retry_usd", "failure_loss_usd",
    ]
    if incomplete_cost:
        components = components[:-1]
    rows = []
    for name in components:
        rows.append(
            repr(name)
            + ": {"
            + repr("value_usd") + ": 0.0, "
            + repr("authority") + ": " + repr("ZERO_BY_CONTRACT") + ", "
            + repr("source_digest") + ": " + repr("a" * 64)
            + "}"
        )
    cost_literal = "{" + ", ".join(rows) + "}"
    declared_cost = 0.5 if mismatched_cost else 0.25
    frozen_rate = "f" * 64 if bad_rate_card else rate_card_digest
    return f"""
import json
import sys
req = json.load(sys.stdin)
decision_id = (
    req["unit"]["task_id"] + "::"
    + req["unit"]["policy_id"] + "::"
    + str(req["unit"]["replicate"])
)
provider_request_id = "req-" + req["unit"]["policy_id"]
response = {{
    "schema": "DGC_UNIT_EXECUTION_RESPONSE_V1",
    "unit": req["unit"],
    "attempt": req["attempt"],
    "quality": 0.8,
    "catastrophic_regret": 0.99,
    "risk_signal": 0.1,
    "actual_cost_usd": {declared_cost},
    "provider_usage_traces": [{{
        "trace_id": "trace-" + decision_id,
        "decision_id": decision_id,
        "policy_id": req["unit"]["policy_id"],
        "authority": "PROVIDER_LIVE",
        "provider": "provider",
        "model": "model",
        "model_version": "2026-08-23-r1",
        "rate_card_digest": "{frozen_rate}",
        "input_tokens": 250000,
        "cached_input_tokens": 0,
        "cache_write_tokens": 0,
        "long_cache_write_tokens": 0,
        "output_tokens": 0,
        "provider_request_id": provider_request_id,
    }}],
    "physical_cost_evidence": {cost_literal},
    "trace": {trace},
}}
sys.stdout.write(json.dumps(response, sort_keys=True))
"""
def _subjects(
    tmp_path: Path,
    *,
    valid_adapter: bool = True,
    incomplete_cost: bool = False,
    mismatched_cost: bool = False,
    bad_rate_card: bool = False,
):
    repo = tmp_path / "repo"
    repo.mkdir()
    scripts = repo / "scripts"
    scripts.mkdir()
    rate_card = ProviderRateCard(
        provider="provider",
        model="model",
        input_usd_per_million=1.0,
        cached_input_usd_per_million=0.1,
        cache_write_usd_per_million=1.25,
        long_cache_write_usd_per_million=1.25,
        output_usd_per_million=2.0,
        source_uri="https://example.invalid/provider/model/pricing",
        retrieved_at="2026-08-23T00:00:00Z",
    )
    adapter = scripts / "fixture_adapter.py"
    adapter.write_text(
        _adapter_source(
            rate_card_digest=rate_card.digest,
            valid=valid_adapter,
            incomplete_cost=incomplete_cost,
            mismatched_cost=mismatched_cost,
            bad_rate_card=bad_rate_card,
        ),
        encoding="utf-8",
    )

    manifest_dir = repo / "manifests"
    manifest_dir.mkdir()
    pricing_manifest = manifest_dir / "pricing.json"
    pricing_doc = {
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
    }
    pricing_manifest.write_text(json.dumps(pricing_doc), encoding="utf-8")
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

    risk_impl = scripts / "fixture_risk.py"
    risk_impl.write_text(
        """
import json
import sys
req = json.load(sys.stdin)
response = {
    "schema": "DGC_RISK_ENDPOINT_RESPONSE_V1",
    "catastrophic_regret": float(req["adapter_response"]["risk_signal"]),
    "evidence": {
        "source_field": "risk_signal",
        "source_value": req["adapter_response"]["risk_signal"],
    },
}
sys.stdout.write(json.dumps(response, sort_keys=True))
""",
        encoding="utf-8",
    )
    risk_manifest = manifest_dir / "risk.json"
    risk_doc = {
        "schema": "DGC_RISK_ENDPOINT_MANIFEST_V1",
        "endpoint_name": "catastrophic_regret",
        "scale": "[0,1]",
        "semantics_version": "fixture-v1",
        "protocol": "DGC_RISK_ENDPOINT_EXECUTION_PROTOCOL_V1",
        "request_schema": "DGC_RISK_ENDPOINT_REQUEST_V1",
        "response_schema": "DGC_RISK_ENDPOINT_RESPONSE_V1",
        "implementation_path": "scripts/fixture_risk.py",
        "implementation_sha256": sha256_file(risk_impl),
        "argv": [sys.executable, "scripts/fixture_risk.py"],
        "timeout_seconds": 10,
        "source_fields": ["risk_signal"],
        "policy_outcome_independent_definition": True,
        "post_outcome_relabeling_allowed": False,
        "network_access_allowed": False,
    }
    risk_manifest.write_text(json.dumps(risk_doc), encoding="utf-8")

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
        "components": [
            {
                "component": "executor_manifest",
                "path": "manifests/executor.json",
                "sha256": sha256_file(executor_manifest),
                "bytes": executor_manifest.stat().st_size,
                "schema": "DGC_EXECUTOR_MANIFEST_V1",
            },
            {
                "component": "pricing_snapshot",
                "path": "manifests/pricing.json",
                "sha256": sha256_file(pricing_manifest),
                "bytes": pricing_manifest.stat().st_size,
                "schema": "DGC_PRICING_SNAPSHOT_V1",
            },
            {
                "component": "risk_endpoint_manifest",
                "path": "manifests/risk.json",
                "sha256": sha256_file(risk_manifest),
                "bytes": risk_manifest.stat().st_size,
                "schema": "DGC_RISK_ENDPOINT_MANIFEST_V1",
            },
        ],
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
    assert all(row.catastrophic_regret == pytest.approx(0.1) for row in verified.results)
    assert all(row.catastrophic_regret != pytest.approx(0.99) for row in verified.results)
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


def test_risk_implementation_byte_drift_is_rejected_before_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, _, execution, harness, authority, materialization = _subjects(tmp_path)
    _patch(monkeypatch, execution, harness, authority)
    (repo / "scripts" / "fixture_risk.py").write_text("raise SystemExit(23)\n", encoding="utf-8")
    with pytest.raises(FrozenPanelExecutionError, match="risk endpoint implementation bytes differ"):
        execute_frozen_panel(
            repository_root=repo,
            execution_manifest_freeze_path=tmp_path / "execution.json",
            harness_freeze_path=tmp_path / "harness.json",
            confirmatory_root_authority_path=tmp_path / "root.json",
            materialization_generation_root=materialization,
            source_registry_path=tmp_path / "registry.json",
            output_root=tmp_path / "bundle",
        )


def test_incomplete_physical_cost_evidence_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, _, execution, harness, authority, materialization = _subjects(
        tmp_path, incomplete_cost=True
    )
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


def test_declared_cost_mismatch_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, _, execution, harness, authority, materialization = _subjects(
        tmp_path, mismatched_cost=True
    )
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


def test_unfrozen_provider_rate_card_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, _, execution, harness, authority, materialization = _subjects(
        tmp_path, bad_rate_card=True
    )
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
