from __future__ import annotations
import pytest
from cwc.governance.change_detection import bounded_conditional_mean_change_eprocess
from cwc.governance.restricted_sampling import certify_restricted_adaptive_policy
from cwc.governance.sampling_trace import SamplingSelectionCommit, certify_restricted_sampling_trace
from cwc.governance.covariate_shift import target_mean_lcb_under_covariate_shift
from cwc.governance.transport_geometry import certify_weighted_l1_transport_geometry, weighted_l1_distance
from cwc.governance.metareasoning import MetaOperation, MetaTransition
from cwc.governance.metareasoning_branch_bound import certify_meta_action_with_transition_bounds
from cwc.governance.compute_value import ValueOfComputationEstimate
from cwc.governance.statistical_authority import StatisticalScope, certify_statistical_inference_authority
from cwc.governance.compute_governor import ComputeGovernor
from cwc.governance.contracts import CandidateOperation, ComputeDirective
from cwc.governance.budget import BudgetLedger


def test_change_eprocess_detects_upward_and_downward_departures():
    up=bounded_conditional_mean_change_eprocess([.9]*100,lower=0,upper=1,baseline_mean=.5,tolerance=.05,alpha=.05,lambdas=[1.0]*100,predictable_lambda_attested=True)
    down=bounded_conditional_mean_change_eprocess([.1]*100,lower=0,upper=1,baseline_mean=.5,tolerance=.05,alpha=.05,lambdas=[1.0]*100,predictable_lambda_attested=True)
    assert up.alarm_up and not up.alarm_down
    assert down.alarm_down and not down.alarm_up


def test_change_eprocess_no_alarm_is_not_stationarity_claim_but_no_false_trigger_here():
    r=bounded_conditional_mean_change_eprocess([.5]*50,lower=0,upper=1,baseline_mean=.5,tolerance=.05,alpha=.05,lambdas=[.5]*50,predictable_lambda_attested=True)
    assert not r.alarm


def test_change_eprocess_requires_predictability_attestation():
    with pytest.raises(ValueError):
        bounded_conditional_mean_change_eprocess([.5],lower=0,upper=1,baseline_mean=.5,tolerance=.05,alpha=.05,lambdas=[1.0],predictable_lambda_attested=False)


def test_sampling_trace_requires_pre_outcome_propensity_commit():
    p=certify_restricted_adaptive_policy(target_distribution={"a":.6,"b":.4},minimum_propensity=.2)
    good=[SamplingSelectionCommit("a",.4,1,2,p.policy_digest),SamplingSelectionCommit("b",.3,3,4,p.policy_digest)]
    c=certify_restricted_sampling_trace(p,good,telemetry_chain_verified=True)
    assert c.pre_outcome_ordering_verified
    with pytest.raises(ValueError):
        certify_restricted_sampling_trace(p,[SamplingSelectionCommit("a",.4,2,2,p.policy_digest)],telemetry_chain_verified=True)


def test_sampling_trace_rejects_propensity_below_floor_and_unverified_chain():
    p=certify_restricted_adaptive_policy(target_distribution={"a":.5,"b":.5},minimum_propensity=.2)
    with pytest.raises(ValueError):
        certify_restricted_sampling_trace(p,[SamplingSelectionCommit("a",.1,1,2,p.policy_digest)],telemetry_chain_verified=True)
    with pytest.raises(ValueError):
        certify_restricted_sampling_trace(p,[SamplingSelectionCommit("a",.3,1,2,p.policy_digest)],telemetry_chain_verified=False)


def test_covariate_shift_lcb_penalizes_weight_uncertainty():
    a=target_mean_lcb_under_covariate_shift([1.0]*200,[1.0]*200,lower=0,upper=1,delta=.05,max_density_ratio=1.0,ratio_induced_mean_error_budget=0.0,weight_authority_digest="w")
    b=target_mean_lcb_under_covariate_shift([1.0]*200,[1.0]*200,lower=0,upper=1,delta=.05,max_density_ratio=1.0,ratio_induced_mean_error_budget=.1,weight_authority_digest="w")
    assert a.target_mean_lower > b.target_mean_lower
    assert a.target_mean_lower > .8


def test_covariate_shift_rejects_unbounded_weight():
    with pytest.raises(ValueError):
        target_mean_lcb_under_covariate_shift([.5],[2.0],lower=0,upper=1,delta=.05,max_density_ratio=1.0,ratio_induced_mean_error_budget=0.0,weight_authority_digest="w")


