from __future__ import annotations

from cwc.research_ops.claim_attack import attack_claim
from cwc.research_ops.models import ClaimRecord, SourceSpan


def test_causal_claim_without_intervention_is_flagged() -> None:
    claim = ClaimRecord(
        claim_id="C1",
        source_id="S1",
        source_span=SourceSpan("S1", "paper.txt", 1, 1),
        claim_text="X causes Y",
        claim_type="EMPIRICAL",
        relation="CAUSES",
        comparison="control",
        metric="mse",
    )
    assert "causal_overreach" in attack_claim(claim)


def test_association_never_auto_promotes_to_causal() -> None:
    claim = ClaimRecord(
        claim_id="C2",
        source_id="S1",
        source_span=SourceSpan("S1", "paper.txt", 1, 1, span_quality="COARSE_SNAPSHOT_ONLY"),
        claim_text="X predicts Y",
        claim_type="EMPIRICAL",
        relation="PREDICTS",
        comparison="baseline",
        metric="accuracy",
    )
    flags = attack_claim(claim)
    assert "observational_only" in flags
    assert "coarse_source_span" in flags
    assert "causal_overreach" not in flags
