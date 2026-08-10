from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from typing import Any


@dataclass(frozen=True, slots=True)
class InferenceTrace:
    run_id: str
    model_commit: str
    checkpoint_hash: str
    tokenizer_hash: str
    prompt_hash: str
    generation_seed: int
    sampling_parameters: dict[str, Any]
    candidate_ids: tuple[str, ...]
    counterfactual_model_version: str
    credit_estimator_version: str
    uncertainty_state: str
    abstention_reason: str
    runtime_telemetry: dict[str, Any]

    def canonical_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()
