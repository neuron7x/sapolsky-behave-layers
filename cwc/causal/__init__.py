"""Causal identification layer for CWC Vertical Inference Ascension (VIA)."""

from .cate import (
    collapse_context,
    destroy_interaction,
    doubly_robust_policy_value,
    ips_policy_value,
    oracle_gap,
    treatment_effects_against,
)
from .crossfit import fold_assignment, grouped_kfold
from .interventions import balanced_randomized_assignments, permute_each_replicate_context_rows
from .opportunity import (
    OpportunityPoint,
    OpportunitySummary,
    QualityComputeOutcome,
    capture_fraction,
    critical_lambdas,
    opportunity_at_lambda,
    representative_lambdas,
    summarize_opportunity,
    validate_quality_compute_replay,
)
from .potential_outcomes import (
    PotentialOutcome,
    TrialObservation,
    context_action_matrix,
    validate_exhaustive_replay,
)

__all__ = [
    "PotentialOutcome",
    "TrialObservation",
    "balanced_randomized_assignments",
    "collapse_context",
    "context_action_matrix",
    "destroy_interaction",
    "doubly_robust_policy_value",
    "fold_assignment",
    "grouped_kfold",
    "ips_policy_value",
    "oracle_gap",
    "permute_each_replicate_context_rows",
    "treatment_effects_against",
    "validate_exhaustive_replay",
    "OpportunityPoint",
    "OpportunitySummary",
    "QualityComputeOutcome",
    "capture_fraction",
    "critical_lambdas",
    "opportunity_at_lambda",
    "representative_lambdas",
    "summarize_opportunity",
    "validate_quality_compute_replay",
]
