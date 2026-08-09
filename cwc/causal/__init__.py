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
]
