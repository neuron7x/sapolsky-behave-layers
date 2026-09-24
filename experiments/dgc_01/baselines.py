from __future__ import annotations

from dataclasses import dataclass

from experiments.dgc_01.workloads import SyntheticDecisionTask


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    policy: str
    buy_diagnostic: bool
    score: float


def _score(task: SyntheticDecisionTask, buy: bool) -> float:
    if buy:
        action = task.optimal_action(task.true_world)
        return -task.realized_loss(action) - task.diagnostic_cost
    return -task.realized_loss(task.baseline_action)


def b0_fixed(task: SyntheticDecisionTask) -> PolicyDecision:
    buy = True
    return PolicyDecision("B0_FIXED", buy, _score(task, buy))


def b1_uncertainty(task: SyntheticDecisionTask) -> PolicyDecision:
    # Frozen entropy threshold; blind to decision consequence.
    buy = task.uncertainty_bits >= 0.75
    return PolicyDecision("B1_UNCERTAINTY", buy, _score(task, buy))


def b2_cost_quality(task: SyntheticDecisionTask) -> PolicyDecision:
    # Stronger than entropy alone: estimated 0-1 accuracy gain per unit cost.
    expected_accuracy_gain = min(task.p_world_b, 1.0 - task.p_world_b)
    buy = expected_accuracy_gain / task.diagnostic_cost > 1.0
    return PolicyDecision("B2_COST_QUALITY_ROUTER", buy, _score(task, buy))


def b3_dgc(task: SyntheticDecisionTask) -> PolicyDecision:
    # No true-world access: uses declared prior, utility loss and diagnostic cost.
    buy = task.oracle_voc > 0.0
    return PolicyDecision("B3_DGC", buy, _score(task, buy))


POLICIES = (b0_fixed, b1_uncertainty, b2_cost_quality, b3_dgc)
