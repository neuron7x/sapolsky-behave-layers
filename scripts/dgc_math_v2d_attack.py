from __future__ import annotations

from cwc.governance.change_detection import bounded_conditional_mean_change_eprocess
from cwc.governance.restricted_sampling import certify_restricted_adaptive_policy
from cwc.governance.sampling_trace import SamplingSelectionCommit, certify_restricted_sampling_trace
from cwc.governance.covariate_shift import target_mean_lcb_under_covariate_shift
from cwc.governance.transport_geometry import certify_weighted_l1_transport_geometry
from cwc.governance.metareasoning import MetaOperation, MetaTransition
from cwc.governance.metareasoning_branch_bound import certify_meta_action_with_transition_bounds


def must_kill(name, fn):
    try:
        fn()
    except (ValueError, RuntimeError):
        print(f"KILLED {name}")
        return True
    raise AssertionError(f"SURVIVED {name}")


def main():
    p=certify_restricted_adaptive_policy(target_distribution={"a":.5,"b":.5},minimum_propensity=.2)
    attacks=[
        ("OUTCOME_DEPENDENT_LAMBDA_NO_ATTESTATION", lambda: bounded_conditional_mean_change_eprocess([.9],lower=0,upper=1,baseline_mean=.5,tolerance=.05,alpha=.05,lambdas=[10.0],predictable_lambda_attested=False)),
        ("POST_OUTCOME_PROPENSITY_COMMIT", lambda: certify_restricted_sampling_trace(p,[SamplingSelectionCommit("a",.3,5,4,p.policy_digest)],telemetry_chain_verified=True)),
        ("HIDDEN_LOW_PROPENSITY", lambda: certify_restricted_sampling_trace(p,[SamplingSelectionCommit("a",.01,1,2,p.policy_digest)],telemetry_chain_verified=True)),
        ("UNBOUNDED_COVARIATE_WEIGHT", lambda: target_mean_lcb_under_covariate_shift([1.0],[9.0],lower=0,upper=1,delta=.05,max_density_ratio=2.0,ratio_induced_mean_error_budget=0,weight_authority_digest="w")),
        ("DEGENERATE_TRANSPORT_METRIC", lambda: certify_weighted_l1_transport_geometry(feature_weights={"x":0.0},coordinate_lipschitz={"x":1.0},feature_authority_digest="f")),
        ("FAKE_META_UPPER_BOUND", lambda: certify_meta_action_with_transition_bounds(stop_value=0.0,operations=[MetaOperation("c",0.0,(MetaTransition("s",1.0),))],next_state_stop_values={"s":1.0},next_state_value_upper={"s":.5},upper_bound_authority_digest="fake")),
    ]
    killed=sum(must_kill(n,f) for n,f in attacks)
    print(f"DGC-MATH-V2D-ATTACK: PASS ({killed}/{len(attacks)} killed)")

if __name__=="__main__": main()
