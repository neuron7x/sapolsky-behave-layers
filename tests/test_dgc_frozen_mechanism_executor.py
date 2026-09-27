from __future__ import annotations

import json
from pathlib import Path

import pytest

import cwc.governance.frozen_mechanism_executor as executor_module
from cwc.governance.cost_accounting import ProviderRateCard
from cwc.governance.distributed_eval_control import DistributedEvalSpec
from cwc.governance.frozen_mechanism_executor import (
    FrozenMechanismExecutionError,
    _mechanism_request,
    execute_frozen_mechanism_panel,
)


def h(char: str) -> str:
    return char * 64


class _Binding:
    materialized_task_manifest_sha256 = h("4")


class _Reference:
    digest = h("3")

    def binding(self, family_id: str):
        assert family_id == "FAM"
        return _Binding()


def _fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, risk=False, null_request=False):
    repo = tmp_path / "repo"
    repo.mkdir()
    spec = DistributedEvalSpec(
        experiment_id="mechanism-test",
        task_ids=("task-1",),
        policy_ids=("DGC",),
        replicates=1,
        max_attempts_per_unit=1,
        lease_ttl_ticks=3,
        max_cost_per_unit_usd=1.0,
        global_budget_usd=1.0,
        harness_digest=h("1"),
        statistical_plan_digest=h("2"),
    )
    execution = {
        "family_id": "FAM",
        "freeze_digest": h("5"),
        "repository_commit": "a" * 40,
        "repository_tree": "b" * 40,
        "materialization_reference_digest": h("3"),
        "task_manifest_digest": h("4"),
        "components": [{"component": "executor_manifest", "sha256": h("6")}],
        "governance_policies": [{"policy_id": "DGC"}],
    }
    harness = {
        "family_id": "FAM",
        "execution_manifest_freeze_digest": h("5"),
        "harness_freeze_digest": h("7"),
    }
    authority = {
        "family_id": "FAM",
        "authority_digest": h("8"),
        "execution_manifest_freeze_digest": h("5"),
        "harness_freeze_digest": h("7"),
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
    }
    card = ProviderRateCard(
        provider="provider",
        model="model",
        input_usd_per_million=1.0,
        cached_input_usd_per_million=0.1,
        cache_write_usd_per_million=1.25,
        long_cache_write_usd_per_million=1.25,
        output_usd_per_million=2.0,
        source_uri="https://example.invalid/pricing",
        retrieved_at="2026-09-24T00:00:00Z",
    )

    monkeypatch.setattr(executor_module, "verify_execution_manifest_freeze_document", lambda _: execution)
    monkeypatch.setattr(executor_module, "verify_harness_freeze_document", lambda _: harness)
    monkeypatch.setattr(executor_module, "verify_mechanism_execution_authority_document", lambda _: authority)
    monkeypatch.setattr(executor_module, "_assert_git_identity", lambda *_: None)
    monkeypatch.setattr(executor_module, "verify_materialization_generation", lambda *_, **__: _Reference())
    monkeypatch.setattr(
        executor_module,
        "_executor_manifest",
        lambda *_: ({"entrypoint_sha256": h("9"), "allowed_environment_variables": []}, ("python", "adapter.py"), 5.0),
    )
    monkeypatch.setattr(
        executor_module,
        "_pricing_rate_cards",
        lambda *_: ({("provider", "model", "v1"): card}, h("a")),
    )
    monkeypatch.setattr(
        executor_module,
        "_policy_subject",
        lambda **_: {
            "policy_id": "DGC",
            "path": "policies/DGC.json",
            "sha256": h("b"),
        },
    )
    monkeypatch.setattr(
        executor_module,
        "verify_mechanism_execution_bundle",
        lambda *_, **__: True,
    )

    components = [
        "router_usd", "countermodel_usd", "retrieval_usd", "tools_usd",
        "verification_usd", "human_review_usd", "infra_usd", "retry_usd",
        "failure_loss_usd",
    ]

    def invoke(*, request, **_kwargs):
        raw_request_id = None if null_request else "req-1"
        response = {
            "schema": "DGC_UNIT_EXECUTION_RESPONSE_V1",
            "unit": request["unit"],
            "attempt": request["attempt"],
            "quality": 0.8,
            "provider_usage_traces": [{
                "trace_id": "trace-1",
                "decision_id": "task-1::DGC::0",
                "policy_id": "DGC",
                "authority": "PROVIDER_LIVE",
                "provider": "provider",
                "model": "model",
                "model_version": "v1",
                "rate_card_digest": card.digest,
                "input_tokens": 250000,
                "cached_input_tokens": 0,
                "cache_write_tokens": 0,
                "long_cache_write_tokens": 0,
                "output_tokens": 0,
                "provider_request_id": raw_request_id,
            }],
            "physical_cost_evidence": {
                name: {
                    "value_usd": 0.0,
                    "authority": "ZERO_BY_CONTRACT",
                    "source_digest": h("c"),
                }
                for name in components
            },
            "actual_cost_usd": 0.25,
            "trace": {"upstream": h("d")},
        }
        if risk:
            response["catastrophic_regret"] = 0.0
        raw = json.dumps(response, sort_keys=True).encode("utf-8")
        return response, raw, b""

    monkeypatch.setattr(executor_module, "_invoke", invoke)
    materialization = tmp_path / "materialization"
    materialization.mkdir()
    return repo, execution, authority, materialization


