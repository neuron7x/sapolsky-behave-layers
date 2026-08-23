from __future__ import annotations

import json
from pathlib import Path

import pytest

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes
from cwc.governance.product_statistical_plan import ProductStatisticalPlan, deterministic_three_way_task_split
from cwc.governance.task_partition import TaskPartitionError, verify_task_partition_document


def digest_tasks(values) -> str:
    return sha256_bytes(canonical_json_bytes(tuple(sorted(values))))


def write(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def valid_partition_doc() -> dict:
    plan = ProductStatisticalPlan()
    tasks = tuple(f"task-{i:03d}" for i in range(100))
    calibration, confirmatory, generalization = deterministic_three_way_task_split(
        tasks,
        calibration_fraction=plan.calibration_fraction,
        generalization_holdout_fraction=plan.generalization_holdout_fraction,
    )
    payload = {
        "family_id": "SWE_BENCH_VERIFIED",
        "materialization_reference_digest": "a" * 64,
        "task_manifest_digest": digest_tasks(tasks),
        "task_count": len(tasks),
        "calibration_task_ids": calibration,
        "confirmatory_task_ids": confirmatory,
        "generalization_task_ids": generalization,
        "calibration_task_digest": digest_tasks(calibration),
        "confirmatory_task_digest": digest_tasks(confirmatory),
        "generalization_task_digest": digest_tasks(generalization),
        "statistical_plan_digest": plan.digest,
        "calibration_fraction": plan.calibration_fraction,
        "generalization_holdout_fraction": plan.generalization_holdout_fraction,
    }
    return {
        "schema": "DGC_TASK_PARTITION_RECEIPT_V2",
        **payload,
        "receipt_digest": sha256_bytes(canonical_json_bytes(payload)),
        "outcomes_observed": False,
        "generalization_outcomes_observed": False,
        "confirmatory_execution_authorized": False,
        "generalization_execution_authorized": False,
        "product_promotion_authorized": False,
    }


def test_valid_three_way_partition_replays_exactly(tmp_path: Path):
    path = write(tmp_path / "partition.json", valid_partition_doc())
    verified = verify_task_partition_document(path)
    assert len(verified["calibration_task_ids"]) == 20
    assert len(verified["confirmatory_task_ids"]) == 60
    assert len(verified["generalization_task_ids"]) == 20


def test_self_consistent_but_non_deterministic_partition_is_rejected(tmp_path: Path):
    doc = valid_partition_doc()
    calibration = list(doc["calibration_task_ids"])
    generalization = list(doc["generalization_task_ids"])
    calibration[0], generalization[0] = generalization[0], calibration[0]
    doc["calibration_task_ids"] = sorted(calibration)
    doc["generalization_task_ids"] = sorted(generalization)
    doc["calibration_task_digest"] = digest_tasks(calibration)
    doc["generalization_task_digest"] = digest_tasks(generalization)
    payload_keys = (
        "family_id", "materialization_reference_digest", "task_manifest_digest", "task_count",
        "calibration_task_ids", "confirmatory_task_ids", "generalization_task_ids",
        "calibration_task_digest", "confirmatory_task_digest", "generalization_task_digest",
        "statistical_plan_digest", "calibration_fraction", "generalization_holdout_fraction",
    )
    payload = {key: doc[key] for key in payload_keys}
    doc["receipt_digest"] = sha256_bytes(canonical_json_bytes(payload))
    path = write(tmp_path / "forged.json", doc)
    with pytest.raises(TaskPartitionError, match="deterministic split rule"):
        verify_task_partition_document(path)


def test_overlap_is_rejected_even_if_counts_are_preserved(tmp_path: Path):
    doc = valid_partition_doc()
    doc["generalization_task_ids"][0] = doc["calibration_task_ids"][0]
    path = write(tmp_path / "overlap.json", doc)
    with pytest.raises(TaskPartitionError, match="overlap"):
        verify_task_partition_document(path)
