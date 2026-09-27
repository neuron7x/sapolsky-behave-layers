from __future__ import annotations

from cwc.governance.bounded_meta_planner import certify_bounded_horizon_meta_plan
from cwc.governance.calibration_lifecycle import activate_initial_calibration, begin_shadow_recalibration, invalidate_calibration_on_drift, promote_shadow_recalibration
from cwc.governance.metareasoning import MetaOperation, MetaTransition
from cwc.governance.covariate_shift import target_mean_lcb_under_covariate_shift


def must_kill(name, fn):
    try: fn()
    except (ValueError,RuntimeError): print(f"KILLED {name}"); return 1
    raise AssertionError(f"SURVIVED {name}")


def main():
    d={"s":0.0,"t":1.0}; ops={"s":(MetaOperation("c",0.0,(MetaTransition("t",1.0),)),)}
    active=activate_initial_calibration(calibration_digest="cal0",risk_control_digest="risk0",source_trace_digest="tr0",drift_guard_digest="g0",preregistration_digest="pre0",risk_control_passed=True,independent_holdout_passed=True)
    invalid=invalidate_calibration_on_drift(active,drift_alarm_digest="alarm",alarm_detected=True)
    shadow=begin_shadow_recalibration(invalid,new_source_trace_digest="tr1",preregistration_digest="pre1")
    attacks=[
        ("FAKE_INITIAL_CALIBRATION_PASS",lambda:activate_initial_calibration(calibration_digest="c",risk_control_digest="r",source_trace_digest="t",drift_guard_digest="g",preregistration_digest="p",risk_control_passed=False,independent_holdout_passed=True)),
        ("FALSE_META_UPPER",lambda:certify_bounded_horizon_meta_plan(root_state="s",decision_values=d,operations=ops,state_value_upper={"s":0.0,"t":0.5},horizon=1,expansion_depth=0,upper_bound_authority_digest="fake",pure_information_certified=True)),
        ("NO_PURE_INFO_AUTHORITY",lambda:certify_bounded_horizon_meta_plan(root_state="s",decision_values=d,operations=ops,state_value_upper={"s":1.0,"t":1.0},horizon=1,expansion_depth=0,upper_bound_authority_digest="u",pure_information_certified=False)),
        ("REUSE_INVALIDATED_TRACE",lambda:begin_shadow_recalibration(invalid,new_source_trace_digest="tr0",preregistration_digest="pre2")),
        ("PROMOTE_WITHOUT_HOLDOUT",lambda:promote_shadow_recalibration(shadow,new_calibration_digest="cal1",new_risk_control_digest="risk1",new_drift_guard_digest="g1",risk_control_passed=True,independent_holdout_passed=False,source_trace_disjoint_attested=True)),
        ("IMPOSSIBLE_DENSITY_RATIO_CAP",lambda:target_mean_lcb_under_covariate_shift([0.5],[0.5],lower=0,upper=1,delta=.05,max_density_ratio=.9,ratio_induced_mean_error_budget=0.0,weight_authority_digest="w")),
    ]
    killed=sum(must_kill(n,f) for n,f in attacks)
    print(f"DGC-MATH-V2E-ATTACK: PASS ({killed}/{len(attacks)} killed)")

if __name__=="__main__": main()
