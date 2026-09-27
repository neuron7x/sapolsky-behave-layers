from __future__ import annotations

import json
from pathlib import Path

import pytest

import cwc.governance.mechanism_harness_freeze as module
from cwc.governance.baseline_panel import BaselineKind
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes
from cwc.governance.mechanism_evidence_plan import MechanismStatisticalPlan
from cwc.governance.mechanism_execution_freeze import COMPONENT_SCHEMAS_MECHANISM
from cwc.governance.mechanism_harness_freeze import (
    MechanismHarnessFreezeError,
    build_mechanism_harness_freeze,
    verify_mechanism_harness_freeze_document,
)


def h(char: str) -> str:
    return char * 64


def _write(path: Path, doc: dict) -> Path:
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _baseline_input(path: Path, feature: str, algorithm: str) -> Path:
    specs = []
    for index, kind in enumerate(BaselineKind):
        row = {
            "kind": kind.value,
            "implementation_version": "v1",
            "feature_schema_digest": feature if kind is BaselineKind.LEARNED_COST_QUALITY_ROUTER else h(str(index + 1)),
            "policy_config_digest": h("abcdef01"[index]),
        }
        if kind is BaselineKind.LEARNED_COST_QUALITY_ROUTER:
            row["training_algorithm_digest"] = algorithm
        specs.append(row)
    return _write(path, {
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


def _fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, inject_risk=False):
    plan = MechanismStatisticalPlan()
    names = list(COMPONENT_SCHEMAS_MECHANISM)
    if inject_risk:
        names.append("risk_endpoint_manifest")
    execution = {
        "family_id": "TERMINAL_BENCH_2_1",
        "freeze_digest": h("a"),
        "mechanism_plan_digest": plan.digest,
        "task_manifest_digest": h("b"),
        "components": [
            {"component": name, "sha256": h("123456789abcdef"[index])}
            for index, name in enumerate(names)
        ],
        "governance_policies": [
            {"policy_id": policy, "sha256": h(char)}
            for policy, char in zip(("B0", "B1", "B2", "B3", "DGC"), "abcde", strict=True)
        ],
    }
    b2 = {
        "family_id": "TERMINAL_BENCH_2_1",
        "execution_manifest_freeze_digest": h("a"),
        "authority_digest": h("f"),
        "feature_schema_digest": h("1"),
        "training_algorithm_digest": h("2"),
        "calibration_task_digest": h("3"),
        "confirmatory_task_digest": h("4"),
        "generalization_task_digest": h("5"),
        "fitted_model_digest": h("6"),
    }
    monkeypatch.setattr(module, "verify_mechanism_execution_freeze_document", lambda _: execution)
    monkeypatch.setattr(module, "verify_mechanism_b2_fit_authority_document", lambda _: b2)
    baseline = _baseline_input(tmp_path / "baseline.json", h("1"), h("2"))
    return execution, b2, baseline, plan


def test_mechanism_harness_binds_exact_risk_free_comparison_frame(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    execution, _, baseline, plan = _fixture(tmp_path, monkeypatch)
    authority = build_mechanism_harness_freeze(
        execution_manifest_freeze_path=tmp_path / "execution.json",
        mechanism_b2_fit_authority_path=tmp_path / "b2.json",
        baseline_panel_input_path=baseline,
    )
    assert authority.mechanism_plan_digest == plan.digest
    assert authority.confirmatory_task_manifest_digest == h("4")
    assert len(authority.policy_harnesses) == 5
    assert len({row.harness_full_digest for row in authority.policy_harnesses}) == 5
    assert authority.document["risk_endpoint_bound"] is False
    assert authority.document["risk_qualification_authorized"] is False
    assert authority.document["product_promotion_authorized"] is False
    out = _write(tmp_path / "harness.json", authority.document)
    verified = verify_mechanism_harness_freeze_document(out)
    assert verified["comparison_frame_digest"] == authority.comparison_frame_digest


def test_mechanism_harness_rejects_risk_endpoint_component(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _, _, baseline, _ = _fixture(tmp_path, monkeypatch, inject_risk=True)
    with pytest.raises(MechanismHarnessFreezeError, match="component population incomplete"):
        build_mechanism_harness_freeze(
            execution_manifest_freeze_path=tmp_path / "execution.json",
            mechanism_b2_fit_authority_path=tmp_path / "b2.json",
            baseline_panel_input_path=baseline,
        )


def test_mechanism_harness_rejects_product_promotion_escalation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    _, _, baseline, _ = _fixture(tmp_path, monkeypatch)
    authority = build_mechanism_harness_freeze(
        execution_manifest_freeze_path=tmp_path / "execution.json",
        mechanism_b2_fit_authority_path=tmp_path / "b2.json",
        baseline_panel_input_path=baseline,
    )
    doc = authority.document
    doc["product_promotion_authorized"] = True
    out = _write(tmp_path / "bad.json", doc)
    with pytest.raises(MechanismHarnessFreezeError, match="authority boundary"):
        verify_mechanism_harness_freeze_document(out)


def test_mechanism_harness_rejects_b2_execution_substitution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    execution, b2, baseline, _ = _fixture(tmp_path, monkeypatch)
    b2["execution_manifest_freeze_digest"] = h("9")
    with pytest.raises(MechanismHarnessFreezeError, match="different execution freeze"):
        build_mechanism_harness_freeze(
            execution_manifest_freeze_path=tmp_path / "execution.json",
            mechanism_b2_fit_authority_path=tmp_path / "b2.json",
            baseline_panel_input_path=baseline,
        )
