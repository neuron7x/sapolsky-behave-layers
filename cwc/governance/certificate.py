from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping


class StopReason(str, Enum):
    DECISION_STABLE = "DECISION_STABLE"
    VALUE_OF_COMPUTE_EXHAUSTED = "VALUE_OF_COMPUTE_EXHAUSTED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    COUNTERMODEL_REVERSAL = "COUNTERMODEL_REVERSAL"
    HUMAN_ESCALATION_REQUIRED = "HUMAN_ESCALATION_REQUIRED"
    SYSTEM_ERROR = "SYSTEM_ERROR"


def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class DGCExecutionCertificate:
    decision_id: str
    selected_action: str
    decision_gradient_digest: str
    compute_spent: Mapping[str, float]
    stop_reason: StopReason
    world_set_digest: str
    utility_digest: str
    governor_digest: str
    budget_before_digest: str
    budget_after_digest: str
    evidence_ids: tuple[str, ...] = ()
    certificate_digest: str | None = None

    def __post_init__(self) -> None:
        required = {
            "decision_id": self.decision_id,
            "selected_action": self.selected_action,
            "decision_gradient_digest": self.decision_gradient_digest,
            "world_set_digest": self.world_set_digest,
            "utility_digest": self.utility_digest,
            "governor_digest": self.governor_digest,
            "budget_before_digest": self.budget_before_digest,
            "budget_after_digest": self.budget_after_digest,
        }
        if any(not str(value).strip() for value in required.values()):
            raise ValueError("certificate identifiers/digests must be non-empty")
        spent = {str(k): float(v) for k, v in self.compute_spent.items()}
        if any(v < 0 for v in spent.values()):
            raise ValueError("compute_spent values must be >= 0")
        evidence = tuple(sorted(set(str(x).strip() for x in self.evidence_ids if str(x).strip())))
        object.__setattr__(self, "compute_spent", MappingProxyType(spent))
        object.__setattr__(self, "evidence_ids", evidence)
        if self.certificate_digest is None:
            object.__setattr__(self, "certificate_digest", _digest(self.payload()))
        elif not str(self.certificate_digest).strip():
            raise ValueError("certificate_digest must be non-empty when supplied")

    def payload(self) -> dict[str, object]:
        return {
            "decision_id": self.decision_id,
            "selected_action": self.selected_action,
            "decision_gradient_digest": self.decision_gradient_digest,
            "compute_spent": dict(sorted(self.compute_spent.items())),
            "stop_reason": self.stop_reason.value,
            "world_set_digest": self.world_set_digest,
            "utility_digest": self.utility_digest,
            "governor_digest": self.governor_digest,
            "budget_before_digest": self.budget_before_digest,
            "budget_after_digest": self.budget_after_digest,
            "evidence_ids": list(self.evidence_ids),
        }

    def verify(self) -> bool:
        return _digest(self.payload()) == self.certificate_digest

    def to_json(self) -> str:
        payload = self.payload()
        payload["certificate_digest"] = self.certificate_digest
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
