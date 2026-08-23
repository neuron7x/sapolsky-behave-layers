from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Iterable


def _nn(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"{name} must be finite and >= 0")
    return value


def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


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
    trial_id: str
    task_id: str
    policy_id: str
    cost: ProductTrialCost
    accepted_success: bool
    quality_gate_passed: bool
    catastrophic_regret_gate_passed: bool
    coverage_gate_passed: bool

    def __post_init__(self) -> None:
        if not all(x.strip() for x in (self.trial_id, self.task_id, self.policy_id)):
            raise ValueError("trial_id, task_id and policy_id are required")

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
    trials: int
    tasks_observed: int
    tasks_expected: int
    accepted_successes: int
    total_operational_usd: float
    cost_per_accepted_success_usd: float
    task_coverage_fraction: float
    full_task_coverage: bool
    trial_population_digest: str
    trial_counts_by_task: tuple[tuple[str, int], ...]


def certify_product_economics(
    trials: list[ProductTrialOutcome], *, expected_task_ids: Iterable[str]
) -> ProductEconomicsCertificate:
    if not trials:
        raise ValueError("non-empty trial population required")
    policies = {t.policy_id for t in trials}
    if len(policies) != 1:
        raise ValueError("one policy per economics certificate required")
    trial_ids = [t.trial_id for t in trials]
    if len(set(trial_ids)) != len(trial_ids):
        raise ValueError("trial_id must be unique; repeated task_id is allowed")

    expected = tuple(sorted({str(x).strip() for x in expected_task_ids if str(x).strip()}))
    if not expected:
        raise ValueError("expected_task_ids must be a non-empty frozen task population")
    observed = {t.task_id for t in trials}
    if not observed.issubset(set(expected)):
        raise ValueError("observed task outside frozen expected task population")

    counts = tuple(sorted((task, sum(t.task_id == task for t in trials)) for task in observed))
    total = math.fsum(t.cost.total_operational_usd for t in trials)
    accepted = sum(t.product_accepted for t in trials)
    cps = math.inf if accepted == 0 else total / accepted
    coverage = len(observed) / len(expected)

    population_rows = sorted((t.trial_id, t.task_id) for t in trials)
    population_digest = _digest({"expected_tasks": expected, "trials": population_rows})
    return ProductEconomicsCertificate(
        policy_id=next(iter(policies)),
        trials=len(trials),
        tasks_observed=len(observed),
        tasks_expected=len(expected),
        accepted_successes=accepted,
        total_operational_usd=total,
        cost_per_accepted_success_usd=cps,
        task_coverage_fraction=coverage,
        full_task_coverage=coverage == 1.0,
        trial_population_digest=population_digest,
        trial_counts_by_task=counts,
    )


def net_saving(
    reference: ProductEconomicsCertificate,
    candidate: ProductEconomicsCertificate,
    *,
    quality_noninferiority_certified: bool,
    catastrophic_regret_noninferiority_certified: bool,
    coverage_equivalence_certified: bool,
) -> float:
    """Authorize total-cost saving only after non-cost product gates pass.

    This deliberately does not infer quality from accepted-success counts. Quality,
    catastrophic-regret and coverage equivalence must be independently certified
    on the same frozen paired trial population before a net-saving claim is emitted.
    """
    if reference.trial_population_digest != candidate.trial_population_digest:
        raise ValueError("paired comparison requires the exact same frozen trial population")
    if not (reference.full_task_coverage and candidate.full_task_coverage):
        raise ValueError("full frozen task coverage required")
    if not (
        quality_noninferiority_certified
        and catastrophic_regret_noninferiority_certified
        and coverage_equivalence_certified
    ):
        raise ValueError("net saving requires independently certified quality/regret/coverage gates")
    if reference.total_operational_usd <= 0.0:
        raise ValueError("reference total operational cost must be > 0")
    return 1.0 - candidate.total_operational_usd / reference.total_operational_usd


def cps_improvement(
    reference: ProductEconomicsCertificate, candidate: ProductEconomicsCertificate
) -> float:
    if reference.trial_population_digest != candidate.trial_population_digest:
        raise ValueError("paired comparison requires the exact same frozen trial population")
    if not math.isfinite(reference.cost_per_accepted_success_usd) or reference.cost_per_accepted_success_usd <= 0:
        raise ValueError("reference CPS must be finite and > 0")
    if not math.isfinite(candidate.cost_per_accepted_success_usd):
        return -math.inf
    return 1.0 - candidate.cost_per_accepted_success_usd / reference.cost_per_accepted_success_usd
