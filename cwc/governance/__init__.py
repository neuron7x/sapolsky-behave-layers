"""Decision-relevant compute governance primitives for the DGC research programme.

This package is intentionally content-agnostic. It may inspect epistemic state and
mint compute-admission decisions, but it must not generate task content or mutate
``cwc.epistemics`` authority.
"""

from cwc.governance.budget import BudgetLedger
from cwc.governance.certificate import DGCExecutionCertificate, StopReason
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
from cwc.governance.loop_guard import LoopGuard
from cwc.governance.perturbation_policy import (
    InterventionType,
    PerturbationBatch,
    PerturbationTemplate,
    compile_local_perturbations,
)
from cwc.governance.scheduler import ProviderLimits, SchedulerDecision, SchedulerState, acquire, release
from cwc.governance.sequential import (
    BoundedMeanConfidenceSequence,
    SamplingMode,
    SequentialDecision,
    SequentialSamplingContract,
    sequential_voc_decision,
    stitched_hoeffding_confidence_sequence,
)
from cwc.governance.telemetry import GovernanceEvent, TelemetryLedger

__all__ = [
    "BoundedMeanConfidenceSequence",
    "BudgetLedger",
    "CandidateOperation",
    "ComputeDecision",
    "ComputeDirective",
    "ComputeGovernor",
    "DGCExecutionCertificate",
    "DecisionGradientCertificate",
    "GovernanceEvent",
    "InterventionType",
    "LoopGuard",
    "Perturbation",
    "PerturbationBatch",
    "PerturbationTemplate",
    "ProviderLimits",
    "RiskClass",
    "SamplingMode",
    "SchedulerDecision",
    "SchedulerState",
    "SequentialDecision",
    "SequentialSamplingContract",
    "StopReason",
    "TelemetryLedger",
    "ValueOfComputationEstimate",
    "acquire",
    "compile_local_perturbations",
    "estimate_decision_gradient",
    "estimate_voc",
    "release",
    "sequential_voc_decision",
    "stitched_hoeffding_confidence_sequence",
]

# DGC mathematical hardening v2
from cwc.governance.adaptive_eprocess import AdaptiveImportanceSample, AdaptiveMeanEProcess, adaptive_importance_mean_eprocess
from cwc.governance.calibration import SplitConformalLowerCalibrator, fit_split_conformal_lower
from cwc.governance.decision_stability import DecisionStabilityCertificate, RemovableComputeCertificate, certify_action_stability, certify_decision_irrelevant_suffix
from cwc.governance.pareto import MeanBound, ParetoCertificate, certify_paired_pareto_improvement, fixed_n_hoeffding_mean_bound
from cwc.governance.robust_voc import RobustnessBudget, RobustVOCLowerBound, robust_voc_lower_bound
from cwc.governance.compute_value import VOCAuthority
from cwc.governance.robust_voc import robustify_voc_estimate
from cwc.governance.ambiguity import CredalExpectationInterval, MinimaxRegretDecision, PerfectInformationStopCertificate, credal_expectation_interval, minimax_regret_action, certify_no_information_worth_cost
from cwc.governance.robust_voc import WassersteinRobustnessBudget, wasserstein_robust_voc_lower_bound
from cwc.governance.risk_control import ConformalRiskControlResult, conformal_risk_control
from cwc.governance.metareasoning import MetaOperation, MetaTransition, MetaValue, finite_horizon_meta_values, myopic_meta_values
