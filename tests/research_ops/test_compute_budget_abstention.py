from cwc.inference.abstention import AbstentionPolicy, decide_causal_authority
from experiments.csca_02_ua.common import evaluate_raw_case, generate_case, raw_case_to_envelope_proxy


def test_compute_budget_is_fail_closed():
    raw = evaluate_raw_case(generate_case(31000, "M0_CORRECT_STRUCTURE"))
    policy = AbstentionPolicy("test", 0.0, 2.0, 2.0, 0.0, 10.0, 1, 0.1)
    decision = decide_causal_authority(
        raw_case_to_envelope_proxy(raw), policy, structural_evaluations=100, max_structural_evaluations=10
    )
    assert decision.state == "ABSTAIN_COMPUTE_BUDGET"
