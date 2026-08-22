from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from statistics import NormalDist
from typing import Iterable


@dataclass(frozen=True, slots=True)
class ProductStatisticalPlan:
    family_count: int = 2
    baseline_count: int = 4
    endpoint_count: int = 3
    familywise_alpha: float = 0.05
    quality_noninferiority_margin: float = 0.02
    catastrophic_regret_noninferiority_margin: float = 0.01
    minimum_cost_effect_of_interest: float = 0.05
    calibration_fraction: float = 0.20
    target_power: float = 0.90
    min_trials_per_task: int = 5
    max_trials_per_task: int = 50
    method: str = "DGC_PRODUCT_PAIRED_CALIBRATION_CONFIRMATORY_V1"

    def __post_init__(self) -> None:
        if min(self.family_count, self.baseline_count, self.endpoint_count) <= 0:
            raise ValueError("family/baseline/endpoint counts must be positive")
        if not 0.0 < self.familywise_alpha < 1.0:
            raise ValueError("familywise_alpha must be in (0,1)")
        if not 0.0 < self.quality_noninferiority_margin < 1.0:
            raise ValueError("quality margin must be in (0,1)")
        if not 0.0 <= self.catastrophic_regret_noninferiority_margin < 1.0:
            raise ValueError("catastrophic-regret margin must be in [0,1)")
        if not 0.0 < self.minimum_cost_effect_of_interest < 1.0:
            raise ValueError("minimum cost effect must be in (0,1)")
        if not 0.0 < self.calibration_fraction < 0.5:
            raise ValueError("calibration_fraction must be in (0,0.5)")
        if not 0.5 < self.target_power < 1.0:
            raise ValueError("target_power must be in (0.5,1)")
        if not (1 <= self.min_trials_per_task <= self.max_trials_per_task):
            raise ValueError("invalid trial bounds")

    @property
    def per_claim_alpha(self) -> float:
        return self.familywise_alpha / (
            self.family_count * self.baseline_count * self.endpoint_count
        )

    @property
    def digest(self) -> str:
        payload = {
            "family_count": self.family_count,
            "baseline_count": self.baseline_count,
            "endpoint_count": self.endpoint_count,
            "familywise_alpha": self.familywise_alpha,
            "quality_noninferiority_margin": self.quality_noninferiority_margin,
            "catastrophic_regret_noninferiority_margin": self.catastrophic_regret_noninferiority_margin,
            "minimum_cost_effect_of_interest": self.minimum_cost_effect_of_interest,
            "calibration_fraction": self.calibration_fraction,
            "target_power": self.target_power,
            "min_trials_per_task": self.min_trials_per_task,
            "max_trials_per_task": self.max_trials_per_task,
            "method": self.method,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


def deterministic_task_split(
    task_ids: Iterable[str], *, calibration_fraction: float = 0.20
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    tasks = tuple(sorted({str(x).strip() for x in task_ids if str(x).strip()}))
    if len(tasks) < 5:
        raise ValueError("at least five tasks required for calibration/confirmatory split")
    if not 0.0 < calibration_fraction < 0.5:
        raise ValueError("calibration_fraction must be in (0,0.5)")
    ranked = sorted(
        tasks,
        key=lambda task: hashlib.sha256(("DGC-SPLIT-V1:" + task).encode("utf-8")).digest(),
    )
    n_cal = max(1, int(math.floor(len(ranked) * calibration_fraction)))
    calibration = tuple(sorted(ranked[:n_cal]))
    confirmatory = tuple(sorted(ranked[n_cal:]))
    if set(calibration) & set(confirmatory) or len(calibration) + len(confirmatory) != len(tasks):
        raise RuntimeError("internal split integrity failure")
    return calibration, confirmatory


def approximate_required_trials_per_task(
    *,
    calibration_std: float,
    effect_of_interest: float,
    confirmatory_task_count: int,
    plan: ProductStatisticalPlan,
) -> int:
    """Pre-execution normal-approximation power sizing from calibration-only variance.

    This sizes repeated trials; it is not the confirmatory inference procedure.
    If the required count exceeds the hard cap, the experiment is underpowered
    under the frozen plan and must not silently lower its evidence standard.
    """
    sigma = float(calibration_std)
    effect = float(effect_of_interest)
    if not math.isfinite(sigma) or sigma < 0.0:
        raise ValueError("calibration_std must be finite and >= 0")
    if not math.isfinite(effect) or effect <= 0.0:
        raise ValueError("effect_of_interest must be finite and > 0")
    if confirmatory_task_count <= 0:
        raise ValueError("confirmatory_task_count must be > 0")
    z_alpha = NormalDist().inv_cdf(1.0 - plan.per_claim_alpha)
    z_power = NormalDist().inv_cdf(plan.target_power)
    total_required = ((z_alpha + z_power) * sigma / effect) ** 2
    per_task = max(plan.min_trials_per_task, int(math.ceil(total_required / confirmatory_task_count)))
    if per_task > plan.max_trials_per_task:
        raise RuntimeError(
            f"UNDERPOWERED: required_trials_per_task={per_task} exceeds cap={plan.max_trials_per_task}"
        )
    return per_task