def test_mechanism_request_uses_mechanism_authority_not_product_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, execution, authority, _ = _fixture(tmp_path, monkeypatch)
    spec = DistributedEvalSpec(**dict(authority["distributed_spec"]))
    from cwc.governance.distributed_eval_control import DistributedEvalCoordinator
    coordinator = DistributedEvalCoordinator(spec)
    lease = coordinator.claim("worker", tick=0)
    assert lease is not None
    request = _mechanism_request(
        repository_root=repo,
        execution=execution,
        authority=authority,
        lease=lease,
    )
    assert request["authority_kind"] == "MECHANISM_EXECUTION"
    assert request["mechanism_authority_digest"] == authority["authority_digest"]
    assert "root_digest" not in request
    assert "generation_id" not in request


def test_executor_publishes_risk_free_mechanism_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, _, _, materialization = _fixture(tmp_path, monkeypatch)
    output = tmp_path / "mechanism-bundle"
    result = execute_frozen_mechanism_panel(
        repository_root=repo,
        execution_manifest_freeze_path=tmp_path / "execution.json",
        harness_freeze_path=tmp_path / "harness.json",
        mechanism_authority_path=tmp_path / "authority.json",
        materialization_generation_root=materialization,
        source_registry_path=tmp_path / "registry.json",
        output_root=output,
    )
    assert result == output
    manifest = json.loads((output / "MECHANISM_EXECUTION_BUNDLE.json").read_text())
    assert manifest["expected_units"] == 1
    assert manifest["committed_units"] == 1
    assert manifest["risk_qualification_authorized"] is False
    assert manifest["product_promotion_authorized"] is False
    record = json.loads(next((output / "records").glob("*.json")).read_text())
    assert record["result_payload"]["quality"] == pytest.approx(0.8)
    assert "catastrophic_regret" not in record["result_payload"]
    evidence = json.loads(next((output / "evidence").glob("*.json")).read_text())
    assert "risk_endpoint_response" not in evidence


def test_adapter_risk_leakage_prevents_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, _, _, materialization = _fixture(tmp_path, monkeypatch, risk=True)
    output = tmp_path / "mechanism-bundle"
    with pytest.raises(FrozenMechanismExecutionError, match="remaining frozen units"):
        execute_frozen_mechanism_panel(
            repository_root=repo,
            execution_manifest_freeze_path=tmp_path / "execution.json",
            harness_freeze_path=tmp_path / "harness.json",
            mechanism_authority_path=tmp_path / "authority.json",
            materialization_generation_root=materialization,
            source_registry_path=tmp_path / "registry.json",
            output_root=output,
        )
    assert not output.exists()


def test_null_provider_request_id_prevents_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, _, _, materialization = _fixture(tmp_path, monkeypatch, null_request=True)
    output = tmp_path / "mechanism-bundle"
    with pytest.raises(FrozenMechanismExecutionError, match="remaining frozen units"):
        execute_frozen_mechanism_panel(
            repository_root=repo,
            execution_manifest_freeze_path=tmp_path / "execution.json",
            harness_freeze_path=tmp_path / "harness.json",
            mechanism_authority_path=tmp_path / "authority.json",
            materialization_generation_root=materialization,
            source_registry_path=tmp_path / "registry.json",
            output_root=output,
        )
    assert not output.exists()
