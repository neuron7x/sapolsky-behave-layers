"""Decision-relevant compute governance primitives for the DGC research programme.

This package is intentionally content-agnostic.  It may inspect epistemic state and
mint compute-admission decisions, but it must not generate task content or mutate
``cwc.epistemics`` authority.
"""

from cwc.governance.budget import BudgetLedger
from cwc.governance.compute_governor import ComputeGovernor
from cwc.governance.compute_value import ValueOfComputationEstimate, estimate_voc
from cwc.governance.contracts import (
    CandidateOperation,
    ComputeDecision,
    ComputeDirective,
    DecisionGradientCertificate,
    Perturbation,
    RiskClass,
)
from cwc.governance.decision_gradient import estimate_decision_gradient

__all__ = [
    "BudgetLedger",
    "CandidateOperation",
    "ComputeDecision",
    "ComputeDirective",
    "ComputeGovernor",
    "DecisionGradientCertificate",
    "Perturbation",
    "RiskClass",
    "ValueOfComputationEstimate",
    "estimate_decision_gradient",
    "estimate_voc",
]
