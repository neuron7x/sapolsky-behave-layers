from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class InterventionCreditTrace:
    trace_id: str
    cohort: str
    context: str
    checkpoint_hash: str
    model_state_hash_before: str
    model_state_hash_after: str
    prompt_hash: str
    base_output_hash: str
    factual_top_token: int
    candidate_spans: dict[str, tuple[int, int]]
    intervention_token: int
    estimator_method: str
    estimator_budget: int
    approximate_credits: dict[str, float]
    approximate_variance: dict[str, float]
    exact_credits: dict[str, float] | None
    decision_state: str
    decision_candidate: str | None
    decision_sign: int | None
    authority_scope: str
    abstention_reason: str
    logical_evaluations: int
    unique_forward_evaluations: int
    runtime_telemetry: dict[str, Any]
    active_control: bool = False

    def canonical_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()