def test_weighted_l1_geometry_derives_sound_global_lipschitz():
    g=certify_weighted_l1_transport_geometry(feature_weights={"x":2.0,"y":1.0},coordinate_lipschitz={"x":4.0,"y":1.0},feature_authority_digest="feat")
    assert g.global_lipschitz_upper == pytest.approx(2.0)
    assert weighted_l1_distance([0,0],[1,3],g)==pytest.approx(5.0)


def test_weighted_l1_geometry_rejects_zero_metric_weight():
    with pytest.raises(ValueError):
        certify_weighted_l1_transport_geometry(feature_weights={"x":0.0},coordinate_lipschitz={"x":1.0},feature_authority_digest="feat")


def test_transition_local_meta_bound_certifies_global_stop():
    op=MetaOperation("probe",.2,(MetaTransition("a",.5),MetaTransition("b",.5)))
    cert=certify_meta_action_with_transition_bounds(stop_value=1.0,operations=[op],next_state_stop_values={"a":.9,"b":1.0},next_state_value_upper={"a":1.1,"b":1.1},upper_bound_authority_digest="pi")
    assert cert.certified_optimal_action=="STOP"
    assert cert.suboptimality_upper_bound==pytest.approx(0.0)


def test_transition_local_meta_bound_can_certify_operation_and_tight_gap():
    op=MetaOperation("probe",.1,(MetaTransition("a",.5),MetaTransition("b",.5)))
    cert=certify_meta_action_with_transition_bounds(stop_value=.5,operations=[op],next_state_stop_values={"a":.9,"b":.9},next_state_value_upper={"a":.95,"b":.95},upper_bound_authority_digest="pi")
    assert cert.certified_optimal_action=="probe"
    assert cert.suboptimality_upper_bound==pytest.approx(.05)


def test_transition_local_meta_bound_rejects_invalid_upper_authority():
    op=MetaOperation("probe",.1,(MetaTransition("a",1.0),))
    with pytest.raises(ValueError):
        certify_meta_action_with_transition_bounds(stop_value=.5,operations=[op],next_state_stop_values={"a":.9},next_state_value_upper={"a":.8},upper_bound_authority_digest="pi")


def _estimate():
    return ValueOfComputationEstimate("op",1.0,.2,.8,.4,1.0,"TEST")


def test_strict_governor_requires_bound_statistical_certificate():
    est=_estimate(); op=CandidateOperation("op",ComputeDirective.RETRIEVE,.2)
    budget=BudgetLedger(10,10,10)
    no=ComputeGovernor.select(operations=[op],estimates={"op":est},budget=budget,decision_digest="d",production_strict_math=True)
    assert no.directive is ComputeDirective.STOP
    cert=certify_statistical_inference_authority(estimate=est,scope=StatisticalScope.IID_FIXED,sampling_policy_digest="p",sampling_trace_digest="t",calibration_digest="c",drift_guard_digest="g",invalidated_by_drift=False)
    yes=ComputeGovernor.select(operations=[op],estimates={"op":est},budget=budget,decision_digest="d",production_strict_math=True,statistical_certificates={"op":cert})
    assert yes.operation_id=="op"


def test_strict_governor_rejects_drift_invalidated_certificate_and_estimate_swap():
    est=_estimate(); op=CandidateOperation("op",ComputeDirective.RETRIEVE,.2); budget=BudgetLedger(10,10,10)
    bad=certify_statistical_inference_authority(estimate=est,scope=StatisticalScope.IID_FIXED,sampling_policy_digest="p",sampling_trace_digest="t",calibration_digest="c",drift_guard_digest="g",invalidated_by_drift=True)
    out=ComputeGovernor.select(operations=[op],estimates={"op":est},budget=budget,decision_digest="d",production_strict_math=True,statistical_certificates={"op":bad})
    assert out.directive is ComputeDirective.STOP
    cert=certify_statistical_inference_authority(estimate=est,scope=StatisticalScope.IID_FIXED,sampling_policy_digest="p",sampling_trace_digest="t",calibration_digest="c",drift_guard_digest="g",invalidated_by_drift=False)
    swapped=ValueOfComputationEstimate("op",2.0,.2,1.8,1.0,2.0,"TEST")
    out2=ComputeGovernor.select(operations=[op],estimates={"op":swapped},budget=budget,decision_digest="d",production_strict_math=True,statistical_certificates={"op":cert})
    assert out2.directive is ComputeDirective.STOP
