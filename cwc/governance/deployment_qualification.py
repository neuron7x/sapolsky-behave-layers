from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

from cwc.governance.product_evidence import ProductEvidenceRecord


def _req(name: str, value: str) -> str:
    value = str(value).strip()
    if not value:
        raise ValueError(f"{name} required")
    return value


def _fraction(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be in [0,1]")
    return value


def _nonnegative(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0.0:
        raise ValueError(f"{name} must be finite and >=0")
    return value


@dataclass(frozen=True, slots=True)
class ShadowQualificationPlan:
    min_trials: int
    min_coverage: float
    max_false_stop_rate: float
    max_mean_regret: float
    max_p95_latency_overhead_ms: float
    plan_authority_digest: str

    def __post_init__(self) -> None:
        if self.min_trials <= 0:
            raise ValueError("min_trials must be >0")
        object.__setattr__(self, "min_coverage", _fraction("min_coverage", self.min_coverage))
        object.__setattr__(self, "max_false_stop_rate", _fraction("max_false_stop_rate", self.max_false_stop_rate))
        object.__setattr__(self, "max_mean_regret", _nonnegative("max_mean_regret", self.max_mean_regret))
        object.__setattr__(self, "max_p95_latency_overhead_ms", _nonnegative("max_p95_latency_overhead_ms", self.max_p95_latency_overhead_ms))
        object.__setattr__(self, "plan_authority_digest", _req("plan_authority_digest", self.plan_authority_digest))


@dataclass(frozen=True, slots=True)
class ShadowQualificationResult:
    trials: int
    coverage: float
    false_stop_rate: float
    mean_regret: float
    p95_latency_overhead_ms: float
    baseline_action_authority_digest: str
    outcome_scorer_digest: str
    dgc_had_control_authority: bool
    qualified: bool


def qualify_shadow_mode(
    *,
    plan: ShadowQualificationPlan,
    trials: int,
    coverage: float,
    false_stop_rate: float,
    mean_regret: float,
    p95_latency_overhead_ms: float,
    baseline_action_authority_digest: str,
    outcome_scorer_digest: str,
    dgc_had_control_authority: bool,
) -> ShadowQualificationResult:
    if trials < 0:
        raise ValueError("trials must be >=0")
    coverage = _fraction("coverage", coverage)
    false_stop_rate = _fraction("false_stop_rate", false_stop_rate)
    mean_regret = _nonnegative("mean_regret", mean_regret)
    latency = _nonnegative("p95_latency_overhead_ms", p95_latency_overhead_ms)
    baseline_digest = _req("baseline_action_authority_digest", baseline_action_authority_digest)
    scorer_digest = _req("outcome_scorer_digest", outcome_scorer_digest)
    if dgc_had_control_authority:
        raise ValueError("shadow evidence invalid if DGC controlled the production action")
    qualified = (
        trials >= plan.min_trials
        and coverage >= plan.min_coverage
        and false_stop_rate <= plan.max_false_stop_rate
        and mean_regret <= plan.max_mean_regret
        and latency <= plan.max_p95_latency_overhead_ms
    )
    return ShadowQualificationResult(
        trials=trials,
        coverage=coverage,
        false_stop_rate=false_stop_rate,
        mean_regret=mean_regret,
        p95_latency_overhead_ms=latency,
        baseline_action_authority_digest=baseline_digest,
        outcome_scorer_digest=scorer_digest,
        dgc_had_control_authority=False,
        qualified=qualified,
    )


@dataclass(frozen=True, slots=True)
class CanaryLimits:
    traffic_fraction: float
    max_spend_usd_per_task: float
    max_tool_calls: int
    max_reasoning_steps: int
    max_wall_time_ms: int
    max_concurrency: int
    automatic_baseline_fallback: bool
    rollback_test_digest: str

    def __post_init__(self) -> None:
        fraction = float(self.traffic_fraction)
        if not math.isfinite(fraction) or not 0.0 < fraction <= 0.1:
            raise ValueError("canary traffic_fraction must be in (0,0.1]")
        object.__setattr__(self, "traffic_fraction", fraction)
        object.__setattr__(self, "max_spend_usd_per_task", _nonnegative("max_spend_usd_per_task", self.max_spend_usd_per_task))
        if min(self.max_tool_calls, self.max_reasoning_steps, self.max_wall_time_ms, self.max_concurrency) <= 0:
            raise ValueError("canary hard limits must be positive")
        if not self.automatic_baseline_fallback:
            raise ValueError("automatic baseline fallback is mandatory")
        object.__setattr__(self, "rollback_test_digest", _req("rollback_test_digest", self.rollback_test_digest))

    @property
    def digest(self) -> str:
        payload = {
            "traffic_fraction": self.traffic_fraction,
            "max_spend_usd_per_task": self.max_spend_usd_per_task,
            "max_tool_calls": self.max_tool_calls,
            "max_reasoning_steps": self.max_reasoning_steps,
            "max_wall_time_ms": self.max_wall_time_ms,
            "max_concurrency": self.max_concurrency,
            "automatic_baseline_fallback": self.automatic_baseline_fallback,
            "rollback_test_digest": self.rollback_test_digest,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def authorize_bounded_canary(
    *, evidence: ProductEvidenceRecord, shadow: ShadowQualificationResult, limits: CanaryLimits
) -> str:
    if not evidence.product_qualified:
        raise RuntimeError("bounded canary prohibited before PRODUCT_QUALIFIED")
    if not shadow.qualified:
        raise RuntimeError("bounded canary prohibited before shadow qualification")
    return limits.digest
