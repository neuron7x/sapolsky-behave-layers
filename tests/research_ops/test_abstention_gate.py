from cwc.inference.abstention import AbstentionPolicy, decide_causal_authority
from experiments.csca_02_ua.common import evaluate_raw_case, generate_case, raw_case_to_envelope_proxy

POLICY = AbstentionPolicy("test", 0.0, 0.5, 1.0, 0.5, 10.0, 32, 0.1)


def test_zero_cause_is_rejection_not_accept():
    raw = evaluate_raw_case(generate_case(31000, "N0_ZERO_CAUSE"))
    decision = decide_causal_authority(raw_case_to_envelope_proxy(raw), POLICY)
    assert decision.state == "FALSIFIED_NO_LEVERAGE"
    assert decision.candidate is None


def test_bad_structural_model_abstains():
    raw = evaluate_raw_case(generate_case(31000, "M4_SIGN_ERROR"))
    decision = decide_causal_authority(raw_case_to_envelope_proxy(raw), POLICY)
    assert decision.state == "ABSTAIN_UNCERTAIN_MODEL"
