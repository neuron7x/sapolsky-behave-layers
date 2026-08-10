from __future__ import annotations

from .models import ClaimRecord

CAUSAL_RELATIONS = {"CAUSES", "CAUSAL_MECHANISM", "CHANGES_UNDER_DO"}
ASSOCIATION_RELATIONS = {"CORRELATES_WITH", "PREDICTS"}


def attack_claim(claim: ClaimRecord) -> tuple[str, ...]:
    """Generate machine flags only. This function never returns a causal verdict."""
    claim.validate()
    flags: list[str] = []
    relation = claim.relation.upper()
    if relation in CAUSAL_RELATIONS and not claim.intervention.strip():
        flags.append("causal_overreach")
    if not claim.comparison.strip():
        flags.append("missing_control")
    if not claim.metric.strip():
        flags.append("metric_unspecified")
    if relation in ASSOCIATION_RELATIONS:
        flags.append("observational_only")
    if claim.source_span.span_quality != "EXACT":
        flags.append("coarse_source_span")
    return tuple(sorted(set(flags)))
