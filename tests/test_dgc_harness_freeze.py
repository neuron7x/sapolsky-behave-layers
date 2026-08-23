from __future__ import annotations

import json
from pathlib import Path

import pytest

from cwc.governance.baseline_panel import BaselineKind
from cwc.governance.harness_freeze import (
    DGC_ROLE,
    HarnessFreezeError,
    build_harness_freeze,
    verify_harness_freeze_document,
)
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes


def h(char: str) -> str:
    return char * 64


def write(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def execution_doc(path: Path, *, policy_ids=("B0", "B1", "B2", "B3", "DGC"), collide=False) -> Path:
    components = [
        {"component": name, "path": f"m/{name}.json", "sha256": h(char), "bytes": 10, "schema": "x"}
        for name, char in zip(
            ("model_manifest", "prompt_policy", "tool_manifest", "environment", "budget", "pricing_snapshot", "scorer"),
            "1234567",
            strict=True,
        )
    ]
    policies = []
    for index, policy_id in enumerate(policy_ids):
        digest = h("8") if collide else h("89abcdef"[index])
        policies.append({
            "policy_id": policy_id,
            "path": f"p/{policy_id}.json",
            "sha256": digest,
            "implementation_sha256": h("1"),
            "config_sha256": h("2"),
        })
    payload = {
        "family_id": "SWE_BENCH_VERIFIED",
        "repository_commit": "a" * 40,
        "repository_tree": "b" * 40,
        "materialization_reference_path": "eval_bundle/materialization.json",
        "materialization_reference_digest": h("0"),
        "materialized_tree_sha256": h("a"),
        "task_manifest_digest": h("b"),
        "statistical_plan_digest": h("c"),
        "statistical_plan": {},
        "components": components,
        "governance_policies": policies,
        "prebaseline_comparison_digest": h("d"),
    }
    doc = {
        "schema": "DGC_EXECUTION_MANIFEST_FREEZE_V1",
        **payload,
        "freeze_digest": sha256_bytes(canonical_json_bytes(payload)),
        "baseline_panel_bound": False,
        "harness_frozen": False,
        "confirmatory_execution_authorized": False,
        "product_promotion_authorized": False,
    }
    return write(path, doc)


def b2_doc(path: Path, *, execution_digest: str, feature=h("e"), algorithm=h("f")) -> Path:
    payload = {
        "family_id": "SWE_BENCH_VERIFIED",
        "execution_manifest_freeze_digest": execution_digest,
        "task_partition_receipt_digest": h("1"),
        "fit_input_sha256": h("2"),
        "fit_receipt_sha256": h("3"),
        "feature_schema_digest": feature,
        "training_algorithm_digest": algorithm,
        "calibration_task_digest": h("4"),
        "confirmatory_task_digest": h("5"),
        "fitted_model_digest": h("6"),
        "calibration_task_count": 100,
    }
    doc = {
        "schema": "DGC_B2_FIT_AUTHORITY_V1",
        **payload,
        "authority_digest": sha256_bytes(canonical_json_bytes(payload)),
        "confirmatory_execution_authorized": False,
        "product_promotion_authorized": False,
    }
    return write(path, doc)


def baseline_input(path: Path, *, b2_feature=h("e"), b2_algorithm=h("f")) -> Path:
    specs = []
    for index, kind in enumerate(BaselineKind):
        row = {
            "kind": kind.value,
            "implementation_version": "v1",
            "feature_schema_digest": b2_feature if kind is BaselineKind.LEARNED_COST_QUALITY_ROUTER else h(str(index + 1)),
            "policy_config_digest": h("abcdef01"[index]),
        }
        if kind is BaselineKind.LEARNED_COST_QUALITY_ROUTER:
            row["training_algorithm_digest"] = b2_algorithm
        specs.append(row)
    return write(path, {
        "schema": "DGC_BASELINE_PANEL_INPUT_V1",
        "specs": specs,
        "baseline_policy_ids": {
            BaselineKind.FIXED_COMPUTE.value: "B0",
            BaselineKind.UNCERTAINTY_ROUTER.value: "B1",
            BaselineKind.LEARNED_COST_QUALITY_ROUTER.value: "B2",
            BaselineKind.SEQUENTIAL_VERIFICATION.value: "B3",
        },
        "dgc_policy_id": "DGC",
    })


def fixture(tmp_path: Path, *, collide=False, policy_ids=("B0", "B1", "B2", "B3", "DGC")):
    execution = execution_doc(tmp_path / "execution.json", collide=collide, policy_ids=policy_ids)
    execution_payload = json.loads(execution.read_text())
    b2 = b2_doc(tmp_path / "b2.json", execution_digest=execution_payload["freeze_digest"])
    baselines = baseline_input(tmp_path / "baselines.json")
    return execution, b2, baselines


def test_final_harness_freeze_binds_exact_fitted_b0_b3_plus_dgc(tmp_path: Path):
    execution, b2, baselines = fixture(tmp_path)
    authority = build_harness_freeze(
        execution_manifest_freeze_path=execution,
        b2_fit_authority_path=b2,
        baseline_panel_input_path=baselines,
    )
    assert authority.family_id == "SWE_BENCH_VERIFIED"
    assert len(authority.policy_harnesses) == 5
    assert len({row.governance_policy_digest for row in authority.policy_harnesses}) == 5
    assert len({row.harness_full_digest for row in authority.policy_harnesses}) == 5
    role_map = {row.role: row.policy_id for row in authority.policy_role_bindings}
    assert role_map[DGC_ROLE] == "DGC"
    assert role_map[BaselineKind.FIXED_COMPUTE.value] == "B0"
    assert role_map[BaselineKind.UNCERTAINTY_ROUTER.value] == "B1"
    assert role_map[BaselineKind.LEARNED_COST_QUALITY_ROUTER.value] == "B2"
    assert role_map[BaselineKind.SEQUENTIAL_VERIFICATION.value] == "B3"
    b2_spec = next(row for row in authority.baseline_specs if row["kind"] == BaselineKind.LEARNED_COST_QUALITY_ROUTER.value)
    assert b2_spec["calibration_task_digest"] == h("4")
    assert b2_spec["fitted_model_digest"] == h("6")

    out = write(tmp_path / "harness.json", authority.document)
    verified = verify_harness_freeze_document(out)
    assert verified["harness_frozen"] is True
    assert verified["comparison_frame_digest"] == authority.comparison_frame_digest


def test_harness_freeze_rejects_b2_schema_mismatch(tmp_path: Path):
    execution, b2, _ = fixture(tmp_path)
    baselines = baseline_input(tmp_path / "bad-baselines.json", b2_feature=h("9"))
    with pytest.raises(HarnessFreezeError, match="feature schema"):
        build_harness_freeze(
            execution_manifest_freeze_path=execution,
            b2_fit_authority_path=b2,
            baseline_panel_input_path=baselines,
        )


def test_harness_freeze_rejects_missing_policy_arm(tmp_path: Path):
    execution, b2, baselines = fixture(tmp_path, policy_ids=("B0", "B1", "B2", "DGC"))
    with pytest.raises(HarnessFreezeError, match="exact B0-B3 \+ DGC"):
        build_harness_freeze(
            execution_manifest_freeze_path=execution,
            b2_fit_authority_path=b2,
            baseline_panel_input_path=baselines,
        )


def test_harness_freeze_rejects_governance_digest_collision(tmp_path: Path):
    execution, b2, baselines = fixture(tmp_path, collide=True)
    with pytest.raises(HarnessFreezeError, match="distinct content digests"):
        build_harness_freeze(
            execution_manifest_freeze_path=execution,
            b2_fit_authority_path=b2,
            baseline_panel_input_path=baselines,
        )


def test_harness_document_tamper_is_rejected(tmp_path: Path):
    execution, b2, baselines = fixture(tmp_path)
    authority = build_harness_freeze(
        execution_manifest_freeze_path=execution,
        b2_fit_authority_path=b2,
        baseline_panel_input_path=baselines,
    )
    out = write(tmp_path / "harness.json", authority.document)
    doc = json.loads(out.read_text())
    doc["comparison_frame_digest"] = h("f")
    write(out, doc)
    with pytest.raises(HarnessFreezeError, match="digest mismatch"):
        verify_harness_freeze_document(out)


def test_policy_role_substitution_is_rejected_even_if_five_arms_remain(tmp_path: Path):
    execution, b2, baselines = fixture(tmp_path)
    authority = build_harness_freeze(
        execution_manifest_freeze_path=execution,
        b2_fit_authority_path=b2,
        baseline_panel_input_path=baselines,
    )
    out = write(tmp_path / "harness.json", authority.document)
    doc = json.loads(out.read_text())
    rows = doc["policy_role_bindings"]
    b0 = next(row for row in rows if row["role"] == BaselineKind.FIXED_COMPUTE.value)
    dgc = next(row for row in rows if row["role"] == DGC_ROLE)
    b0["policy_id"], dgc["policy_id"] = dgc["policy_id"], b0["policy_id"]
    write(out, doc)
    with pytest.raises(HarnessFreezeError, match="digest mismatch"):
        verify_harness_freeze_document(out)
