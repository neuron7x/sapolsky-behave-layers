from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Sequence

from cwc.governance.restricted_sampling import RestrictedAdaptiveSamplingPolicy


@dataclass(frozen=True, slots=True)
class SamplingSelectionCommit:
    item_id: str
    selection_probability: float
    selection_event_index: int
    outcome_event_index: int
    policy_digest: str


@dataclass(frozen=True, slots=True)
class SamplingTraceCertificate:
    n: int
    policy_digest: str
    trace_digest: str
    max_observed_importance_weight: float
    telemetry_chain_verified: bool
    pre_outcome_ordering_verified: bool
    method: str = "HASH_BOUND_RESTRICTED_ADAPTIVE_SAMPLING_TRACE_V1"


def certify_restricted_sampling_trace(
    policy: RestrictedAdaptiveSamplingPolicy,
    commits: Sequence[SamplingSelectionCommit], *, telemetry_chain_verified: bool,
) -> SamplingTraceCertificate:
    if not telemetry_chain_verified:
        raise ValueError("verified append-only telemetry chain required")
    if not commits:
        raise ValueError("non-empty sampling commits required")
    q = dict(policy.target_distribution)
    payload = []
    max_w = 0.0
    last_selection_index = -1
    for c in commits:
        if c.policy_digest != policy.policy_digest:
            raise ValueError("sampling commit policy digest mismatch")
        if c.item_id not in q or q[c.item_id] <= 0.0:
            raise ValueError("sampled item outside positive target support")
        p = float(c.selection_probability)
        if not math.isfinite(p) or p < policy.minimum_propensity - 1e-15 or p > 1.0:
            raise ValueError("selection propensity violates certified policy")
        if c.selection_event_index <= last_selection_index:
            raise ValueError("selection event indexes must strictly increase")
        if c.selection_event_index >= c.outcome_event_index:
            raise ValueError("selection propensity must be committed before outcome")
        w = q[c.item_id] / p
        if w > policy.max_importance_weight + 1e-12:
            raise ValueError("observed importance weight exceeds certified cap")
        max_w = max(max_w, w)
        last_selection_index = c.selection_event_index
        payload.append((c.item_id, p, c.selection_event_index, c.outcome_event_index, c.policy_digest))
    digest = hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode("utf-8")).hexdigest()
    return SamplingTraceCertificate(len(commits), policy.policy_digest, digest, max_w, True, True)
