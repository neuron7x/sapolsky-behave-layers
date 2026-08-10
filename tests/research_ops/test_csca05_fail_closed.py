from dataclasses import replace

from cwc.credit.ablation_shapley import AblationShapleyEstimate
from cwc.inference.composed_authority import ShadowCreditPolicy, decide_shadow_credit
from cwc.inference.intervention_trace import InterventionCreditTrace


def test_zero_credit_game_cannot_receive_authority():
    estimate = AblationShapleyEstimate(
        credits={"A": 0.0, "B": 0.0, "C": 0.0, "D": 0.0},
        estimator_variance={"A": 0.0, "B": 0.0, "C": 0.0, "D": 0.0},
        logical_evaluations=12,
        unique_forward_evaluations=8,
        sampling_units=2,
        method="ANTITHETIC_PERMUTATION_ABLATION_SHAPLEY",
    )
    decision = decide_shadow_credit(estimate, ShadowCreditPolicy("p", 3.29, 1e-3, 16), context="PROSE")
    assert decision.state == "ABSTAIN_UNRESOLVED_CREDIT"


def test_trace_hash_binds_active_control_and_model_state():
    trace = InterventionCreditTrace(
        trace_id="t", cohort="PRIMARY", context="PROSE", checkpoint_hash="c",
        model_state_hash_before="m", model_state_hash_after="m", prompt_hash="p",
        base_output_hash="o", factual_top_token=1, candidate_spans={"A": (1, 2)},
        intervention_token=32, estimator_method="x", estimator_budget=2,
        approximate_credits={"A": 1.0}, approximate_variance={"A": 0.1}, exact_credits={"A": 1.0},
        decision_state="ACCEPT_SHADOW_CREDIT_CONTEXT_BOUND", decision_candidate="A", decision_sign=1,
        authority_scope="CONTEXT_ONLY", abstention_reason="NONE", logical_evaluations=3,
        unique_forward_evaluations=2, runtime_telemetry={}, active_control=False,
    )
    assert trace.sha256() != replace(trace, active_control=True).sha256()
    assert trace.sha256() != replace(trace, model_state_hash_after="mutated").sha256()
