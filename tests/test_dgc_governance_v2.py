from __future__ import annotations

from dataclasses import replace

import pytest

from cwc.governance.budget import BudgetLedger
from cwc.governance.certificate import DGCExecutionCertificate, StopReason
from cwc.governance.compute_governor import ComputeGovernor
from cwc.governance.compute_value import estimate_voc
from cwc.governance.contracts import CandidateOperation, ComputeDirective, Perturbation
from cwc.governance.loop_guard import LoopGuard
from cwc.governance.perturbation_policy import (
    InterventionType,
    PerturbationTemplate,
    compile_local_perturbations,
)
from cwc.governance.scheduler import ProviderLimits, SchedulerState, acquire, release
from cwc.governance.sequential import (
    SamplingMode,
    SequentialDecision,
    SequentialSamplingContract,
    sequential_voc_decision,
    stitched_hoeffding_confidence_sequence,
)
from cwc.governance.telemetry import TelemetryLedger


def test_stitched_hoeffding_is_time_uniform_by_declared_spending_schedule() -> None:
    contract = SequentialSamplingContract(SamplingMode.IID_BOUNDED, lower=0.0, upper=1.0, delta=0.05)
    widths = []
    for n in (1, 10, 100, 1000):
        cs = stitched_hoeffding_confidence_sequence([0.7] * n, contract=contract)
        assert 0.0 <= cs.lower <= 0.7 <= cs.upper <= 1.0
        widths.append(cs.half_width)
    assert widths[-1] < widths[0]


def test_adaptive_sequential_policy_fails_closed() -> None:
    contract = SequentialSamplingContract(SamplingMode.ADAPTIVE, lower=0.0, upper=1.0, delta=0.05)
    with pytest.raises(ValueError, match="ADAPTIVE_POLICY_REQUIRES_SEPARATE_E_PROCESS"):
        stitched_hoeffding_confidence_sequence([0.5], contract=contract)


def test_sequential_voc_stop_and_continue_are_interval_decisions() -> None:
    c = SequentialSamplingContract(SamplingMode.IID_BOUNDED, lower=0.0, upper=1.0, delta=0.05)
    low = stitched_hoeffding_confidence_sequence([0.0] * 5000, contract=c)
    high = stitched_hoeffding_confidence_sequence([1.0] * 5000, contract=c)
    assert sequential_voc_decision(low, compute_cost=0.2) is SequentialDecision.STOP_VALUE_EXHAUSTED
    assert sequential_voc_decision(high, compute_cost=0.2) is SequentialDecision.CONTINUE_VALUE_POSITIVE


def test_perturbation_compiler_is_deterministic_and_budgeted() -> None:
    templates = [
        PerturbationTemplate(
            target_variable="latency",
            candidate_values=("10", "20", "30"),
            intervention_type=InterventionType.PARAMETER_SHIFT,
            provenance="fixture:latency-grid",
            plausibility_weight=1.0,
        )
    ]
    a = compile_local_perturbations({"latency": "10"}, templates, max_raw=1)
    b = compile_local_perturbations({"latency": "10"}, templates, max_raw=1)
    assert a == b
    assert a.raw_candidates == 3
    assert a.dropped_same_value == 1
    assert a.dropped_by_budget == 1
    assert len(a.perturbations) == 1


def test_causal_perturbation_requires_structural_authority() -> None:
    with pytest.raises(ValueError, match="structural_model_digest"):
        PerturbationTemplate(
            target_variable="x",
            candidate_values=("1",),
            intervention_type=InterventionType.CAUSAL_INTERVENTION,
            provenance="fixture",
            plausibility_weight=1.0,
        )
    p = Perturbation(
        perturbation_id="p",
        target_variable="x",
        baseline_value="0",
        perturbed_value="1",
        intervention_type="CAUSAL_INTERVENTION",
        provenance="fixture",
        plausibility_weight=1.0,
        causal_dependencies=("y",),
        structural_model_digest="scm-sha256",
    )
    assert p.structural_model_digest == "scm-sha256"


def test_governor_rejects_cost_meter_mismatch() -> None:
    budget = BudgetLedger(hard_tokens=100, hard_money=100, hard_time=100)
    op = CandidateOperation("probe", ComputeDirective.LOCAL_PROBE, estimated_cost=2.0)
    estimate = estimate_voc(
        operation_id="probe",
        gross_value=10.0,
        total_cost=1.0,
        gross_lower=9.0,
        gross_upper=11.0,
        method="fixture",
    )
    decision = ComputeGovernor.select(
        operations=[op], estimates={"probe": estimate}, budget=budget, decision_digest="d"
    )
    assert decision.directive is ComputeDirective.STOP


def test_scheduler_enforces_concurrency_and_rate_without_retry_bypass() -> None:
    limits = ProviderLimits(max_concurrency=1, bucket_capacity=2.0, refill_per_second=1.0)
    s0 = SchedulerState(in_flight=0, available_tokens=1.0, last_timestamp=0.0)
    first = acquire(s0, limits, now=0.0)
    assert first.granted
    blocked = acquire(first.state, limits, now=0.0)
    assert not blocked.granted and blocked.reason_code == "CONCURRENCY_LIMIT"
    released = release(first.state)
    rate_block = acquire(released, limits, now=0.0)
    assert not rate_block.granted and rate_block.reason_code == "RATE_LIMIT"
    refilled = acquire(released, limits, now=1.0)
    assert refilled.granted


def test_telemetry_hash_chain_detects_tamper() -> None:
    ledger = TelemetryLedger().append(
        operation_requested="probe",
        reason_code="ADMIT",
        predicted_voc=1.0,
        predicted_voc_lower=0.5,
        predicted_voc_upper=1.5,
        budget_before="b0",
        budget_after="b1",
        decision_digest="d",
        evidence_ids=("E2", "E1"),
    )
    assert ledger.verify()
    bad_event = replace(ledger.events[0], reason_code="TAMPER")
    assert not TelemetryLedger((bad_event,)).verify()


def test_execution_certificate_is_content_free_and_digest_bound() -> None:
    cert = DGCExecutionCertificate(
        decision_id="d1",
        selected_action="A",
        decision_gradient_digest="dg",
        compute_spent={"tokens": 10, "money": 0.1},
        stop_reason=StopReason.DECISION_STABLE,
        world_set_digest="world",
        utility_digest="utility",
        governor_digest="gov",
        budget_before_digest="b0",
        budget_after_digest="b1",
        evidence_ids=("E1",),
    )
    assert cert.verify()
    assert "chain" not in cert.to_json().lower()
    forged = replace(cert, selected_action="B")
    assert not forged.verify()


def test_loop_guard_has_hard_terminal_bound() -> None:
    guard = LoopGuard(max_steps=2)
    guard = guard.advance().advance()
    assert guard.exhausted
    with pytest.raises(RuntimeError, match="DGC_MAX_STEPS_EXHAUSTED"):
        guard.advance()
