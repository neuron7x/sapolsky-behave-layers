from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from cwc.credit.envelope import CreditAuthorityDecision


@dataclass(frozen=True, slots=True)
class ReplayCandidate:
    candidate_id: str
    unresolved_priority: float


@dataclass(frozen=True, slots=True)
class ReplayDecision:
    candidate_id: str | None
    reason: str


def choose_replay_candidate(
    authority: CreditAuthorityDecision,
    candidates: Sequence[ReplayCandidate],
) -> ReplayDecision:
    """Only accepted credit may influence offline replay priority; never token logits."""
    if authority.state != "ACCEPT_CAUSAL_CREDIT" or authority.candidate is None:
        return ReplayDecision(None, f"NO_REPLAY_AUTHORITY:{authority.state}")
    matching = [c for c in candidates if c.candidate_id == authority.candidate]
    if not matching:
        return ReplayDecision(None, "ACCEPTED_CANDIDATE_NOT_IN_REPLAY_SET")
    return ReplayDecision(matching[0].candidate_id, "UNCERTAINTY_GATED_CAUSAL_CREDIT")
