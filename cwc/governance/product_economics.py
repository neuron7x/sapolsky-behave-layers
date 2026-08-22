from __future__ import annotations

import math
from dataclasses import dataclass


def _nn(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"{name} must be finite and >= 0")
    return value


@dataclass(frozen=True, slots=True)
class ProductTrialCost:
    model_usd: float
    router_usd: float
    countermodel_usd: float
    retrieval_usd: float
    tools_usd: float
    verification_usd: float
    human_review_usd: float
    infra_usd: float
    retry_usd: float
    failure_loss_usd: float

    def __post_init__(self) -> None:
        for name in (
            "model_usd", "router_usd", "countermodel_usd", "retrieval_usd",
            "tools_usd", "verification_usd", "human_review_usd", "infra_usd",
            "retry_usd", "failure_loss_usd",
        ):
            object.__setattr__(self, name, _nn(name, getattr(self, name)))

    @property
    def total_operational_usd(self) -> float:
        return math.fsum((
            self.model_usd,
            self.router_usd,
            self.countermodel_usd,
            self.retrieval_usd,
            self.tools_usd,
            self.verification_usd,
            self.human_review_usd,
            self.infra_usd,
            self.retry_usd,
            self.failure_loss_usd,
        ))


@dataclass(frozen=True, slots=True)
class ProductTrialOutcome:
    task_id: str
    policy_id: str
    cost: ProductTrialCost
    accepted_success: bool
    quality_gate_passed: bool
    catastrophic_regret_gate_passed: bool
    coverage_gate_passed: bool

    @property
    def product_accepted(self) -> bool:
        return (
            self.accepted_success
            and self.quality_gate_passed
            and self.catastrophic_regret_gate_passed
            and self.coverage_gate_passed
        )


@dataclass(frozen=True, slots=True)
class ProductEconomicsCertificate:
    policy_id: str
    tasks: int
    accepted_successes: int
    total_operational_usd: float
    cost_per_accepted_success_usd: float
    full_task_coverage: bool


def certify_product_economics(trials: list[ProductTrialOutcome]) -> ProductEconomicsCertificate:
    if not trials:
        raise ValueError("non-empty trial population required")
    policies = {t.policy_id for t in trials}
    if len(policies) != 1:
        raise ValueError("one policy per economics certificate required")
    task_ids = [t.task_id for t in trials]
    if any(not x.strip() for x in task_ids) or len(set(task_ids)) != len(task_ids):
        raise ValueError("task ids must be unique and non-empty")
    total = math.fsum(t.cost.total_operational_usd for t in trials)
    accepted = sum(t.product_accepted for t in trials)
    if accepted == 0:
        cps = math.inf
    else:
        cps = total / accepted
    return ProductEconomicsCertificate(
        policy_id=next(iter(policies)),
        tasks=len(trials),
        accepted_successes=accepted,
        total_operational_usd=total,
        cost_per_accepted_success_usd=cps,
        full_task_coverage=True,
    )


def net_saving(reference: ProductEconomicsCertificate, candidate: ProductEconomicsCertificate) -> float:
    if reference.tasks != candidate.tasks:
        raise ValueError("paired comparison requires equal task counts")
    if reference.accepted_successes != candidate.accepted_successes:
        raise ValueError("net saving is not authorized when accepted-success counts differ")
    if reference.total_operational_usd <= 0.0:
        raise ValueError("reference total operational cost must be > 0")
    return 1.0 - candidate.total_operational_usd / reference.total_operational_usd
