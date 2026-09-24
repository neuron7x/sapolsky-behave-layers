from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

from cwc.governance.calibration_variance import CalibrationObservation
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes
from cwc.governance.product_statistical_plan import ProductStatisticalPlan
from cwc.governance.trial_sizing_authority import TrialSizingAuthorityError, authorize_trial_sizing
from cwc.governance.trial_sizing_receipt import freeze_cluster_aware_trial_sizing


def h(char: str) -> str:
    return char * 64


def write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def docs(tmp_path: Path):
    plan = ProductStatisticalPlan()
    execution_payload = {
        "family_id": "SWE_BENCH_VERIFIED",
        "repository_commit": "a" * 40,
        "repository_tree": "b" * 40,
        "materialization_reference_path": "eval_bundle/materialization.json",
        "materialization_reference_digest": h("1"),
        "materialized_tree_sha256": h("2"),
        "task_manifest_digest": h("3"),
        "statistical_plan_digest": plan.digest,
        "statistical_plan": asdict(plan),
        "components": [],
        "governance_policies": [],
        "prebaseline_comparison_digest": h("4"),
    }
    execution_digest = sha256_bytes(canonical_json_bytes(execution_payload))
    execution = write(tmp_path / "execution.json", {
        "schema": "DGC_EXECUTION_MANIFEST_FREEZE_V1",
        **execution_payload,
        "freeze_digest": execution_digest,
        "baseline_panel_bound": False,
        "harness_frozen": False,
        "confirmatory_execution_authorized": False,
        "product_promotion_authorized": False,
    })

    partition_payload = {
        "family_id": "SWE_BENCH_VERIFIED",
        "materialization_reference_digest": h("1"),
        "task_manifest_digest": h("3"),
        "task_count": 8,
        "calibration_task_ids": ["c1", "c2", "c3"],
        "confirmatory_task_ids": ["q1", "q2", "q3", "q4", "q5"],
        "calibration_task_digest": sha256_bytes(canonical_json_bytes(("c1", "c2", "c3"))),
        "confirmatory_task_digest": sha256_bytes(canonical_json_bytes(("q1", "q2", "q3", "q4", "q5"))),
        "statistical_plan_digest": plan.digest,
        "calibration_fraction": plan.calibration_fraction,
    }
    partition_digest = sha256_bytes(canonical_json_bytes(partition_payload))
    partition = write(tmp_path / "partition.json", {
        "schema": "DGC_TASK_PARTITION_RECEIPT_V1",
        **partition_payload,
        "receipt_digest": partition_digest,
        "outcomes_observed": False,
        "confirmatory_execution_authorized": False,
        "product_promotion_authorized": False,
    })

    b2_payload = {
        "family_id": "SWE_BENCH_VERIFIED",
        "execution_manifest_freeze_digest": execution_digest,
        "task_partition_receipt_digest": partition_digest,
        "fit_input_sha256": h("5"),
        "fit_receipt_sha256": h("6"),
        "feature_schema_digest": h("7"),
        "training_algorithm_digest": h("8"),
        "calibration_task_digest": partition_payload["calibration_task_digest"],
        "confirmatory_task_digest": partition_payload["confirmatory_task_digest"],
        "fitted_model_digest": h("9"),
        "calibration_task_count": 3,
    }
    b2_digest = sha256_bytes(canonical_json_bytes(b2_payload))
    b2 = write(tmp_path / "b2.json", {
        "schema": "DGC_B2_FIT_AUTHORITY_V1",
        **b2_payload,
        "authority_digest": b2_digest,
        "confirmatory_execution_authorized": False,
        "product_promotion_authorized": False,
    })

    harness_payload = {
        "family_id": "SWE_BENCH_VERIFIED",
        "execution_manifest_freeze_digest": execution_digest,
        "b2_fit_authority_digest": b2_digest,
        "baseline_panel_input_sha256": h("a"),
        "baseline_panel_digest": h("b"),
        "baseline_specs": [],
        "comparison_frame_digest": h("c"),
        "policy_harnesses": [
            {"policy_id": policy, "governance_policy_digest": h(char), "harness_full_digest": h(full)}
            for policy, char, full in zip(
                ("B0", "B1", "B2", "B3", "DGC"),
                "def01",
                "23456",
                strict=True,
            )
        ],
    }
    harness_digest = sha256_bytes(canonical_json_bytes(harness_payload))
    harness = write(tmp_path / "harness.json", {
        "schema": "DGC_HARNESS_FREEZE_V1",
        **harness_payload,
        "harness_freeze_digest": harness_digest,
        "harness_frozen": True,
        "confirmatory_execution_authorized": False,
        "product_promotion_authorized": False,
    })
    return plan, execution, partition, b2, harness


