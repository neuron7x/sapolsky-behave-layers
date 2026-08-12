from __future__ import annotations

from dataclasses import dataclass

from cwc.counterfactual.model import CANDIDATES
from cwc.counterfactual.uncertainty import CounterfactualPredictionEnvelope
from cwc.credit.envelope import CreditAuthorityDecision


@dataclass(frozen=True, slots=True)
class AbstentionPolicy:
    version: str
    delta: float
    max_intervention_nrmse: float
    max_model_disagreement: float
    min_rank_stability: float
    max_ood_score: float
    min_intervention_support: int
    leverage_floor: float = 0.10


def decide_causal_authority(
    envelope: CounterfactualPredictionEnvelope,
    policy: AbstentionPolicy,
    *,
    structural_evaluations: int = 0,
    max_structural_evaluations: int | None = None,
) -> CreditAuthorityDecision:
    if max_structural_evaluations is not None and structural_evaluations > max_structural_evaluations:
        return CreditAuthorityDecision(
            "ABSTAIN_COMPUTE_BUDGET", None, "STRUCTURAL_EVALUATION_BUDGET_EXCEEDED", policy.version
        )
    counts = envelope.intervention_support
    if not counts or max(counts.values(), default=0) == 0:
        return CreditAuthorityDecision("OBSERVATIONAL_ONLY", None, "NO_INTERVENTION_SUPPORT", policy.version)
    if min(counts.values()) < policy.min_intervention_support:
        return CreditAuthorityDecision(
            "ABSTAIN_INSUFFICIENT_INTERVENTION_SUPPORT",
            None,
            "INTERVENTION_SUPPORT_BELOW_FROZEN_MINIMUM",
            policy.version,
        )
    if max(envelope.observed_effect_magnitudes.values(), default=0.0) < policy.leverage_floor:
        return CreditAuthorityDecision(
            "FALSIFIED_NO_LEVERAGE", None, "SUPPORTED_INTERVENTIONS_SHOW_NO_LEVERAGE", policy.version
        )
    if envelope.ood_score > policy.max_ood_score:
        return CreditAuthorityDecision("ABSTAIN_OOD", None, "CONTEXT_SUPPORT_OUTSIDE_FROZEN_BOUNDARY", policy.version)
    if envelope.intervention_nrmse > policy.max_intervention_nrmse:
        return CreditAuthorityDecision("ABSTAIN_UNCERTAIN_MODEL", None, "INTERVENTION_ADEQUACY_FAILED", policy.version)
    if envelope.model_disagreement > policy.max_model_disagreement:
        return CreditAuthorityDecision("ABSTAIN_UNCERTAIN_MODEL", None, "MODEL_FAMILY_DISAGREEMENT", policy.version)
    if envelope.rank_stability < policy.min_rank_stability:
        return CreditAuthorityDecision("ABSTAIN_UNCERTAIN_MODEL", None, "CREDIT_RANK_UNSTABLE", policy.version)

    top = envelope.provisional_candidate
    top_interval = envelope.credit(top)
    best_other_upper = max(envelope.credit(name).upper for name in CANDIDATES if name != top)
    if not (top_interval.lower > best_other_upper + policy.delta):
        return CreditAuthorityDecision("ABSTAIN_UNRESOLVED_CREDIT", None, "CREDIT_INTERVALS_OVERLAP", policy.version)
    return CreditAuthorityDecision("ACCEPT_CAUSAL_CREDIT", top, "ALL_FROZEN_AUTHORITY_GATES_PASSED", policy.version)
