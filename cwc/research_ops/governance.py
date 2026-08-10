from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json


@dataclass(frozen=True, slots=True)
class HumanDecision:
    decision_id: str
    gate: str
    subject_id: str
    reviewer: str
    reviewer_role: str
    decision: str
    rationale: str
    evidence_refs: tuple[str, ...]
    created_at: str
    architecture_authority: bool = False


def validate_human_decision(record: HumanDecision) -> None:
    required = {
        "decision_id": record.decision_id,
        "gate": record.gate,
        "subject_id": record.subject_id,
        "reviewer": record.reviewer,
        "reviewer_role": record.reviewer_role,
        "decision": record.decision,
        "rationale": record.rationale,
        "created_at": record.created_at,
    }
    missing = [key for key, value in required.items() if not value.strip()]
    if missing:
        raise ValueError("human decision missing: " + ", ".join(missing))
    if record.architecture_authority and record.gate != "H5_ARCHITECTURE_INTEGRATION":
        raise ValueError("architecture authority may only be granted at H5")
    if record.architecture_authority and record.decision != "INTEGRATE":
        raise ValueError("architecture authority requires INTEGRATE decision")
    if record.architecture_authority and not record.evidence_refs:
        raise ValueError("architecture authority requires explicit evidence references")


def write_human_decision(record: HumanDecision, directory: Path) -> Path:
    validate_human_decision(record)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{record.decision_id}.json"
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing != asdict(record):
            raise RuntimeError(f"immutable decision conflict: {path}")
        return path
    path.write_text(json.dumps(asdict(record), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
