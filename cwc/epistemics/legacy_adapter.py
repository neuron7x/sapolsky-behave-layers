from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from cwc.causal.regime_identifiability import RegimeIVDecision
from cwc.epistemics.countermodel_search import CountermodelSearchDecision
from cwc.epistemics.lattice import (
    EpistemicMachine,
    EpistemicRecord,
    EpistemicState,
    EvidenceRef,
)


@dataclass(frozen=True, slots=True)
class LegacyAdaptation:
    record: EpistemicRecord
    source_state: str
    mapping_rule: str


def adapt_regime_iv_decision(
    machine: EpistemicMachine,
    decision: RegimeIVDecision,
    *,
    claim_id: str,
    factual_evidence: Sequence[EvidenceRef],
    predictive_evidence: Sequence[EvidenceRef],
    assumption_evidence: Sequence[EvidenceRef],
    terminal_evidence: Sequence[EvidenceRef],
    context_scope: Sequence[str],
) -> LegacyAdaptation:
    """Map frozen CSCA-08 string states into the live typed runtime layer.

    This adapter does not mutate historical artifacts. Assumption violations and
    insufficient-information outcomes map to UNIDENTIFIED, not FALSIFIED causal
    truth and never INTERVENTION_SUPPORTED.
    """
    observed = machine.observe(
        claim_id=claim_id,
        context_scope=context_scope,
        evidence=factual_evidence,
        reason="legacy factual trace imported",
    )
    pred_cap = machine.issue_predictive_capability(observed, evidence=predictive_evidence)
    predictive = machine.transition(observed, pred_cap)

    if decision.state == "CAUSAL_CANDIDATE_UNDER_ASSUMPTIONS":
        assumption_ids = tuple(a.assumption_id for a in decision.assumptions)
        cap = machine.issue_assumption_capability(
            predictive,
            assumption_ids=assumption_ids,
            evidence=assumption_evidence,
            reason="legacy assumption-conditional candidate imported",
        )
        return LegacyAdaptation(
            record=machine.transition(predictive, cap),
            source_state=decision.state,
            mapping_rule="candidate survives only as ASSUMPTION_CONDITIONAL",
        )

    if decision.state in {"IDENTIFYING_ASSUMPTION_VIOLATED", "INSUFFICIENT_INFORMATION_BUDGET"}:
        cap = machine.issue_terminal_capability(
            predictive,
            target_state=EpistemicState.UNIDENTIFIED,
            evidence=terminal_evidence,
            reason=f"legacy state {decision.state} blocks causal identification",
        )
        return LegacyAdaptation(
            record=machine.transition(predictive, cap),
            source_state=decision.state,
            mapping_rule="assumption/information failure -> UNIDENTIFIED",
        )

    cap = machine.issue_terminal_capability(
        predictive,
        target_state=EpistemicState.ABSTAIN,
        evidence=terminal_evidence,
        reason=f"unknown legacy state {decision.state}; fail closed",
    )
    return LegacyAdaptation(
        record=machine.transition(predictive, cap),
        source_state=decision.state,
        mapping_rule="unknown legacy state -> ABSTAIN",
    )


def adapt_countermodel_decision(
    machine: EpistemicMachine,
    upstream: EpistemicRecord,
    decision: CountermodelSearchDecision,
    *,
    countermodel_evidence: Sequence[EvidenceRef],
) -> LegacyAdaptation:
    """Apply COG-COUNTERMODEL-01R output without permitting silent promotion."""
    if upstream.state is not EpistemicState.ASSUMPTION_CONDITIONAL:
        return LegacyAdaptation(
            record=upstream,
            source_state=decision.state,
            mapping_rule="upstream not assumption-conditional; countermodel search cannot promote",
        )

    if decision.state == "OBSERVATIONALLY_EQUIVALENT_COUNTERMODEL_SURVIVES":
        cap = machine.issue_terminal_capability(
            upstream,
            target_state=EpistemicState.UNIDENTIFIED,
            evidence=countermodel_evidence,
            reason="causally distinct factual-law countermodel survives",
        )
        return LegacyAdaptation(
            record=machine.transition(upstream, cap),
            source_state=decision.state,
            mapping_rule="surviving exact countermodel -> UNIDENTIFIED",
        )

    if decision.state in {
        "ASSUMPTION_CONDITIONAL_IDENTIFICATION_COUNTERMODELS_OUTSIDE_BOUNDS",
        "NO_EXACT_COUNTERMODEL_FOUND_IN_FROZEN_SEARCH_CLASS",
    }:
        return LegacyAdaptation(
            record=upstream,
            source_state=decision.state,
            mapping_rule="no promotion: retain ASSUMPTION_CONDITIONAL",
        )

    cap = machine.issue_terminal_capability(
        upstream,
        target_state=EpistemicState.ABSTAIN,
        evidence=countermodel_evidence,
        reason=f"countermodel decision {decision.state} is not promotion-bearing",
    )
    return LegacyAdaptation(
        record=machine.transition(upstream, cap),
        source_state=decision.state,
        mapping_rule="unrecognized/ineligible countermodel outcome -> ABSTAIN",
    )
