from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StructuralAdequacyEnvelope:
    best_model_family: str
    max_cell_idr: float
    covered_cells: int
    min_cell_support: int
    max_empirical_leverage: float
    context_shift_candidates: tuple[str, ...]
    factual_rmse: float | None = None


@dataclass(frozen=True, slots=True)
class StructuralAuthorityPolicy:
    version: str
    max_cell_idr: float
    required_cells: int
    min_cell_support: int
    leverage_floor: float


@dataclass(frozen=True, slots=True)
class StructuralAuthorityDecision:
    state: str
    model_family: str | None
    reason: str
    policy_version: str


def decide_structural_authority(
    envelope: StructuralAdequacyEnvelope,
    policy: StructuralAuthorityPolicy,
) -> StructuralAuthorityDecision:
    if envelope.covered_cells < policy.required_cells or envelope.min_cell_support < policy.min_cell_support:
        return StructuralAuthorityDecision(
            "ABSTAIN_INSUFFICIENT_STRUCTURAL_COVERAGE", None,
            "INTERVENTION_COVERAGE_BELOW_FROZEN_MINIMUM", policy.version,
        )
    if envelope.max_empirical_leverage < policy.leverage_floor:
        return StructuralAuthorityDecision(
            "FALSIFIED_NO_CAUSAL_LEVERAGE", None,
            "INTERVENTIONS_SHOW_NO_MEASURABLE_LEVERAGE", policy.version,
        )
    if envelope.max_cell_idr > policy.max_cell_idr:
        return StructuralAuthorityDecision(
            "ABSTAIN_STRUCTURAL_MISSPECIFICATION", None,
            "INTERVENTIONAL_DIVERGENCE_EXCEEDS_FROZEN_CALIBRATION", policy.version,
        )
    if envelope.context_shift_candidates:
        return StructuralAuthorityDecision(
            "CONTEXT_CONDITIONAL_ONLY", envelope.best_model_family,
            "INTERVENTIONAL_EFFECT_CHANGES_ACROSS_CONTEXT", policy.version,
        )
    return StructuralAuthorityDecision(
        "STRUCTURAL_ADEQUACY_ACCEPTED_SYNTHETIC", envelope.best_model_family,
        "CALIBRATED_INTERVENTIONAL_ADEQUACY_PASSED", policy.version,
    )
