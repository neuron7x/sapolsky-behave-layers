from __future__ import annotations

import random
import pytest

from cwc.governance.bounded_meta_planner import certify_bounded_horizon_meta_plan
from cwc.governance.calibration_lifecycle import CalibrationState, activate_initial_calibration, begin_shadow_recalibration, certify_estimate_from_active_calibration, invalidate_calibration_on_drift, promote_shadow_recalibration
from cwc.governance.compute_value import ValueOfComputationEstimate
from cwc.governance.metareasoning import MetaOperation, MetaTransition, finite_horizon_meta_values
from cwc.governance.statistical_authority import StatisticalScope, certify_statistical_inference_authority, sign_statistical_inference_certificate, verify_signed_statistical_inference_certificate
from cwc.governance.covariate_shift import target_mean_lcb_under_covariate_shift


def _model():
    d={"s":0.0,"t":0.0,"g":2.0}; ops={"s":(MetaOperation("c1",0.6,(MetaTransition("t",1.0),)),),"t":(MetaOperation("c2",0.6,(MetaTransition("g",1.0),)),)}
    return d,ops


def test_bounded_planner_exposes_complementarity_and_full_expansion_is_exact():
    d,ops=_model(); upper={s:2.0 for s in d}
    shallow=certify_bounded_horizon_meta_plan(root_state="s",decision_values=d,operations=ops,state_value_upper=upper,horizon=2,expansion_depth=1,upper_bound_authority_digest="pi",pure_information_certified=True)
    exact=certify_bounded_horizon_meta_plan(root_state="s",decision_values=d,operations=ops,state_value_upper=upper,horizon=2,expansion_depth=2,upper_bound_authority_digest="pi",pure_information_certified=True)
    assert shallow.lower_value==pytest.approx(0.0) and shallow.upper_value==pytest.approx(1.4)
    assert exact.lower_value==pytest.approx(0.8) and exact.upper_value==pytest.approx(0.8) and exact.certified_optimal_action=="c1"


def test_bounded_planner_contains_exact_bellman_and_gap_refines_on_random_models():
    rng=random.Random(20260822); states=("s0","s1","s2","s3")
    for _ in range(100):
        d={s:rng.random()*2 for s in states}; ops={}
        for s in states:
            rows=[]
            for j in range(2):
                a,b=rng.choice(states),rng.choice(states); p=rng.random()
                rows.append(MetaOperation(f"{s}-c{j}",rng.random()*.4,(MetaTransition(a,p),MetaTransition(b,1-p))))
            ops[s]=tuple(rows)
        exact=finite_horizon_meta_values(decision_values=d,operations=ops,horizon=3)["s0"].value
        upper={s:max(d.values()) for s in states}; gap=float("inf")
        for depth in range(4):
            c=certify_bounded_horizon_meta_plan(root_state="s0",decision_values=d,operations=ops,state_value_upper=upper,horizon=3,expansion_depth=depth,upper_bound_authority_digest="pi",pure_information_certified=True)
            assert c.lower_value<=exact+1e-10<=c.upper_value+1e-10 and c.residual_optimality_gap<=gap+1e-10; gap=c.residual_optimality_gap
        assert c.lower_value==pytest.approx(exact)==c.upper_value


def _active():
    return activate_initial_calibration(calibration_digest="cal0",risk_control_digest="risk0",source_trace_digest="trace0",drift_guard_digest="guard0",preregistration_digest="pre0",risk_control_passed=True,independent_holdout_passed=True)


def test_initial_calibration_requires_preregistered_risk_control_and_holdout():
    with pytest.raises(ValueError): activate_initial_calibration(calibration_digest="c",risk_control_digest="r",source_trace_digest="t",drift_guard_digest="g",preregistration_digest="p",risk_control_passed=False,independent_holdout_passed=True)


def test_drift_invalidation_requires_new_shadow_generation_before_reuse():
    invalid=invalidate_calibration_on_drift(_active(),drift_alarm_digest="alarm",alarm_detected=True)
    assert invalid.state is CalibrationState.INVALIDATED_DRIFT
    with pytest.raises(ValueError): begin_shadow_recalibration(invalid,new_source_trace_digest="trace0",preregistration_digest="pre1")
    shadow=begin_shadow_recalibration(invalid,new_source_trace_digest="trace1",preregistration_digest="pre1")
    with pytest.raises(ValueError): promote_shadow_recalibration(shadow,new_calibration_digest="cal0",new_risk_control_digest="risk1",new_drift_guard_digest="guard1",risk_control_passed=True,independent_holdout_passed=True,source_trace_disjoint_attested=True)
    active1=promote_shadow_recalibration(shadow,new_calibration_digest="cal1",new_risk_control_digest="risk1",new_drift_guard_digest="guard1",risk_control_passed=True,independent_holdout_passed=True,source_trace_disjoint_attested=True)
    assert active1.state is CalibrationState.ACTIVE and active1.generation==1


def test_invalidated_calibration_cannot_mint_authority():
    invalid=invalidate_calibration_on_drift(_active(),drift_alarm_digest="alarm",alarm_detected=True)
    est=ValueOfComputationEstimate("op",1,.2,.8,.4,1,"fixture")
    with pytest.raises(ValueError): certify_estimate_from_active_calibration(estimate=est,authority=invalid,scope=StatisticalScope.IID_FIXED,sampling_policy_digest="p",sampling_trace_digest="t")


def test_signed_statistical_authority_binds_issuer_key_and_estimate():
    est=ValueOfComputationEstimate("op",1,.2,.8,.4,1,"fixture")
    cert=certify_statistical_inference_authority(estimate=est,scope=StatisticalScope.IID_FIXED,sampling_policy_digest="p",sampling_trace_digest="t",calibration_digest="c",drift_guard_digest="g",invalidated_by_drift=False)
    signed=sign_statistical_inference_certificate(cert,issuer_id="issuer",secret_key=b"a"*32)
    assert verify_signed_statistical_inference_certificate(signed,trusted_issuer_id="issuer",secret_key=b"a"*32,estimate=est)
    assert not verify_signed_statistical_inference_certificate(signed,trusted_issuer_id="other",secret_key=b"a"*32,estimate=est)
    assert not verify_signed_statistical_inference_certificate(signed,trusted_issuer_id="issuer",secret_key=b"b"*32,estimate=est)


def test_density_ratio_global_cap_below_one_is_impossible():
    with pytest.raises(ValueError): target_mean_lcb_under_covariate_shift([0.5],[0.5],lower=0,upper=1,delta=.05,max_density_ratio=.9,ratio_induced_mean_error_budget=0.0,weight_authority_digest="w")
