from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass


def _nonnegative(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and >= 0")
    return value


def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class ProviderRateCard:
    provider: str
    model: str
    input_usd_per_million: float
    cached_input_usd_per_million: float
    output_usd_per_million: float
    cache_write_usd_per_million: float = 0.0
    long_cache_write_usd_per_million: float = 0.0
    source_uri: str = ""
    retrieved_at: str = ""

    def __post_init__(self) -> None:
        if not all(str(x).strip() for x in (self.provider, self.model, self.source_uri, self.retrieved_at)):
            raise ValueError("provider/model/source/retrieved_at are required")
        for name in (
            "input_usd_per_million", "cached_input_usd_per_million", "output_usd_per_million",
            "cache_write_usd_per_million", "long_cache_write_usd_per_million",
        ):
            object.__setattr__(self, name, _nonnegative(name, getattr(self, name)))

    @property
    def digest(self) -> str:
        return _digest({
            "provider": self.provider,
            "model": self.model,
            "input_usd_per_million": self.input_usd_per_million,
            "cached_input_usd_per_million": self.cached_input_usd_per_million,
            "output_usd_per_million": self.output_usd_per_million,
            "cache_write_usd_per_million": self.cache_write_usd_per_million,
            "long_cache_write_usd_per_million": self.long_cache_write_usd_per_million,
            "source_uri": self.source_uri,
            "retrieved_at": self.retrieved_at,
        })

    def token_cost_usd(
        self, *, input_tokens: int, cached_input_tokens: int, output_tokens: int,
        cache_write_tokens: int = 0, long_cache_write_tokens: int = 0,
    ) -> float:
        counts = (input_tokens, cached_input_tokens, cache_write_tokens, long_cache_write_tokens, output_tokens)
        if min(counts) < 0:
            raise ValueError("token counts must be >= 0")
        special = cached_input_tokens + cache_write_tokens + long_cache_write_tokens
        if special > input_tokens:
            raise ValueError("cached/cache-write input subsets cannot exceed input tokens")
        uncached = input_tokens - special
        return (
            uncached * self.input_usd_per_million
            + cached_input_tokens * self.cached_input_usd_per_million
            + cache_write_tokens * self.cache_write_usd_per_million
            + long_cache_write_tokens * self.long_cache_write_usd_per_million
            + output_tokens * self.output_usd_per_million
        ) / 1_000_000.0


@dataclass(frozen=True, slots=True)
class MeteredDecisionCost:
    trace_id: str
    rate_card_digest: str
    model_token_usd: float
    tool_usd: float
    retrieval_usd: float
    governor_usd: float
    monitor_usd: float
    retry_usd: float
    gpu_usd: float
    other_provider_usd: float
    latency_penalty_usd: float

    def __post_init__(self) -> None:
        if not self.trace_id.strip() or not self.rate_card_digest.strip():
            raise ValueError("trace_id and rate_card_digest required")
        for name in (
            "model_token_usd", "tool_usd", "retrieval_usd", "governor_usd", "monitor_usd",
            "retry_usd", "gpu_usd", "other_provider_usd", "latency_penalty_usd",
        ):
            object.__setattr__(self, name, _nonnegative(name, getattr(self, name)))

    @property
    def total_usd(self) -> float:
        return sum((
            self.model_token_usd, self.tool_usd, self.retrieval_usd, self.governor_usd,
            self.monitor_usd, self.retry_usd, self.gpu_usd, self.other_provider_usd,
            self.latency_penalty_usd,
        ))

    @property
    def digest(self) -> str:
        return _digest({
            "trace_id": self.trace_id,
            "rate_card_digest": self.rate_card_digest,
            "model_token_usd": self.model_token_usd,
            "tool_usd": self.tool_usd,
            "retrieval_usd": self.retrieval_usd,
            "governor_usd": self.governor_usd,
            "monitor_usd": self.monitor_usd,
            "retry_usd": self.retry_usd,
            "gpu_usd": self.gpu_usd,
            "other_provider_usd": self.other_provider_usd,
            "latency_penalty_usd": self.latency_penalty_usd,
        })
