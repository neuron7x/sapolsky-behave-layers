from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from statistics import fmean
from typing import Iterable


def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class CalibrationObservation:
    comparison_id: str
    task_id: str
    replicate: int
    value: float

    def __post_init__(self) -> None:
        comparison = str(self.comparison_id).strip()
        task = str(self.task_id).strip()
        if not comparison or not task:
            raise ValueError("comparison_id and task_id are required")
        if int(self.replicate) < 0:
            raise ValueError("replicate must be >= 0")
        value = float(self.value)
        if not math.isfinite(value):
            raise ValueError("value must be finite")
        object.__setattr__(self, "comparison_id", comparison)
        object.__setattr__(self, "task_id", task)
        object.__setattr__(self, "replicate", int(self.replicate))
        object.__setattr__(self, "value", value)


@dataclass(frozen=True, slots=True)
class BalancedVarianceEstimate:
    comparison_id: str
    task_count: int
    replicates_per_task: int
    grand_mean: float
    between_task_std: float
    within_task_std: float
    task_mean_variance: float
    pooled_within_variance: float
    population_digest: str


def estimate_balanced_variance_components(
    observations: Iterable[CalibrationObservation],
    *,
    comparison_id: str,
) -> BalancedVarianceEstimate:
    comparison = str(comparison_id).strip()
    if not comparison:
        raise ValueError("comparison_id required")
    rows = [row for row in observations if row.comparison_id == comparison]
    if not rows:
        raise ValueError(f"no observations for comparison_id={comparison}")

    keys = [(row.task_id, row.replicate) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate task/replicate observations are not allowed")

    by_task: dict[str, list[CalibrationObservation]] = {}
    for row in rows:
        by_task.setdefault(row.task_id, []).append(row)
    if len(by_task) < 2:
        raise ValueError("at least two calibration tasks are required")

    replicate_sets = []
    for task, task_rows in sorted(by_task.items()):
        reps = tuple(sorted(row.replicate for row in task_rows))
        if len(reps) < 2:
            raise ValueError("at least two replicates per task are required")
        expected = tuple(range(len(reps)))
        if reps != expected:
            raise ValueError(
                f"replicates must be contiguous 0..R-1 for task={task}; observed={reps}"
            )
        replicate_sets.append(reps)
    if len(set(replicate_sets)) != 1:
        raise ValueError("balanced replicate sets are required across calibration tasks")
    replicates = len(replicate_sets[0])

    ordered_rows = sorted(rows, key=lambda row: (row.task_id, row.replicate))
    task_means: dict[str, float] = {}
    within_ss = 0.0
    for task, task_rows in sorted(by_task.items()):
        values = [row.value for row in sorted(task_rows, key=lambda row: row.replicate)]
        mean = fmean(values)
        task_means[task] = mean
        within_ss += math.fsum((value - mean) ** 2 for value in values)

    n_tasks = len(task_means)
    pooled_within_variance = within_ss / (n_tasks * (replicates - 1))
    grand_mean = fmean(task_means.values())
    task_mean_variance = math.fsum(
        (mean - grand_mean) ** 2 for mean in task_means.values()
    ) / (n_tasks - 1)
    between_task_variance = max(
        0.0, task_mean_variance - pooled_within_variance / replicates
    )

    payload = [
        (row.comparison_id, row.task_id, row.replicate, row.value)
        for row in ordered_rows
    ]
    return BalancedVarianceEstimate(
        comparison_id=comparison,
        task_count=n_tasks,
        replicates_per_task=replicates,
        grand_mean=grand_mean,
        between_task_std=math.sqrt(between_task_variance),
        within_task_std=math.sqrt(max(0.0, pooled_within_variance)),
        task_mean_variance=task_mean_variance,
        pooled_within_variance=pooled_within_variance,
        population_digest=_digest(payload),
    )


def estimate_all_balanced_variance_components(
    observations: Iterable[CalibrationObservation],
) -> tuple[BalancedVarianceEstimate, ...]:
    rows = tuple(observations)
    comparisons = tuple(sorted({row.comparison_id for row in rows}))
    if not comparisons:
        raise ValueError("non-empty calibration observations required")
    return tuple(
        estimate_balanced_variance_components(rows, comparison_id=comparison)
        for comparison in comparisons
    )
