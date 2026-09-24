from __future__ import annotations

import json
from pathlib import Path

import pytest

import cwc.governance.mechanism_execution_authority as authority_module
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.mechanism_evidence_plan import MechanismStatisticalPlan
from cwc.governance.mechanism_execution_authority import (
    MechanismExecutionAuthorityError,
    build_mechanism_execution_authority,
    verify_mechanism_execution_authority_document,
)


def h(char: str) -> str:
    return char * 64


def _task_digest(ids):
    return sha256_bytes(canonical_json_bytes(tuple(sorted(ids))))


def _fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    manifests = repo / "manifests"
    manifests.mkdir()
    budget = manifests / "budget.json"
    budget.write_text(
        json.dumps({
            "schema": "DGC_BUDGET_MANIFEST_V1",
            "max_tokens": 100000,
            "max_cost_usd": 2.0,
            "max_wall_time_s": 1200,
            "max_steps": 100,
        }, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    tasks = ("task-a", "task-b", "task-c")
    task_digest = _task_digest(tasks)
    execution = {
        "family_id": "TERMINAL_BENCH_2_1",
        "freeze_digest": h("1"),
        "statistical_plan_digest": h("2"),
        "task_manifest_digest": h("3"),
        "components": [{
            "component": "budget",
            "path": "manifests/budget.json",
            "sha256": sha256_file(budget),
            "bytes": budget.stat().st_size,
            "schema": "DGC_BUDGET_MANIFEST_V1",
        }],
    }
    roles = [
        {"role": "B0_FIXED_COMPUTE", "policy_id": "B0"},
        {"role": "B1_UNCERTAINTY_ROUTER", "policy_id": "B1"},
        {"role": "B2_LEARNED_COST_QUALITY_ROUTER", "policy_id": "B2"},
        {"role": "B3_SEQUENTIAL_VERIFICATION", "policy_id": "B3"},
        {"role": "DGC", "policy_id": "DGC"},
    ]
    harness = {
        "family_id": "TERMINAL_BENCH_2_1",
        "execution_manifest_freeze_digest": h("1"),
        "harness_freeze_digest": h("4"),
        "confirmatory_task_manifest_digest": task_digest,
        "comparison_frame_digest": h("5"),
        "policy_role_bindings": roles,
    }
    partition = {
        "family_id": "TERMINAL_BENCH_2_1",
        "receipt_digest": h("6"),
        "statistical_plan_digest": h("2"),
        "task_manifest_digest": h("3"),
        "confirmatory_task_ids": list(tasks),
        "confirmatory_task_digest": task_digest,
    }
    plan = MechanismStatisticalPlan(min_trials_per_task=2, max_trials_per_task=10)
    sizing = {
        "receipt_digest": h("7"),
        "confirmatory_task_count": len(tasks),
        "required_trials_per_task": 3,
    }

    monkeypatch.setattr(
        authority_module,
        "verify_execution_manifest_freeze_document",
        lambda _: execution,
    )
    monkeypatch.setattr(
        authority_module,
        "verify_harness_freeze_document",
        lambda _: harness,
    )
    monkeypatch.setattr(
        authority_module,
        "verify_task_partition_document",
        lambda _: partition,
    )
    monkeypatch.setattr(
        authority_module,
        "verify_mechanism_trial_sizing_document",
        lambda *_args, **_kwargs: sizing,
    )
    return repo, execution, harness, partition, sizing, plan


def test_authority_binds_exact_mechanism_population_and_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, _, _, _, _, plan = _fixture(tmp_path, monkeypatch)
    authority = build_mechanism_execution_authority(
        repository_root=repo,
        execution_manifest_freeze_path=tmp_path / "execution.json",
        harness_freeze_path=tmp_path / "harness.json",
        task_partition_path=tmp_path / "partition.json",
        mechanism_sizing_path=tmp_path / "sizing.json",
        mechanism_plan=plan,
    )
    assert authority.confirmatory_task_count == 3
    assert authority.required_trials_per_task == 3
    assert authority.distributed_spec["policy_ids"] == ["B0", "B1", "B2", "B3", "DGC"]
    assert authority.distributed_spec["replicates"] == 3
    assert authority.max_cost_per_unit_usd == pytest.approx(2.0)
    assert authority.global_budget_usd == pytest.approx(3 * 5 * 3 * 2.0)
    assert authority.document["mechanism_execution_authorized"] is True
    assert authority.document["risk_qualification_authorized"] is False
    assert authority.document["product_promotion_authorized"] is False
    assert authority.document["commercial_claim_authorized"] is False

    out = tmp_path / "authority.json"
    out.write_text(json.dumps(authority.document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    verified = verify_mechanism_execution_authority_document(out)
    assert verified["distributed_spec_digest"] == authority.distributed_spec_digest


def test_task_population_substitution_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, _, harness, partition, _, plan = _fixture(tmp_path, monkeypatch)
    partition["confirmatory_task_ids"] = ["task-a", "task-b", "task-x"]
    partition["confirmatory_task_digest"] = _task_digest(tuple(partition["confirmatory_task_ids"]))
    harness["confirmatory_task_manifest_digest"] = _task_digest(("task-a", "task-b", "task-c"))
    with pytest.raises(MechanismExecutionAuthorityError, match="differ from final frozen harness"):
        build_mechanism_execution_authority(
            repository_root=repo,
            execution_manifest_freeze_path=tmp_path / "execution.json",
            harness_freeze_path=tmp_path / "harness.json",
            task_partition_path=tmp_path / "partition.json",
            mechanism_sizing_path=tmp_path / "sizing.json",
            mechanism_plan=plan,
        )


def test_sizing_count_mismatch_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, _, _, _, sizing, plan = _fixture(tmp_path, monkeypatch)
    sizing["confirmatory_task_count"] = 4
    with pytest.raises(MechanismExecutionAuthorityError, match="sizing confirmatory count"):
        build_mechanism_execution_authority(
            repository_root=repo,
            execution_manifest_freeze_path=tmp_path / "execution.json",
            harness_freeze_path=tmp_path / "harness.json",
            task_partition_path=tmp_path / "partition.json",
            mechanism_sizing_path=tmp_path / "sizing.json",
            mechanism_plan=plan,
        )


def test_policy_role_substitution_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, _, harness, _, _, plan = _fixture(tmp_path, monkeypatch)
    harness["policy_role_bindings"][0]["role"] = "UNKNOWN_ROLE"
    with pytest.raises(MechanismExecutionAuthorityError, match="not exact B0-B3"):
        build_mechanism_execution_authority(
            repository_root=repo,
            execution_manifest_freeze_path=tmp_path / "execution.json",
            harness_freeze_path=tmp_path / "harness.json",
            task_partition_path=tmp_path / "partition.json",
            mechanism_sizing_path=tmp_path / "sizing.json",
            mechanism_plan=plan,
        )


def test_budget_byte_drift_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, _, _, _, _, plan = _fixture(tmp_path, monkeypatch)
    budget = repo / "manifests" / "budget.json"
    doc = json.loads(budget.read_text())
    doc["max_cost_usd"] = 999
    budget.write_text(json.dumps(doc, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(MechanismExecutionAuthorityError, match="bytes differ"):
        build_mechanism_execution_authority(
            repository_root=repo,
            execution_manifest_freeze_path=tmp_path / "execution.json",
            harness_freeze_path=tmp_path / "harness.json",
            task_partition_path=tmp_path / "partition.json",
            mechanism_sizing_path=tmp_path / "sizing.json",
            mechanism_plan=plan,
        )


def test_illegal_product_authority_flag_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    repo, _, _, _, _, plan = _fixture(tmp_path, monkeypatch)
    authority = build_mechanism_execution_authority(
        repository_root=repo,
        execution_manifest_freeze_path=tmp_path / "execution.json",
        harness_freeze_path=tmp_path / "harness.json",
        task_partition_path=tmp_path / "partition.json",
        mechanism_sizing_path=tmp_path / "sizing.json",
        mechanism_plan=plan,
    )
    doc = authority.document
    doc["product_promotion_authorized"] = True
    out = tmp_path / "illegal.json"
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(MechanismExecutionAuthorityError, match="authority boundary"):
        verify_mechanism_execution_authority_document(out)
