from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import pytest

import cwc.governance.mechanism_b2_fit_authority as module
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes
from cwc.governance.mechanism_b2_fit_authority import (
    MechanismB2FitAuthorityError,
    authorize_mechanism_b2_fit,
    verify_mechanism_b2_fit_authority_document,
)
from cwc.governance.mechanism_b2_fit_receipt import fit_mechanism_b2_with_receipt
from cwc.governance.mechanism_learned_baseline import (
    MechanismCalibrationExample,
    MechanismLearnedRouterConfig,
)


def _write(path: Path, doc: dict) -> Path:
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _task_digest(ids: tuple[str, ...]) -> str:
    return sha256_bytes(canonical_json_bytes(tuple(sorted(ids))))


def _fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cfg = MechanismLearnedRouterConfig(
        feature_names=("difficulty",),
        action_ids=("DEEP", "STANDARD"),
        ridge_lambda=0.1,
        quality_weight=1.0,
        cost_weight=0.2,
    )
    rows = [
        MechanismCalibrationExample("c1", "DEEP", (0.0,), 0.8, 0.4),
        MechanismCalibrationExample("c1", "STANDARD", (0.0,), 0.75, 0.1),
        MechanismCalibrationExample("c2", "DEEP", (1.0,), 0.95, 0.4),
        MechanismCalibrationExample("c2", "STANDARD", (1.0,), 0.35, 0.1),
    ]
    forbidden = ("g1", "p1")
    receipt = fit_mechanism_b2_with_receipt(
        config=cfg,
        examples=rows,
        forbidden_task_ids=forbidden,
        expected_feature_schema_digest=cfg.feature_schema_digest,
        expected_training_algorithm_digest=cfg.training_algorithm_digest,
    )
    fit_input = {
        "schema": "DGC_MECHANISM_B2_FIT_INPUT_V1",
        "config": {
            "feature_names": list(cfg.feature_names),
            "action_ids": list(cfg.action_ids),
            "ridge_lambda": cfg.ridge_lambda,
            "quality_weight": cfg.quality_weight,
            "cost_weight": cfg.cost_weight,
        },
        "examples": [
            {
                "task_id": row.task_id,
                "action_id": row.action_id,
                "features": list(row.features),
                "quality": row.quality,
                "cost_usd": row.cost_usd,
            }
            for row in rows
        ],
        "forbidden_task_ids": list(forbidden),
        "expected_feature_schema_digest": cfg.feature_schema_digest,
        "expected_training_algorithm_digest": cfg.training_algorithm_digest,
    }
    fit_input_path = _write(tmp_path / "fit-input.json", fit_input)
    receipt_path = _write(tmp_path / "fit-receipt.json", asdict(receipt))
    execution = {
        "family_id": "FAM",
        "freeze_digest": "a" * 64,
        "materialization_reference_digest": "b" * 64,
        "task_manifest_digest": _task_digest(("c1", "c2", "g1", "p1")),
        "statistical_plan_digest": "c" * 64,
    }
    partition = {
        "family_id": "FAM",
        "receipt_digest": "d" * 64,
        "materialization_reference_digest": "b" * 64,
        "task_manifest_digest": execution["task_manifest_digest"],
        "statistical_plan_digest": "c" * 64,
        "calibration_task_ids": ["c1", "c2"],
        "confirmatory_task_ids": ["p1"],
        "generalization_task_ids": ["g1"],
        "calibration_task_digest": receipt.calibration_task_digest,
        "confirmatory_task_digest": _task_digest(("p1",)),
        "generalization_task_digest": _task_digest(("g1",)),
    }
    monkeypatch.setattr(module, "verify_mechanism_execution_freeze_document", lambda _: execution)
    monkeypatch.setattr(module, "verify_task_partition_document", lambda _: partition)
    return fit_input_path, receipt_path, execution, partition


def test_mechanism_b2_authority_replays_serialized_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    fit_input, receipt, _, _ = _fixture(tmp_path, monkeypatch)
    authority = authorize_mechanism_b2_fit(
        execution_manifest_freeze_path=tmp_path / "execution.json",
        task_partition_path=tmp_path / "partition.json",
        fit_input_path=fit_input,
        fit_receipt_path=receipt,
    )
    assert authority.calibration_task_count == 2
    doc = authority.document
    assert doc["risk_fields_consumed"] is False
    assert doc["risk_qualification_authorized"] is False
    assert doc["product_promotion_authorized"] is False
    out = _write(tmp_path / "authority.json", doc)
    assert verify_mechanism_b2_fit_authority_document(out)["authority_digest"] == authority.authority_digest


def test_mechanism_b2_authority_rejects_risk_field_injection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    fit_input, receipt, _, _ = _fixture(tmp_path, monkeypatch)
    doc = json.loads(fit_input.read_text())
    doc["examples"][0]["catastrophic_regret"] = 0.0
    _write(fit_input, doc)
    with pytest.raises(MechanismB2FitAuthorityError, match="forbidden risk field"):
        authorize_mechanism_b2_fit(
            execution_manifest_freeze_path=tmp_path / "execution.json",
            task_partition_path=tmp_path / "partition.json",
            fit_input_path=fit_input,
            fit_receipt_path=receipt,
        )


def test_mechanism_b2_authority_rejects_product_escalation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    fit_input, receipt, _, _ = _fixture(tmp_path, monkeypatch)
    authority = authorize_mechanism_b2_fit(
        execution_manifest_freeze_path=tmp_path / "execution.json",
        task_partition_path=tmp_path / "partition.json",
        fit_input_path=fit_input,
        fit_receipt_path=receipt,
    )
    doc = authority.document
    doc["product_promotion_authorized"] = True
    out = _write(tmp_path / "bad.json", doc)
    with pytest.raises(MechanismB2FitAuthorityError, match="authority boundary"):
        verify_mechanism_b2_fit_authority_document(out)
