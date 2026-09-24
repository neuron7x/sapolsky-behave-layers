from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from statistics import NormalDist
from typing import Iterable

from cwc.governance.average_conditional_mean_cs import (
    ASSUMPTION_BOUNDARY as PRIMARY_ASSUMPTION_BOUNDARY,
    BOUNDARY_METHOD as PRIMARY_BOUNDARY_METHOD,
    CLAIM_TARGET as PRIMARY_CLAIM_TARGET,
    CONFSEQ_REFERENCE_COMMIT,
    METHOD as PRIMARY_INFERENCE_METHOD,
    PREDICTOR_RULE as PRIMARY_PREDICTOR_RULE,
    SEQUENCE_ORDER_RULE as PRIMARY_SEQUENCE_ORDER,
)

PLAN_METHOD = "DGC_PRODUCT_ANYTIME_VALID_ACM_V5_EXACT_STITCHING_THREE_WAY_HOLDOUT"


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
    generalization_holdout_fraction: float = 0.20
    target_power: float = 0.90
    min_trials_per_task: int = 5
    max_trials_per_task: int = 50
    primary_inference_method: str = PRIMARY_INFERENCE_METHOD
    primary_boundary_method: str = PRIMARY_BOUNDARY_METHOD
    primary_claim_target: str = PRIMARY_CLAIM_TARGET
    primary_assumption_boundary: str = PRIMARY_ASSUMPTION_BOUNDARY
    primary_sequence_order: str = PRIMARY_SEQUENCE_ORDER
    primary_predictor_rule: str = PRIMARY_PREDICTOR_RULE
    confseq_reference_commit: str = CONFSEQ_REFERENCE_COMMIT
    method: str = PLAN_METHOD

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
        if not 0.0 < self.generalization_holdout_fraction < 0.5:
            raise ValueError("generalization_holdout_fraction must be in (0,0.5)")
        if self.calibration_fraction + self.generalization_holdout_fraction >= 0.5:
            raise ValueError("calibration + generalization holdout must leave >50% for confirmatory tasks")
        if not 0.5 < self.target_power < 1.0:
            raise ValueError("target_power must be in (0.5,1)")
        if not (1 <= self.min_trials_per_task <= self.max_trials_per_task):
            raise ValueError("invalid trial bounds")
        frozen = {
            "primary_inference_method": (self.primary_inference_method, PRIMARY_INFERENCE_METHOD),
            "primary_boundary_method": (self.primary_boundary_method, PRIMARY_BOUNDARY_METHOD),
            "primary_claim_target": (self.primary_claim_target, PRIMARY_CLAIM_TARGET),
            "primary_assumption_boundary": (self.primary_assumption_boundary, PRIMARY_ASSUMPTION_BOUNDARY),
            "primary_sequence_order": (self.primary_sequence_order, PRIMARY_SEQUENCE_ORDER),
            "primary_predictor_rule": (self.primary_predictor_rule, PRIMARY_PREDICTOR_RULE),
            "confseq_reference_commit": (self.confseq_reference_commit, CONFSEQ_REFERENCE_COMMIT),
            "method": (self.method, PLAN_METHOD),
        }
        for name, (observed, expected) in frozen.items():
            if observed != expected:
                raise ValueError(f"{name} must equal frozen V5 identity")

    @property
    def per_claim_alpha(self) -> float:
        return self.familywise_alpha / (self.family_count * self.baseline_count * self.endpoint_count)

    @property
    def per_family_alpha(self) -> float:
        return self.familywise_alpha / self.family_count

    @property
    def boundary_crossing_alpha_per_claim(self) -> float:
        # Theorem 4 has two-sided coverage 1-2*alpha_boundary.
        return self.per_claim_alpha / 2.0

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
            "generalization_holdout_fraction": self.generalization_holdout_fraction,
            "target_power": self.target_power,
            "min_trials_per_task": self.min_trials_per_task,
            "max_trials_per_task": self.max_trials_per_task,
            "primary_inference_method": self.primary_inference_method,
            "primary_boundary_method": self.primary_boundary_method,
            "primary_claim_target": self.primary_claim_target,
            "primary_assumption_boundary": self.primary_assumption_boundary,
            "primary_sequence_order": self.primary_sequence_order,
            "primary_predictor_rule": self.primary_predictor_rule,
            "confseq_reference_commit": self.confseq_reference_commit,
            "method": self.method,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()


def _rank_tasks(task_ids: Iterable[str], *, salt: str) -> tuple[str, ...]:
    tasks = tuple(sorted({str(x).strip() for x in task_ids if str(x).strip()}))
    return tuple(sorted(tasks, key=lambda task: hashlib.sha256((salt + task).encode("utf-8")).digest()))


