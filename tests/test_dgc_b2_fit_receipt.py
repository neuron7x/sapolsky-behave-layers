import pytest

from cwc.governance.b2_fit_receipt import fit_b2_with_receipt
from cwc.governance.learned_baseline import CalibrationExample, LearnedRouterConfig


def config():
    return LearnedRouterConfig(("x",), ("cheap", "strong"), 1.0, 1.0, 0.1, 1.0)


def examples():
    return [
        CalibrationExample("t1", "cheap", (0.0,), 0.5, 0.1, 0.0),
        CalibrationExample("t1", "strong", (0.0,), 0.8, 0.4, 0.0),
        CalibrationExample("t2", "cheap", (1.0,), 0.6, 0.1, 0.0),
        CalibrationExample("t2", "strong", (1.0,), 0.9, 0.4, 0.0),
    ]


def test_deterministic_receipt_and_no_execution_authority():
    cfg = config()
    kwargs = dict(
        config=cfg,
        examples=examples(),
        forbidden_task_ids=("confirm1",),
        expected_feature_schema_digest=cfg.feature_schema_digest,
        expected_training_algorithm_digest=cfg.training_algorithm_digest,
    )
    first = fit_b2_with_receipt(**kwargs)
    second = fit_b2_with_receipt(**kwargs)
    assert first == second
    assert len(first.receipt_digest) == 64
    assert first.confirmatory_execution_authorized is False
    assert first.calibration_task_count == 2


def test_schema_mismatch_rejected():
    cfg = config()
    with pytest.raises(ValueError, match="schema"):
        fit_b2_with_receipt(
            config=cfg,
            examples=examples(),
            forbidden_task_ids=(),
            expected_feature_schema_digest="0" * 64,
            expected_training_algorithm_digest=cfg.training_algorithm_digest,
        )


def test_algorithm_mismatch_rejected():
    cfg = config()
    with pytest.raises(ValueError, match="algorithm"):
        fit_b2_with_receipt(
            config=cfg,
            examples=examples(),
            forbidden_task_ids=(),
            expected_feature_schema_digest=cfg.feature_schema_digest,
            expected_training_algorithm_digest="0" * 64,
        )


def test_confirmatory_leakage_rejected():
    cfg = config()
    with pytest.raises(ValueError, match="leakage"):
        fit_b2_with_receipt(
            config=cfg,
            examples=examples(),
            forbidden_task_ids=("t2",),
            expected_feature_schema_digest=cfg.feature_schema_digest,
            expected_training_algorithm_digest=cfg.training_algorithm_digest,
        )
