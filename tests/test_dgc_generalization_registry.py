from __future__ import annotations

import json
from pathlib import Path

import pytest

from cwc.governance.generalization_registry import (
    AXIS_SCHEMA,
    GeneralizationAxis,
    GeneralizationRegistryError,
    REQUIRED_BASELINE_ROLES,
    build_generalization_registry,
    recompute_generalization_registry_from_document,
    verify_generalization_registry_document,
)
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes
from cwc.governance.product_statistical_plan import ProductStatisticalPlan, deterministic_three_way_task_split


def h(char: str) -> str:
    return char * 64


def task_digest(values) -> str:
    return sha256_bytes(canonical_json_bytes(tuple(sorted(values))))


def write(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def execution_doc(path: Path) -> Path:
    plan = ProductStatisticalPlan()
    component_names = (
        "model_manifest", "prompt_policy", "tool_manifest", "environment",
        "budget", "pricing_snapshot", "scorer",
    )
    components = [
        {"component": name, "path": f"m/{name}.json", "sha256": h(char), "bytes": 10, "schema": "x"}
        for name, char in zip(component_names, "1234567", strict=True)
    ]
    policies = [
        {
            "policy_id": policy_id,
            "path": f"p/{policy_id}.json",
            "sha256": h(char),
            "implementation_sha256": h("a"),
            "config_sha256": h("b"),
        }
        for policy_id, char in zip(("B0", "B1", "B2", "B3", "DGC"), "89abc", strict=True)
    ]
    payload = {
        "family_id": "SWE_BENCH_VERIFIED",
        "repository_commit": "a" * 40,
        "repository_tree": "b" * 40,
        "materialization_reference_path": "eval_bundle/materialization.json",
        "materialization_reference_digest": h("d"),
        "materialized_tree_sha256": h("e"),
        "task_manifest_digest": h("f"),
        "statistical_plan_digest": plan.digest,
        "statistical_plan": {
            "family_count": plan.family_count,
            "baseline_count": plan.baseline_count,
            "endpoint_count": plan.endpoint_count,
            "familywise_alpha": plan.familywise_alpha,
            "quality_noninferiority_margin": plan.quality_noninferiority_margin,
            "catastrophic_regret_noninferiority_margin": plan.catastrophic_regret_noninferiority_margin,
            "minimum_cost_effect_of_interest": plan.minimum_cost_effect_of_interest,
            "calibration_fraction": plan.calibration_fraction,
            "generalization_holdout_fraction": plan.generalization_holdout_fraction,
            "target_power": plan.target_power,
            "min_trials_per_task": plan.min_trials_per_task,
            "max_trials_per_task": plan.max_trials_per_task,
            "method": plan.method,
        },
        "components": components,
        "governance_policies": policies,
        "prebaseline_comparison_digest": h("0"),
    }
    return write(path, {
        "schema": "DGC_EXECUTION_MANIFEST_FREEZE_V1",
        **payload,
        "freeze_digest": sha256_bytes(canonical_json_bytes(payload)),
        "baseline_panel_bound": False,
        "harness_frozen": False,
        "confirmatory_execution_authorized": False,
        "product_promotion_authorized": False,
    })


def partition_doc(path: Path, *, execution_path: Path) -> Path:
    execution = json.loads(execution_path.read_text())
    plan = ProductStatisticalPlan()
    tasks = tuple(f"task-{i:03d}" for i in range(100))
    calibration, confirmatory, g1 = deterministic_three_way_task_split(
        tasks,
        calibration_fraction=plan.calibration_fraction,
        generalization_holdout_fraction=plan.generalization_holdout_fraction,
    )
    payload = {
        "family_id": execution["family_id"],
        "materialization_reference_digest": execution["materialization_reference_digest"],
        "task_manifest_digest": task_digest(tasks),
        "task_count": len(tasks),
        "calibration_task_ids": calibration,
        "confirmatory_task_ids": confirmatory,
        "generalization_task_ids": g1,
        "calibration_task_digest": task_digest(calibration),
        "confirmatory_task_digest": task_digest(confirmatory),
        "generalization_task_digest": task_digest(g1),
        "statistical_plan_digest": plan.digest,
        "calibration_fraction": plan.calibration_fraction,
        "generalization_holdout_fraction": plan.generalization_holdout_fraction,
    }
    return write(path, {
        "schema": "DGC_TASK_PARTITION_RECEIPT_V2",
        **payload,
        "receipt_digest": sha256_bytes(canonical_json_bytes(payload)),
        "outcomes_observed": False,
        "generalization_outcomes_observed": False,
        "confirmatory_execution_authorized": False,
        "generalization_execution_authorized": False,
        "product_promotion_authorized": False,
    })


def role_map() -> dict[str, str]:
    return {
        "B0_FIXED_COMPUTE": "B0",
        "B1_UNCERTAINTY_ROUTER": "B1",
        "B2_LEARNED_COST_QUALITY_ROUTER": "B2",
        "B3_SEQUENTIAL_VERIFICATION": "B3",
        "DGC": "DGC",
    }


def axis_docs(root: Path, *, partition_path: Path) -> dict[GeneralizationAxis, Path]:
    partition = json.loads(partition_path.read_text())
    plan = ProductStatisticalPlan()
    g1 = partition["generalization_task_digest"]
    common = {
        "schema": AXIS_SCHEMA,
        "source_authority_digest": h("d"),
        "base_task_population_digest": g1,
        "model_manifest_digest": h("1"),
        "pricing_snapshot_digest": h("6"),
        "scorer_digest": h("7"),
        "perturbation_manifest_digest": h("0"),
        "reference_baseline_roles": list(REQUIRED_BASELINE_ROLES),
        "quality_noninferiority_margin": plan.quality_noninferiority_margin,
        "catastrophic_noninferiority_margin": plan.catastrophic_regret_noninferiority_margin,
        "cost_effect_direction": "BASELINE_MINUS_DGC_POSITIVE",
        "outcomes_observed": False,
        "policy_retuning_allowed": False,
    }
    rows = {
        GeneralizationAxis.UNSEEN_TASKS: {
            **common,
            "axis": GeneralizationAxis.UNSEEN_TASKS.value,
            "evaluation_manifest_digest": h("1"),
            "source_family_id": "SWE_BENCH_VERIFIED",
            "task_population_digest": g1,
        },
        GeneralizationAxis.UNSEEN_DOMAIN: {
            **common,
            "axis": GeneralizationAxis.UNSEEN_DOMAIN.value,
            "evaluation_manifest_digest": h("2"),
            "source_family_id": "TERMINAL_BENCH_2_1",
            "task_population_digest": h("9"),
            "base_task_population_digest": h("9"),
        },
        GeneralizationAxis.UNSEEN_MODEL_PROVIDER: {
            **common,
            "axis": GeneralizationAxis.UNSEEN_MODEL_PROVIDER.value,
            "evaluation_manifest_digest": h("3"),
            "source_family_id": "SWE_BENCH_VERIFIED",
            "task_population_digest": g1,
            "model_manifest_digest": h("e"),
        },
        GeneralizationAxis.CHANGED_ECONOMICS: {
            **common,
            "axis": GeneralizationAxis.CHANGED_ECONOMICS.value,
            "evaluation_manifest_digest": h("4"),
            "source_family_id": "SWE_BENCH_VERIFIED",
            "task_population_digest": g1,
            "pricing_snapshot_digest": h("e"),
        },
        GeneralizationAxis.PERTURBATION_SHIFT: {
            **common,
            "axis": GeneralizationAxis.PERTURBATION_SHIFT.value,
            "evaluation_manifest_digest": h("5"),
            "source_family_id": "SWE_BENCH_VERIFIED",
            "task_population_digest": h("a"),
            "perturbation_manifest_digest": h("f"),
        },
    }
    result = {}
    for index, axis in enumerate(GeneralizationAxis, start=1):
        rel = Path("eval_bundle") / f"g{index}.json"
        write(root / rel, rows[axis])
        result[axis] = rel
    return result


def fixture(tmp_path: Path):
    execution = execution_doc(tmp_path / "execution.json")
    partition_rel = Path("eval_bundle/task-partition.json")
    partition = partition_doc(tmp_path / partition_rel, execution_path=execution)
    axes = axis_docs(tmp_path, partition_path=partition)
    return execution, partition_rel, axes


def build(tmp_path: Path):
    execution, partition_rel, axes = fixture(tmp_path)
    authority = build_generalization_registry(
        repository_root=tmp_path,
        execution_manifest_freeze_path=execution,
        task_partition_path=partition_rel,
        axis_manifest_paths=axes,
        policy_role_bindings=role_map(),
    )
    return authority, execution, partition_rel, axes


def test_registry_freezes_exact_g1_g5_before_outcomes(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    authority, execution, _, _ = build(tmp_path)
    assert len(authority.axes) == 5
    assert authority.per_claim_alpha == pytest.approx(0.05 / 60.0)
    assert authority.g1_holdout_task_digest != authority.primary_confirmatory_task_digest
    output = write(tmp_path / "eval_bundle/registry.json", authority.document)
    verified = verify_generalization_registry_document(output)
    assert verified["policy_retuning_allowed"] is False
    rebuilt = recompute_generalization_registry_from_document(
        repository_root=tmp_path,
        execution_manifest_freeze_path=execution,
        registry_path=output,
    )
    assert rebuilt.registry_digest == authority.registry_digest


def test_g3_without_model_provider_shift_is_rejected(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    execution, partition_rel, axes = fixture(tmp_path)
    g3 = tmp_path / axes[GeneralizationAxis.UNSEEN_MODEL_PROVIDER]
    doc = json.loads(g3.read_text())
    doc["model_manifest_digest"] = h("1")
    write(g3, doc)
    with pytest.raises(GeneralizationRegistryError, match="distinct frozen model/provider"):
        build_generalization_registry(
            repository_root=tmp_path,
            execution_manifest_freeze_path=execution,
            task_partition_path=partition_rel,
            axis_manifest_paths=axes,
            policy_role_bindings=role_map(),
        )


def test_g4_without_economic_shift_is_rejected(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    execution, partition_rel, axes = fixture(tmp_path)
    g4 = tmp_path / axes[GeneralizationAxis.CHANGED_ECONOMICS]
    doc = json.loads(g4.read_text())
    doc["pricing_snapshot_digest"] = h("6")
    write(g4, doc)
    with pytest.raises(GeneralizationRegistryError, match="distinct frozen pricing"):
        build_generalization_registry(
            repository_root=tmp_path,
            execution_manifest_freeze_path=execution,
            task_partition_path=partition_rel,
            axis_manifest_paths=axes,
            policy_role_bindings=role_map(),
        )


def test_g5_without_perturbed_population_identity_is_rejected(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    execution, partition_rel, axes = fixture(tmp_path)
    g5 = tmp_path / axes[GeneralizationAxis.PERTURBATION_SHIFT]
    doc = json.loads(g5.read_text())
    doc["task_population_digest"] = doc["base_task_population_digest"]
    write(g5, doc)
    with pytest.raises(GeneralizationRegistryError, match="perturbed population identity"):
        build_generalization_registry(
            repository_root=tmp_path,
            execution_manifest_freeze_path=execution,
            task_partition_path=partition_rel,
            axis_manifest_paths=axes,
            policy_role_bindings=role_map(),
        )


def test_post_freeze_axis_manifest_mutation_breaks_registry_replay(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    authority, execution, _, axes = build(tmp_path)
    output = write(tmp_path / "eval_bundle/registry.json", authority.document)
    g2 = tmp_path / axes[GeneralizationAxis.UNSEEN_DOMAIN]
    doc = json.loads(g2.read_text())
    doc["evaluation_manifest_digest"] = h("f")
    write(g2, doc)
    with pytest.raises(GeneralizationRegistryError, match="differs from subject recomputation"):
        recompute_generalization_registry_from_document(
            repository_root=tmp_path,
            execution_manifest_freeze_path=execution,
            registry_path=output,
        )


def test_policy_role_drift_is_rejected(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    execution, partition_rel, axes = fixture(tmp_path)
    roles = role_map()
    roles["DGC"], roles["B0_FIXED_COMPUTE"] = roles["B0_FIXED_COMPUTE"], roles["DGC"]
    authority = build_generalization_registry(
        repository_root=tmp_path,
        execution_manifest_freeze_path=execution,
        task_partition_path=partition_rel,
        axis_manifest_paths=axes,
        policy_role_bindings=roles,
    )
    assert dict(authority.policy_role_bindings)["DGC"] == "B0"
