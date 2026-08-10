from cwc.inference.abstention import AbstentionPolicy, decide_causal_authority
from experiments.csca_02_ua.common import evaluate_raw_case, generate_case, raw_case_to_envelope_proxy

POLICY = AbstentionPolicy("test", 0.0, 0.85, 1.0, 0.5, 10.0, 32, 0.1)


def test_zero_cause_never_receives_causal_authority():
    raw = evaluate_raw_case(generate_case(61000, "N0_ZERO_CAUSE"))
    decision = decide_causal_authority(raw_case_to_envelope_proxy(raw), POLICY)
    assert decision.state == "FALSIFIED_NO_LEVERAGE"
    assert decision.candidate is None
    assert decision.architecture_authority is False
