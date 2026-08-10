"""Causal-credit envelopes and estimators."""
from .envelope import CreditAuthorityDecision, EpistemicState
from .estimator import estimate_credit_envelope

__all__ = ["CreditAuthorityDecision", "EpistemicState", "estimate_credit_envelope"]

from .budgeted_shapley import (
    ShapleyEstimate,
    antithetic_crn_mc,
    crn_chain_mc,
    double_antithetic_crn_mc,
    exact_resampling_shapley,
    legacy_independent_mc,
)
from .context_authority import ContextAuthorityDecision, decide_context_direction
