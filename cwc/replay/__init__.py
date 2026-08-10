"""Replay scheduling primitives for experimental CWC modules."""

from .scheduler import ReplayChoice, choose_candidate, choose_least_covered_context

__all__ = ["ReplayChoice", "choose_candidate", "choose_least_covered_context"]

from .causal_governor import ReplayCandidate, ReplayDecision, choose_replay_candidate

# Passive factual-trace identifiability boundary (CSCA-07)
from .passive_identifiability import (
    AR1Law,
    AR1MixtureEProcess,
    PassiveInformationCertificate,
    ar1_relative_entropy_rate,
    passive_information_certificate,
    spectral_topology_counterexample,
    hidden_autocatalytic_fixed_point,
    fiber_ambiguity_counterexample,
    replay_authority_state,
)
