from dataclasses import replace

from cwc.inference.trace import InferenceTrace


def make_trace():
    return InferenceTrace(
        run_id="r1",
        model_commit="abc",
        checkpoint_hash="checkpoint",
        tokenizer_hash="tokenizer",
        prompt_hash="prompt",
        generation_seed=7,
        sampling_parameters={"temperature": 0.0, "top_k": 1},
        candidate_ids=("A", "C"),
        counterfactual_model_version="cf-v1",
        credit_estimator_version="credit-v1",
        uncertainty_state="ABSTAIN_UNCERTAIN_MODEL",
        abstention_reason="TEST",
        runtime_telemetry={"wall_seconds": 0.1},
    )


def test_trace_hash_is_deterministic_and_binds_authority_fields():
    trace = make_trace()
    assert trace.sha256() == make_trace().sha256()
    assert trace.sha256() != replace(trace, uncertainty_state="ACCEPT_CAUSAL_CREDIT").sha256()
    assert trace.sha256() != replace(trace, checkpoint_hash="other").sha256()
    assert trace.sha256() != replace(trace, generation_seed=8).sha256()
