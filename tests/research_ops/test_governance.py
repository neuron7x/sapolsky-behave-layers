from __future__ import annotations

import pytest

from cwc.research_ops.governance import HumanDecision, validate_human_decision


def test_architecture_authority_is_h5_only() -> None:
    rec = HumanDecision(
        decision_id="D",
        gate="H4_EXPERIMENT_DESIGN",
        subject_id="E",
        reviewer="human",
        reviewer_role="reviewer",
        decision="INTEGRATE",
        rationale="r",
        evidence_refs=("x",),
        created_at="2026-08-10",
        architecture_authority=True,
    )
    with pytest.raises(ValueError):
        validate_human_decision(rec)


def test_pending_h5_has_no_architecture_authority() -> None:
    rec = HumanDecision(
        decision_id="D",
        gate="H5_ARCHITECTURE_INTEGRATION",
        subject_id="E",
        reviewer="UNASSIGNED_HUMAN_REVIEWER",
        reviewer_role="ADVERSARIAL_REVIEWER",
        decision="PENDING_HUMAN_REVIEW",
        rationale="r",
        evidence_refs=("x",),
        created_at="2026-08-10",
        architecture_authority=False,
    )
    validate_human_decision(rec)
