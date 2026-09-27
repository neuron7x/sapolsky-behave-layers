from __future__ import annotations

import json
import random
from dataclasses import asdict
from pathlib import Path

import pytest

from cwc.governance.mechanism_b2_fit_receipt import fit_mechanism_b2_with_receipt
from cwc.governance.mechanism_learned_baseline import (
    MechanismCalibrationExample,
    MechanismLearnedRouterConfig,
    fit_mechanism_learned_router,
)


def config():
    return MechanismLearnedRouterConfig(
        feature_names=("difficulty",),
        action_ids=("DEEP", "STANDARD"),
        ridge_lambda=0.1,
        quality_weight=1.0,
        cost_weight=0.2,
    )


def population():
    return [
        MechanismCalibrationExample("t1", "STANDARD", (0.0,), 0.75, 0.10),
        MechanismCalibrationExample("t1", "DEEP", (0.0,), 0.80, 0.40),
        MechanismCalibrationExample("t2", "STANDARD", (1.0,), 0.35, 0.10),
        MechanismCalibrationExample("t2", "DEEP", (1.0,), 0.95, 0.40),
    ]


def test_mechanism_b2_fit_is_deterministic_and_risk_free():
    rows = population()
    first = fit_mechanism_learned_router(config(), rows)
    random.Random(7).shuffle(rows)
    second = fit_mechanism_learned_router(config(), rows)
    assert first.model_digest == second.model_digest
    assert first.calibration_task_digest == second.calibration_task_digest
    assert first.predict((0.0,)) == "STANDARD"
    assert first.predict((1.0,)) == "DEEP"


def test_mechanism_b2_receipt_has_no_risk_surface():
    cfg = config()
    receipt = fit_mechanism_b2_with_receipt(
        config=cfg,
        examples=population(),
        forbidden_task_ids=("confirm",),
        expected_feature_schema_digest=cfg.feature_schema_digest,
        expected_training_algorithm_digest=cfg.training_algorithm_digest,
    )
    doc = asdict(receipt)
    serialized = json.dumps(doc, sort_keys=True)
    assert "catastrophic_regret" not in serialized
    assert "risk_score" not in serialized
    assert doc["risk_fields_consumed"] is False
    assert doc["mechanism_execution_authorized"] is False
    assert doc["product_promotion_authorized"] is False


def test_mechanism_b2_forbidden_task_leakage_fails_closed():
    with pytest.raises(ValueError, match="leakage"):
        fit_mechanism_learned_router(
            config(),
            population(),
            forbidden_task_ids=("t2",),
        )


def test_mechanism_b2_requires_complete_counterfactual_table():
    with pytest.raises(ValueError, match="complete counterfactual"):
        fit_mechanism_learned_router(config(), population()[:-1])


def test_mechanism_b2_config_has_no_regret_weight():
    fields = set(MechanismLearnedRouterConfig.__dataclass_fields__)
    assert "regret_weight" not in fields
