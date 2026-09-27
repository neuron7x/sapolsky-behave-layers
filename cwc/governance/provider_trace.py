from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from cwc.governance.cost_accounting import MeteredDecisionCost, ProviderRateCard


def _nonnegative_int(name: str, value: int) -> int:
    value = int(value)
    if value < 0:
        raise ValueError(f"{name} must be >= 0")
    return value


def _nonnegative_float(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and >= 0")
    return value


def _digest(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


class TraceAuthority(str, Enum):
    SYNTHETIC = "SYNTHETIC"
    LOCAL_EXPERIMENT = "LOCAL_EXPERIMENT"
    PROVIDER_LIVE = "PROVIDER_LIVE"
    CLIENT_PRODUCTION = "CLIENT_PRODUCTION"


@dataclass(frozen=True, slots=True)
class ProviderUsageTrace:
    trace_id: str
    decision_id: str
    policy_id: str
    authority: TraceAuthority
    provider: str
    model: str
    rate_card_digest: str
    input_tokens: int
    cached_input_tokens: int
    cache_write_tokens: int
    long_cache_write_tokens: int
    output_tokens: int
    tool_usd: float = 0.0
    retrieval_usd: float = 0.0
    governor_usd: float = 0.0
    monitor_usd: float = 0.0
    retry_usd: float = 0.0
    gpu_usd: float = 0.0
    other_provider_usd: float = 0.0
    latency_penalty_usd: float = 0.0
    quality_score: float | None = None
    covered: bool = True
    provider_request_id: str | None = None

    def __post_init__(self) -> None:
        required = (self.trace_id, self.decision_id, self.policy_id, self.provider, self.model, self.rate_card_digest)
        if not all(str(x).strip() for x in required):
            raise ValueError("trace/decision/policy/provider/model/rate-card ids are required")
        for name in ("input_tokens", "cached_input_tokens", "cache_write_tokens", "long_cache_write_tokens", "output_tokens"):
            object.__setattr__(self, name, _nonnegative_int(name, getattr(self, name)))
        used_input = self.cached_input_tokens + self.cache_write_tokens + self.long_cache_write_tokens
        if used_input > self.input_tokens:
            raise ValueError("cached/cache-write token subsets cannot exceed input tokens")
        for name in (
            "tool_usd", "retrieval_usd", "governor_usd", "monitor_usd", "retry_usd",
            "gpu_usd", "other_provider_usd", "latency_penalty_usd",
        ):
            object.__setattr__(self, name, _nonnegative_float(name, getattr(self, name)))
        if self.quality_score is not None:
            q = float(self.quality_score)
            if not math.isfinite(q):
                raise ValueError("quality_score must be finite when present")
            object.__setattr__(self, "quality_score", q)
        if self.authority in {TraceAuthority.PROVIDER_LIVE, TraceAuthority.CLIENT_PRODUCTION} and not self.provider_request_id:
            raise ValueError("live provider/client traces require provider_request_id")

    @property
    def digest(self) -> str:
        return _digest({
            "trace_id": self.trace_id,
            "decision_id": self.decision_id,
            "policy_id": self.policy_id,
            "authority": self.authority.value,
            "provider": self.provider,
            "model": self.model,
            "rate_card_digest": self.rate_card_digest,
            "input_tokens": self.input_tokens,
            "cached_input_tokens": self.cached_input_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "long_cache_write_tokens": self.long_cache_write_tokens,
            "output_tokens": self.output_tokens,
            "tool_usd": self.tool_usd,
            "retrieval_usd": self.retrieval_usd,
            "governor_usd": self.governor_usd,
            "monitor_usd": self.monitor_usd,
            "retry_usd": self.retry_usd,
            "gpu_usd": self.gpu_usd,
            "other_provider_usd": self.other_provider_usd,
            "latency_penalty_usd": self.latency_penalty_usd,
            "quality_score": self.quality_score,
            "covered": self.covered,
            "provider_request_id": self.provider_request_id,
        })

    def meter(self, rate_card: ProviderRateCard) -> MeteredDecisionCost:
        if rate_card.digest != self.rate_card_digest:
            raise ValueError("RATE_CARD_DIGEST_MISMATCH")
        if (rate_card.provider, rate_card.model) != (self.provider, self.model):
            raise ValueError("RATE_CARD_IDENTITY_MISMATCH")
        token_usd = rate_card.token_cost_usd(
            input_tokens=self.input_tokens,
            cached_input_tokens=self.cached_input_tokens,
            cache_write_tokens=self.cache_write_tokens,
            long_cache_write_tokens=self.long_cache_write_tokens,
            output_tokens=self.output_tokens,
        )
        return MeteredDecisionCost(
            trace_id=self.trace_id,
            rate_card_digest=self.rate_card_digest,
            model_token_usd=token_usd,
            tool_usd=self.tool_usd,
            retrieval_usd=self.retrieval_usd,
            governor_usd=self.governor_usd,
            monitor_usd=self.monitor_usd,
            retry_usd=self.retry_usd,
            gpu_usd=self.gpu_usd,
            other_provider_usd=self.other_provider_usd,
            latency_penalty_usd=self.latency_penalty_usd,
        )


@dataclass(frozen=True, slots=True)
class ClientVerificationCertificate:
    workload_id: str
    decision_pairs: int
    baseline_policy: str
    dgc_policy: str
    point_savings: float
    savings_lower_bound: float
    point_quality_delta: float
    quality_delta_lower_bound: float
    coverage_equal: bool
    all_traces_client_production: bool
    all_rate_cards_bound: bool
    commercial_claim_allowed: bool
    reason_code: str


def verify_client_evidence(
    *,
    workload_id: str,
    traces: tuple[ProviderUsageTrace, ...],
    rate_cards: Mapping[str, ProviderRateCard],
    baseline_policy: str,
    dgc_policy: str,
    savings_lower_bound: float | None,
    quality_delta_lower_bound: float | None,
    minimum_savings: float = 0.30,
) -> ClientVerificationCertificate:
    """Fail-closed commercial authority verifier.

    Statistical lower bounds are external preregistered evidence. This function
    never manufactures bounds from arbitrary production traces.
    """
    if not workload_id.strip() or baseline_policy == dgc_policy:
        raise ValueError("valid workload and distinct policies required")
    if not traces:
        return ClientVerificationCertificate(workload_id, 0, baseline_policy, dgc_policy, 0.0, float("-inf"), 0.0, float("-inf"), False, False, False, False, "NO_CLIENT_TRACES")

    groups: dict[str, dict[str, ProviderUsageTrace]] = {}
    for t in traces:
        if t.policy_id not in {baseline_policy, dgc_policy}:
            continue
        slot = groups.setdefault(t.decision_id, {})
        if t.policy_id in slot:
            raise ValueError("duplicate policy trace for decision")
        slot[t.policy_id] = t
    pairs = [g for g in groups.values() if baseline_policy in g and dgc_policy in g]
    if len(pairs) != len(groups) or not pairs:
        return ClientVerificationCertificate(workload_id, len(pairs), baseline_policy, dgc_policy, 0.0, float("-inf"), 0.0, float("-inf"), False, False, False, False, "UNPAIRED_CLIENT_TRACES")

    all_client = all(t.authority is TraceAuthority.CLIENT_PRODUCTION for g in pairs for t in g.values())
    coverage_equal = all(g[baseline_policy].covered == g[dgc_policy].covered for g in pairs)
    all_bound = all(t.rate_card_digest in rate_cards for g in pairs for t in g.values())
    if not all_bound:
        return ClientVerificationCertificate(workload_id, len(pairs), baseline_policy, dgc_policy, 0.0, float("-inf"), 0.0, float("-inf"), coverage_equal, all_client, False, False, "RATE_CARD_UNBOUND")

    base_cost = sum(g[baseline_policy].meter(rate_cards[g[baseline_policy].rate_card_digest]).total_usd for g in pairs)
    dgc_cost = sum(g[dgc_policy].meter(rate_cards[g[dgc_policy].rate_card_digest]).total_usd for g in pairs)
    if base_cost <= 0:
        raise ValueError("positive baseline metered cost required")
    point_savings = 1.0 - dgc_cost / base_cost

    q_pairs = [(g[baseline_policy].quality_score, g[dgc_policy].quality_score) for g in pairs]
    if any(a is None or b is None for a, b in q_pairs):
        point_quality = float("nan")
    else:
        point_quality = sum(float(b) - float(a) for a, b in q_pairs) / len(q_pairs)

    if savings_lower_bound is None or quality_delta_lower_bound is None:
        return ClientVerificationCertificate(workload_id, len(pairs), baseline_policy, dgc_policy, point_savings, float("-inf"), point_quality, float("-inf"), coverage_equal, all_client, all_bound, False, "PREREGISTERED_BOUNDS_MISSING")
    s_lcb = float(savings_lower_bound)
    q_lcb = float(quality_delta_lower_bound)
    if not math.isfinite(s_lcb) or not math.isfinite(q_lcb):
        raise ValueError("finite external bounds required")
    allowed = all_client and coverage_equal and all_bound and s_lcb >= minimum_savings and q_lcb >= 0.0
    reason = "CLIENT_VERIFIED" if allowed else "CLIENT_VERIFICATION_GATE_FAILED"
    return ClientVerificationCertificate(workload_id, len(pairs), baseline_policy, dgc_policy, point_savings, s_lcb, point_quality, q_lcb, coverage_equal, all_client, all_bound, allowed, reason)
