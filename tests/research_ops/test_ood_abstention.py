from dataclasses import replace

from cwc.inference.abstention import AbstentionPolicy, decide_causal_authority
from experiments.csca_02_ua.common import evaluate_raw_case, generate_case, raw_case_to_envelope_proxy

POLICY = AbstentionPolicy("test", 0.0, 10.0, 10.0, 0.0, 1.0, 1, 0.0)


def test_ood_surface_forces_abstention_before_credit_authority():
    raw = evaluate_raw_case(generate_case(31000, "M0_CORRECT_STRUCTURE"))
    envelope = raw_case_to_envelope_proxy(raw)
    envelope = replace(envelope, ood_score=POLICY.max_ood_score + 1.0)
    decision = decide_causal_authority(envelope, POLICY)
    assert decision.state == "ABSTAIN_OOD"
    assert decision.candidate is None