def sizing_files(tmp_path: Path, plan: ProductStatisticalPlan, *, replace_task: str | None = None):
    calibration = ["c1", "c2", "c3"]
    if replace_task is not None:
        calibration[-1] = replace_task
    observations = []
    for comparison_index, comparison in enumerate(("cost-vs-B0", "quality-vs-B0")):
        for task_index, task in enumerate(calibration):
            for replicate in range(2):
                observations.append(CalibrationObservation(
                    comparison_id=comparison,
                    task_id=task,
                    replicate=replicate,
                    value=0.10 * comparison_index + 0.01 * task_index + 0.001 * replicate,
                ))
    effects = {"cost-vs-B0": 0.5, "quality-vs-B0": 0.5}
    input_payload = {
        "schema": "DGC_CLUSTER_AWARE_TRIAL_SIZING_INPUT_V1",
        "plan": asdict(plan),
        "observations": [asdict(row) for row in observations],
        "effects_of_interest": effects,
        "confirmatory_task_count": 5,
    }
    input_path = write(tmp_path / "sizing-input.json", input_payload)
    receipt = freeze_cluster_aware_trial_sizing(
        observations=observations,
        effects_of_interest=effects,
        confirmatory_task_count=5,
        plan=plan,
    )
    receipt_path = write(tmp_path / "sizing-receipt.json", asdict(receipt))
    return input_path, receipt_path


def test_trial_sizing_authority_recomputes_exact_calibration_design(tmp_path: Path):
    plan, execution, partition, b2, harness = docs(tmp_path)
    sizing_input, sizing_receipt = sizing_files(tmp_path, plan)
    authority = authorize_trial_sizing(
        execution_manifest_freeze_path=execution,
        b2_fit_authority_path=b2,
        harness_freeze_path=harness,
        task_partition_path=partition,
        sizing_input_path=sizing_input,
        sizing_receipt_path=sizing_receipt,
    )
    assert authority.family_id == "SWE_BENCH_VERIFIED"
    assert authority.confirmatory_task_count == 5
    assert authority.required_trials_per_task >= plan.min_trials_per_task
    assert authority.comparison_count == 2


def test_trial_sizing_rejects_task_substitution_from_confirmatory_population(tmp_path: Path):
    plan, execution, partition, b2, harness = docs(tmp_path)
    sizing_input, sizing_receipt = sizing_files(tmp_path, plan, replace_task="q1")
    with pytest.raises(TrialSizingAuthorityError, match="exact frozen calibration task population"):
        authorize_trial_sizing(
            execution_manifest_freeze_path=execution,
            b2_fit_authority_path=b2,
            harness_freeze_path=harness,
            task_partition_path=partition,
            sizing_input_path=sizing_input,
            sizing_receipt_path=sizing_receipt,
        )


def test_trial_sizing_rejects_forged_receipt_even_when_input_is_valid(tmp_path: Path):
    plan, execution, partition, b2, harness = docs(tmp_path)
    sizing_input, sizing_receipt = sizing_files(tmp_path, plan)
    forged = json.loads(sizing_receipt.read_text())
    forged["required_trials_per_task"] += 1
    write(sizing_receipt, forged)
    with pytest.raises(TrialSizingAuthorityError, match="does not equal deterministic recomputation"):
        authorize_trial_sizing(
            execution_manifest_freeze_path=execution,
            b2_fit_authority_path=b2,
            harness_freeze_path=harness,
            task_partition_path=partition,
            sizing_input_path=sizing_input,
            sizing_receipt_path=sizing_receipt,
        )
