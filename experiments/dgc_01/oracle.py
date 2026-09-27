from __future__ import annotations

from experiments.dgc_01.workloads import SyntheticDecisionTask


def oracle_compute_value(task: SyntheticDecisionTask) -> float:
    """Exact one-step EVPI-minus-cost under the declared synthetic model."""
    return task.expected_baseline_regret - task.diagnostic_cost


def oracle_should_compute(task: SyntheticDecisionTask) -> bool:
    return oracle_compute_value(task) > 0.0