def deterministic_three_way_task_split(
    task_ids: Iterable[str],
    *,
    calibration_fraction: float = 0.20,
    generalization_holdout_fraction: float = 0.20,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    """Freeze calibration, confirmatory and G1-generalization populations pre-outcome."""
    ranked = _rank_tasks(task_ids, salt="DGC-SPLIT-V3:")
    if len(ranked) < 10:
        raise ValueError("at least ten tasks required for three-way product partition")
    if not 0.0 < calibration_fraction < 0.5:
        raise ValueError("calibration_fraction must be in (0,0.5)")
    if not 0.0 < generalization_holdout_fraction < 0.5:
        raise ValueError("generalization_holdout_fraction must be in (0,0.5)")
    if calibration_fraction + generalization_holdout_fraction >= 0.5:
        raise ValueError("calibration + G1 holdout must leave >50% for confirmatory tasks")

    n_total = len(ranked)
    n_cal = max(1, int(math.floor(n_total * calibration_fraction)))
    n_g1 = max(1, int(math.floor(n_total * generalization_holdout_fraction)))
    if n_cal + n_g1 >= n_total - 1:
        raise ValueError("three-way partition leaves too few confirmatory tasks")

    calibration = tuple(sorted(ranked[:n_cal]))
    generalization = tuple(sorted(ranked[n_cal : n_cal + n_g1]))
    confirmatory = tuple(sorted(ranked[n_cal + n_g1 :]))
    populations = (set(calibration), set(confirmatory), set(generalization))
    if any(populations[i] & populations[j] for i in range(3) for j in range(i + 1, 3)):
        raise RuntimeError("internal three-way split overlap")
    if sum(len(population) for population in populations) != n_total:
        raise RuntimeError("internal three-way split population loss")
    return calibration, confirmatory, generalization


def deterministic_task_split(
    task_ids: Iterable[str], *, calibration_fraction: float = 0.20
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Legacy two-way research split; not product-authorized after V3."""
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


@dataclass(frozen=True, slots=True)
class ClusterAwareTrialSizing:
    confirmatory_task_count: int
    between_task_std: float
    within_task_std: float
    effect_of_interest: float
    target_standard_error: float
    asymptotic_between_task_standard_error: float
    required_trials_per_task: int
    achieved_standard_error_at_required_trials: float
    per_claim_alpha: float
    target_power: float
    method: str = "NORMAL_APPROX_CLUSTER_VARIANCE_COMPONENTS_V1_PLANNING_ONLY"


def cluster_aware_required_trials_per_task(
    *,
    between_task_std: float,
    within_task_std: float,
    effect_of_interest: float,
    confirmatory_task_count: int,
    plan: ProductStatisticalPlan,
) -> ClusterAwareTrialSizing:
    """Calibration-only resource planning for repeated trials nested within tasks.

    This is not the V5 confirmatory inference theorem. It remains a conservative
    resource-planning diagnostic for task diversity and within-task noise.
    """
    between = float(between_task_std)
    within = float(within_task_std)
    effect = float(effect_of_interest)
    if not math.isfinite(between) or between < 0:
        raise ValueError("between_task_std must be finite and >= 0")
    if not math.isfinite(within) or within < 0:
        raise ValueError("within_task_std must be finite and >= 0")
    if not math.isfinite(effect) or effect <= 0:
        raise ValueError("effect_of_interest must be finite and > 0")
    if confirmatory_task_count <= 1:
        raise ValueError("confirmatory_task_count must be > 1 for clustered sizing")

    z_alpha = NormalDist().inv_cdf(1.0 - plan.per_claim_alpha)
    z_power = NormalDist().inv_cdf(plan.target_power)
    target_se = effect / (z_alpha + z_power)
    n_tasks = int(confirmatory_task_count)
    between_var = between * between
    within_var = within * within
    asymptotic_se = math.sqrt(between_var / n_tasks)
    available_within_variance = n_tasks * target_se * target_se - between_var

    if available_within_variance <= 0:
        raise RuntimeError(
            "UNDERPOWERED_TASK_HETEROGENEITY: no number of within-task repeats can meet the frozen planning target; "
            f"asymptotic_se={asymptotic_se:.8f} target_se={target_se:.8f}"
        )

    raw_required = 1 if within_var == 0 else math.ceil(within_var / available_within_variance)
    required = max(plan.min_trials_per_task, int(raw_required))
    if required > plan.max_trials_per_task:
        raise RuntimeError(
            f"UNDERPOWERED: required_trials_per_task={required} exceeds cap={plan.max_trials_per_task}"
        )
    achieved_se = math.sqrt(between_var / n_tasks + within_var / (n_tasks * required))
    return ClusterAwareTrialSizing(
        confirmatory_task_count=n_tasks,
        between_task_std=between,
        within_task_std=within,
        effect_of_interest=effect,
        target_standard_error=target_se,
        asymptotic_between_task_standard_error=asymptotic_se,
        required_trials_per_task=required,
        achieved_standard_error_at_required_trials=achieved_se,
        per_claim_alpha=plan.per_claim_alpha,
        target_power=plan.target_power,
    )


def approximate_required_trials_per_task(
    *,
    calibration_std: float,
    effect_of_interest: float,
    confirmatory_task_count: int,
    plan: ProductStatisticalPlan,
) -> int:
    """Legacy IID-only sizing helper; research compatibility only."""
    sigma = float(calibration_std)
    effect = float(effect_of_interest)
    if not math.isfinite(sigma) or sigma < 0.0:
        raise ValueError("calibration_std must be finite and >= 0")
    if not math.isfinite(effect) or effect <= 0.0:
        raise ValueError("effect_of_interest must be finite and > 0.0")
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
