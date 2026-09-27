from cwc.governance.calibration_variance import CalibrationObservation
from cwc.governance.product_statistical_plan import ProductStatisticalPlan
from cwc.governance.trial_sizing_receipt import freeze_cluster_aware_trial_sizing


def obs(comparison, task, values):
    return [CalibrationObservation(comparison, task, index, value) for index, value in enumerate(values)]


def good():
    rows = []
    for comparison, shift in [("cost", 0.0), ("quality", 0.01)]:
        rows += obs(comparison, "a", [0 + shift, 0.01 + shift])
        rows += obs(comparison, "b", [0.01 + shift, 0.02 + shift])
        rows += obs(comparison, "c", [0.02 + shift, 0.03 + shift])
    return rows


def main() -> int:
    killed = 0
    plan = ProductStatisticalPlan()
    try:
        freeze_cluster_aware_trial_sizing(
            observations=good(),
            effects_of_interest={"cost": 0.2},
            confirmatory_task_count=80,
            plan=plan,
        )
    except ValueError:
        killed += 1

    bad = good()
    bad = [
        row for row in bad
        if not (row.comparison_id == "quality" and row.task_id == "c" and row.replicate == 1)
    ]
    try:
        freeze_cluster_aware_trial_sizing(
            observations=bad,
            effects_of_interest={"cost": 0.2, "quality": 0.2},
            confirmatory_task_count=80,
            plan=plan,
        )
    except ValueError:
        killed += 1

    high = []
    for task, value in [("a", 0.0), ("b", 1.0), ("c", 2.0)]:
        high += obs("cost", task, [value, value])
    try:
        freeze_cluster_aware_trial_sizing(
            observations=high,
            effects_of_interest={"cost": 0.01},
            confirmatory_task_count=10,
            plan=plan,
        )
    except RuntimeError:
        killed += 1

    try:
        freeze_cluster_aware_trial_sizing(
            observations=good(),
            effects_of_interest={"cost": 0.2, "quality": 0.0},
            confirmatory_task_count=80,
            plan=plan,
        )
    except ValueError:
        killed += 1

    if killed != 4:
        raise AssertionError(f"expected 4/4 attacks killed, got {killed}")
    print("DGC-TRIAL-SIZING-RECEIPT-ATTACK: PASS killed=4/4")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
