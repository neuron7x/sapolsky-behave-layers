from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ComputeStage = Literal["C0", "C1", "C2", "C3"]


@dataclass(frozen=True, slots=True)
class ComputeRequest:
    compute_request_id: str
    hypothesis_id: str
    experiment_id: str
    stage: ComputeStage
    scientific_question: str
    kill_condition: str
    why_small_scale_is_insufficient: str
    expected_information_gain: float
    estimated_cost_units: float
    baseline_completed: bool = False
    nulls_completed: bool = False
    c0_pass: bool = False
    c1_pass: bool = False
    mechanism_survived_nulls: bool = False
    signal_replicated_across_seeds: bool = False
    ood_test_justifies_scale: bool = False
    scaling_question_is_explicit: bool = False
    stop_condition: str = ""
    owner: str = ""
    approved_by: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ComputeDecision:
    approved: bool
    stage: ComputeStage
    reason: str
    priority_score: float


class ComputeGovernor:
    """Fail-closed implementation of C0→C1→C2→C3 escalation."""

    @staticmethod
    def evaluate(request: ComputeRequest) -> ComputeDecision:
        if not request.kill_condition.strip():
            return ComputeDecision(False, request.stage, "REJECT_NO_KILL_CONDITION", 0.0)
        if request.estimated_cost_units < 0 or request.expected_information_gain < 0:
            return ComputeDecision(False, request.stage, "REJECT_INVALID_COST_OR_INFORMATION_GAIN", 0.0)
        score = request.expected_information_gain / max(request.estimated_cost_units, 1e-12)

        if request.stage == "C0":
            return ComputeDecision(True, "C0", "APPROVE_ANALYTIC_KILL", score)
        if request.stage == "C1":
            if not request.c0_pass:
                return ComputeDecision(False, "C1", "REJECT_C0_NOT_PASSED", score)
            return ComputeDecision(True, "C1", "APPROVE_CHEAP_PILOT", score)
        if request.stage == "C2":
            if not request.c0_pass or not request.c1_pass:
                return ComputeDecision(False, "C2", "REJECT_C0_C1_NOT_PASSED", score)
            if not request.baseline_completed:
                return ComputeDecision(False, "C2", "REJECT_BASELINE_INCOMPLETE", score)
            return ComputeDecision(True, "C2", "APPROVE_SINGLE_DEVICE_REPRODUCTION", score)
        if request.stage == "C3":
            predicates = {
                "mechanism_survived_nulls": request.mechanism_survived_nulls,
                "signal_replicated_across_seeds": request.signal_replicated_across_seeds,
                "ood_test_justifies_scale": request.ood_test_justifies_scale,
                "scaling_question_is_explicit": request.scaling_question_is_explicit,
            }
            failed = [name for name, ok in predicates.items() if not ok]
            if failed:
                return ComputeDecision(False, "C3", "REJECT_SCALE_PRECONDITIONS:" + ",".join(failed), score)
            return ComputeDecision(True, "C3", "APPROVE_FRONTIER_SCALE", score)
        raise ValueError(f"unknown compute stage: {request.stage}")
