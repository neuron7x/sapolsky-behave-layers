from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Sequence


def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class GovernanceEvent:
    index: int
    operation_requested: str
    reason_code: str
    predicted_voc: float | None
    predicted_voc_lower: float | None
    predicted_voc_upper: float | None
    budget_before: str
    budget_after: str
    decision_digest: str
    evidence_ids: tuple[str, ...]
    previous_event_digest: str
    event_digest: str


@dataclass(frozen=True, slots=True)
class TelemetryLedger:
    events: tuple[GovernanceEvent, ...] = ()

    def append(
        self,
        *,
        operation_requested: str,
        reason_code: str,
        predicted_voc: float | None,
        predicted_voc_lower: float | None,
        predicted_voc_upper: float | None,
        budget_before: str,
        budget_after: str,
        decision_digest: str,
        evidence_ids: Sequence[str] = (),
    ) -> "TelemetryLedger":
        previous = self.events[-1].event_digest if self.events else "GENESIS"
        payload = {
            "index": len(self.events),
            "operation_requested": operation_requested,
            "reason_code": reason_code,
            "predicted_voc": predicted_voc,
            "predicted_voc_lower": predicted_voc_lower,
            "predicted_voc_upper": predicted_voc_upper,
            "budget_before": budget_before,
            "budget_after": budget_after,
            "decision_digest": decision_digest,
            "evidence_ids": sorted(set(str(x) for x in evidence_ids)),
            "previous_event_digest": previous,
        }
        event = GovernanceEvent(
            index=int(payload["index"]),
            operation_requested=str(payload["operation_requested"]),
            reason_code=str(payload["reason_code"]),
            predicted_voc=payload["predicted_voc"],
            predicted_voc_lower=payload["predicted_voc_lower"],
            predicted_voc_upper=payload["predicted_voc_upper"],
            budget_before=str(payload["budget_before"]),
            budget_after=str(payload["budget_after"]),
            decision_digest=str(payload["decision_digest"]),
            evidence_ids=tuple(payload["evidence_ids"]),
            previous_event_digest=str(payload["previous_event_digest"]),
            event_digest=_digest(payload),
        )
        return TelemetryLedger(self.events + (event,))

    def verify(self) -> bool:
        previous = "GENESIS"
        for index, event in enumerate(self.events):
            payload = {
                "index": index,
                "operation_requested": event.operation_requested,
                "reason_code": event.reason_code,
                "predicted_voc": event.predicted_voc,
                "predicted_voc_lower": event.predicted_voc_lower,
                "predicted_voc_upper": event.predicted_voc_upper,
                "budget_before": event.budget_before,
                "budget_after": event.budget_after,
                "decision_digest": event.decision_digest,
                "evidence_ids": list(event.evidence_ids),
                "previous_event_digest": previous,
            }
            if event.index != index or event.previous_event_digest != previous or _digest(payload) != event.event_digest:
                return False
            previous = event.event_digest
        return True
