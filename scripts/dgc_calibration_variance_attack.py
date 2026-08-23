from cwc.governance.calibration_variance import (
    CalibrationObservation,
    estimate_balanced_variance_components,
)


def main() -> int:
    killed = 0
    cases = [
        [
            CalibrationObservation("c", "a", 0, 0),
            CalibrationObservation("c", "a", 1, 1),
            CalibrationObservation("c", "b", 0, 1),
            CalibrationObservation("c", "b", 1, 2),
            CalibrationObservation("c", "a", 0, 3),
        ],
        [
            CalibrationObservation("c", "a", 0, 0),
            CalibrationObservation("c", "a", 1, 1),
            CalibrationObservation("c", "b", 0, 1),
            CalibrationObservation("c", "b", 1, 2),
            CalibrationObservation("c", "b", 2, 3),
        ],
        [
            CalibrationObservation("c", "a", 0, 0),
            CalibrationObservation("c", "a", 2, 1),
            CalibrationObservation("c", "b", 0, 1),
            CalibrationObservation("c", "b", 2, 2),
        ],
        [
            CalibrationObservation("c", "a", 0, 0),
            CalibrationObservation("c", "a", 1, 1),
        ],
        [
            CalibrationObservation("c", "a", 0, 0),
            CalibrationObservation("c", "b", 0, 1),
        ],
    ]

    for rows in cases:
        try:
            estimate_balanced_variance_components(rows, comparison_id="c")
        except ValueError:
            killed += 1

    if killed != 5:
        raise AssertionError(f"expected 5/5 attacks killed, got {killed}")
    print("DGC-CALIBRATION-VARIANCE-ATTACK: PASS killed=5/5")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
