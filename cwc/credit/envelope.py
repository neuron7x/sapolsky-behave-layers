from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

EpistemicState = Literal[
    "ACCEPT_CAUSAL_CREDIT",
    "ABSTAIN_UNCERTAIN_MODEL",
    "ABSTAIN_OOD",
    "ABSTAIN_INSUFFICIENT_INTERVENTION_SUPPORT",
    "ABSTAIN_UNRESOLVED_CREDIT",
    "FALSIFIED_NO_LEVERAGE",
    "OBSERVATIONAL_ONLY",
    "ABSTAIN_COMPUTE_BUDGET",
]


@dataclass(frozen=True, slots=True)
class CreditAuthorityDecision:
    state: EpistemicState
    candidate: str | None
    reason: str
    policy_version: str
    architecture_authority: bool = False
