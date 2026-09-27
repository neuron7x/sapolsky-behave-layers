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


def main() -> int:
    cfg = config()
    killed = 0
    cases = [
        dict(
            expected_feature_schema_digest="0" * 64,
            expected_training_algorithm_digest=cfg.training_algorithm_digest,
            forbidden_task_ids=(),
        ),
        dict(
            expected_feature_schema_digest=cfg.feature_schema_digest,
            expected_training_algorithm_digest="0" * 64,
            forbidden_task_ids=(),
        ),
        dict(
            expected_feature_schema_digest=cfg.feature_schema_digest,
            expected_training_algorithm_digest=cfg.training_algorithm_digest,
            forbidden_task_ids=("t2",),
        ),
    ]
    for kwargs in cases:
        try:
            fit_b2_with_receipt(config=cfg, examples=examples(), **kwargs)
        except ValueError:
            killed += 1

    try:
        fit_b2_with_receipt(
            config=cfg,
            examples=examples()[:-1],
            forbidden_task_ids=(),
            expected_feature_schema_digest=cfg.feature_schema_digest,
            expected_training_algorithm_digest=cfg.training_algorithm_digest,
        )
    except ValueError:
        killed += 1

    if killed != 4:
        raise AssertionError(f"expected 4/4 attacks killed, got {killed}")
    print("DGC-B2-FIT-RECEIPT-ATTACK: PASS killed=4/4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
