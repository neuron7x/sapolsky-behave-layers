from __future__ import annotations

import hashlib
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from .trace import InferenceTrace


@dataclass(slots=True)
class ShadowObserver:
    """Non-interfering sidecar: receives immutable post-generation metadata only."""

    sink: Callable[[InferenceTrace], None]
    model_commit: str = "UNKNOWN"
    checkpoint_hash: str = "UNKNOWN"
    tokenizer_hash: str = "UNKNOWN"
    counterfactual_model_version: str = "RESEARCH_ONLY"
    credit_estimator_version: str = "RESEARCH_ONLY"

    @staticmethod
    def _hash_tokens(tokens: Sequence[int]) -> str:
        payload = ",".join(map(str, tokens)).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def observe(
        self,
        *,
        run_id: str,
        prompt_tokens: Sequence[int],
        generation_seed: int,
        sampling_parameters: dict[str, Any],
        candidate_ids: Sequence[str],
        uncertainty_state: str,
        abstention_reason: str,
        wall_seconds: float,
    ) -> None:
        trace = InferenceTrace(
            run_id=run_id,
            model_commit=self.model_commit,
            checkpoint_hash=self.checkpoint_hash,
            tokenizer_hash=self.tokenizer_hash,
            prompt_hash=self._hash_tokens(prompt_tokens),
            generation_seed=generation_seed,
            sampling_parameters=dict(sampling_parameters),
            candidate_ids=tuple(candidate_ids),
            counterfactual_model_version=self.counterfactual_model_version,
            credit_estimator_version=self.credit_estimator_version,
            uncertainty_state=uncertainty_state,
            abstention_reason=abstention_reason,
            runtime_telemetry={"observer_wall_seconds": float(wall_seconds), "recorded_at_monotonic": time.monotonic()},
        )
        self.sink(trace)


def run_shadow_observed_generate_batch(
    engine: Any,
    prompt_tokens: Sequence[int],
    *,
    observer: ShadowObserver | None,
    run_id: str,
    candidate_ids: Sequence[str] = (),
    uncertainty_state: str = "OBSERVATIONAL_ONLY",
    abstention_reason: str = "SHADOW_NO_CAUSAL_AUTHORITY",
    **generation_kwargs: Any,
):
    """Delegate to the base engine first; observer failure cannot alter base output."""
    started = time.perf_counter()
    result = engine.generate_batch(prompt_tokens, **generation_kwargs)
    elapsed = time.perf_counter() - started
    if observer is not None:
        try:
            observer.observe(
                run_id=run_id,
                prompt_tokens=prompt_tokens,
                generation_seed=int(generation_kwargs.get("seed", 42)),
                sampling_parameters={
                    k: generation_kwargs.get(k) for k in ("num_samples", "max_tokens", "temperature", "top_k")
                },
                candidate_ids=candidate_ids,
                uncertainty_state=uncertainty_state,
                abstention_reason=abstention_reason,
                wall_seconds=elapsed,
            )
        except Exception:
            # Fail-open with respect to base inference, fail-closed with respect to causal
            # authority: the sidecar is advisory-only and must never perturb generation.
            pass
    return result
