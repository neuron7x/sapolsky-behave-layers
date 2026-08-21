from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SyntheticDecisionTask:
    task_id: str
    regime: str
    p_world_b: float
    loss_wrong_in_a: float
    loss_wrong_in_b: float
    diagnostic_cost: float
    same_optimal_action: bool
    true_world: str

    @property
    def uncertainty_bits(self) -> float:
        p = self.p_world_b
        if p in (0.0, 1.0):
            return 0.0
        return -(p * math.log2(p) + (1.0 - p) * math.log2(1.0 - p))

    def optimal_action(self, world: str) -> str:
        if self.same_optimal_action:
            return "A"
        return "B" if world == "B" else "A"

    @property
    def baseline_action(self) -> str:
        if self.same_optimal_action:
            return "A"
        expected_loss_a = self.p_world_b * self.loss_wrong_in_b
        expected_loss_b = (1.0 - self.p_world_b) * self.loss_wrong_in_a
        return "A" if expected_loss_a <= expected_loss_b else "B"

    @property
    def expected_baseline_regret(self) -> float:
        if self.same_optimal_action:
            return 0.0
        if self.baseline_action == "A":
            return self.p_world_b * self.loss_wrong_in_b
        return (1.0 - self.p_world_b) * self.loss_wrong_in_a

    @property
    def oracle_voc(self) -> float:
        # Perfect one-step diagnostic: gross value equals expected regret removed.
        return self.expected_baseline_regret - self.diagnostic_cost

    def realized_loss(self, action: str) -> float:
        optimal = self.optimal_action(self.true_world)
        if action == optimal:
            return 0.0
        return self.loss_wrong_in_b if self.true_world == "B" else self.loss_wrong_in_a


def _draw_world(rng: random.Random, p_b: float) -> str:
    return "B" if rng.random() < p_b else "A"


def generate_task(regime: str, seed: int) -> SyntheticDecisionTask:
    rng = random.Random((seed + 1) * 1_000_003 + sum(ord(c) for c in regime))
    if regime == "A":
        p = rng.uniform(0.42, 0.58)
        loss_a = loss_b = 1.0
        cost = rng.uniform(0.08, 0.12)
        same = True
    elif regime == "B":
        # Low entropy but close to the utility-weighted decision boundary.
        p = rng.uniform(0.10, 0.16)
        loss_a = rng.uniform(0.14, 0.18)
        loss_b = rng.uniform(0.95, 1.05)
        cost = rng.uniform(0.025, 0.045)
        same = False
    elif regime == "C":
        p = rng.uniform(0.44, 0.56)
        loss_a = rng.uniform(0.8, 1.0)
        loss_b = rng.uniform(0.8, 1.0)
        cost = rng.uniform(0.08, 0.12)
        same = False
    elif regime == "D":
        p = rng.uniform(0.40, 0.60)
        loss_a = rng.uniform(0.7, 1.0)
        loss_b = rng.uniform(0.7, 1.0)
        cost = rng.uniform(0.08, 0.12)
        same = True
    elif regime == "E":
        # Low-probability world but high decision loss. Accuracy-only routing sees
        # only a small flip probability; utility-aware DGC sees p*loss.
        p = rng.uniform(0.045, 0.05)
        loss_a = rng.uniform(0.15, 0.25)
        loss_b = rng.uniform(1.4, 1.6)
        cost = rng.uniform(0.055, 0.06)
        same = False
    else:
        raise KeyError(regime)
    return SyntheticDecisionTask(
        task_id=f"{regime}-{seed:08d}",
        regime=regime,
        p_world_b=p,
        loss_wrong_in_a=loss_a,
        loss_wrong_in_b=loss_b,
        diagnostic_cost=cost,
        same_optimal_action=same,
        true_world=_draw_world(rng, p),
    )


def generate_workload(per_regime: int, *, seed_offset: int = 0) -> tuple[SyntheticDecisionTask, ...]:
    if per_regime <= 0:
        raise ValueError("per_regime must be positive")
    return tuple(
        generate_task(regime, seed_offset + seed)
        for regime in ("A", "B", "C", "D", "E")
        for seed in range(per_regime)
    )
