"""python -m pytest tests/test_instrumentation_flops.py -v

Hand-calculated small-tensor checks for the analytical FLOP ledger (Act 4.8),
plus an adapter-agreement test against nanochat's own GPT.estimate_flops().
"""

import pytest

from cwc.instrumentation.flops import (
    FlopLedger,
    attention_core_flops,
    dense_linear_flops,
    full_causal_pairs,
    full_noncausal_pairs,
    mlp_flops,
    sliding_causal_pairs,
)


def test_dense_linear_flops_hand_calculated():
    # (4 tokens, 8 in, 16 out): 2 * 4 * 8 * 16 = 1024
    assert dense_linear_flops(tokens=4, d_in=8, d_out=16) == 1024


def test_full_noncausal_pairs():
    assert full_noncausal_pairs(4) == 16


def test_full_causal_pairs():
    # T=4: 1+2+3+4 = 10 = 4*5/2
    assert full_causal_pairs(4) == 10


def test_sliding_causal_pairs_matches_full_causal_when_window_covers_all():
    assert sliding_causal_pairs(5, window=5) == full_causal_pairs(5)


def test_sliding_causal_pairs_hand_calculated():
    # T=4, window=2: query0->1, query1->2, query2->2, query3->2 = 7
    assert sliding_causal_pairs(4, window=2) == 7


def test_sliding_causal_pairs_window_of_one_is_diagonal_only():
    assert sliding_causal_pairs(5, window=1) == 5


def test_attention_core_flops_hand_calculated():
    # B=2, d_model=8, pairs=10: 4*2*10*8 = 640
    assert attention_core_flops(batch=2, d_model=8, valid_attention_pairs=10) == 640


def test_mlp_flops_hand_calculated():
    # tokens=4, d=8, d_ff=32: 2*4*8*32 + 2*4*32*8 = 2048 + 2048 = 4096
    assert mlp_flops(tokens=4, d_model=8, d_ff=32) == 4096


def test_gqa_projection_dimensions_differ_from_mha():
    ledger = FlopLedger()
    record = ledger.add_attention(
        "layer0", batch=1, seq_len=8, d_model=64, n_head=8, n_kv_head=2, head_dim=8, causal=True
    )
    # d_q = 8*8=64, d_kv = 2*8=16: k/v projections must be cheaper than q/o
    assert record.metadata["k_proj"] < record.metadata["q_proj"]
    assert record.metadata["k_proj"] == record.metadata["v_proj"]


def test_window_attention_uses_sliding_pairs():
    ledger = FlopLedger()
    full = ledger.add_attention(
        "full", batch=1, seq_len=64, d_model=32, n_head=4, n_kv_head=4, head_dim=8, causal=True
    )
    windowed = ledger.add_attention(
        "windowed", batch=1, seq_len=64, d_model=32, n_head=4, n_kv_head=4, head_dim=8, causal=True, window=8
    )
    assert windowed.logical_flops < full.logical_flops


def test_ledger_totals_accumulate():
    ledger = FlopLedger()
    ledger.add_dense_linear("a", tokens=4, d_in=8, d_out=8)
    ledger.add_mlp("b", tokens=4, d_model=8, d_ff=32)
    assert ledger.total_logical_flops == ledger.entries[0].logical_flops + ledger.entries[1].logical_flops


def test_negative_flops_rejected():
    ledger = FlopLedger()
    with pytest.raises(ValueError):
        ledger.add("bad", "kind", -1)


def test_embedding_lookup_is_zero_flops_not_dense():
    ledger = FlopLedger()
    record = ledger.add_embedding_lookup("emb", tokens=16, d_model=64)
    assert record.logical_flops == 0


def test_flop_model_error_percent_none_when_no_entries():
    ledger = FlopLedger()
    assert ledger.flop_model_error_percent is None


def test_flop_model_error_percent_zero_when_matched():
    ledger = FlopLedger()
    ledger.add("x", "k", 100)
    assert ledger.flop_model_error_percent == 0.0


def test_expert_assignment_api_is_measurement_ready_but_computes_no_flops():
    ledger = FlopLedger()
    ledger.record_expert_assignments(
        expert_token_counts={0: 10, 1: 5},
        top_k=2,
        shared_expert_token_count=15,
        dropped_token_count=0,
        padded_token_count=0,
    )
    # recording routing shape must not silently add to the FLOP total
    assert ledger.total_logical_flops == 0
    assert ledger.to_dict()["expert_assignment_calls_recorded"] == 1


def test_expert_assignment_rejects_inconsistent_counts():
    ledger = FlopLedger()
    with pytest.raises(ValueError):
        ledger.record_expert_assignments(
            expert_token_counts={0: -1},
            top_k=2,
            shared_expert_token_count=0,
            dropped_token_count=0,
            padded_token_count=0,
        )
    with pytest.raises(ValueError):
        ledger.record_expert_assignments(
            expert_token_counts={0: 1},
            top_k=0,
            shared_expert_token_count=0,
            dropped_token_count=0,
            padded_token_count=0,
        )


def test_nanochat_estimator_agreement_on_dense_matmul_portion():
    """Act 5.4: read nanochat's own estimator, adapt rather than duplicate
    blindly, and document where conventions differ instead of forcing exact
    equality.

    nanochat's GPT.estimate_flops() returns forward+backward FLOPs per token
    as `6 * num_matmul_params() + attn_flops`, where attn_flops uses a PaLM-style
    per-layer approximation (12*h*q*effective_seq, no causal halving, and it
    does not separate Q/K/V/O the way this ledger does). The dense-matmul-only
    forward portion (`2 * num_matmul_params()` per token) is the part with an
    identical "1 MAC = 2 FLOPs, forward only" convention on both sides, so that
    is what this test compares — not the attention core, which is intentionally
    a different formula on each side (documented, not silently reconciled).
    """
    torch = pytest.importorskip("torch")
    from nanochat.gpt import GPT, GPTConfig

    cfg = GPTConfig(sequence_len=32, vocab_size=256, n_layer=2, n_head=2, n_kv_head=2, n_embd=32, window_pattern="L")
    model = GPT(cfg)
    nanochat_dense_forward_flops_per_token = 2 * model.num_matmul_params()

    head_dim = cfg.n_embd // cfg.n_head
    ledger = FlopLedger()
    for _ in range(cfg.n_layer):
        ledger.add_attention(
            "attn",
            batch=1,
            seq_len=1,  # per-token: isolate the projection cost, exclude the core
            d_model=cfg.n_embd,
            n_head=cfg.n_head,
            n_kv_head=cfg.n_kv_head,
            head_dim=head_dim,
            causal=True,
        )
        ledger.add_mlp("mlp", tokens=1, d_model=cfg.n_embd, d_ff=4 * cfg.n_embd)
    ledger.add_lm_head("lm_head", tokens=1, d_model=cfg.n_embd, vocab_size=model.transformer.wte.weight.shape[0])

    # subtract the (seq_len=1) attention-core term, which is not comparable —
    # it collapses to a fixed small constant per layer at seq_len=1, not zero,
    # so isolate the projection-only total instead.
    projection_only_total = sum(
        entry.metadata["q_proj"] + entry.metadata["k_proj"] + entry.metadata["v_proj"] + entry.metadata["o_proj"]
        for entry in ledger.entries
        if entry.kind == "attention"
    )
    mlp_total = sum(entry.logical_flops for entry in ledger.entries if entry.kind == "mlp")
    lm_head_total = sum(entry.logical_flops for entry in ledger.entries if entry.kind == "lm_head")
    ledger_dense_forward_flops_per_token = projection_only_total + mlp_total + lm_head_total

    # Not exact: nanochat's num_matmul_params() also includes small per-layer
    # extras (value-embedding gate, resid/x0 scalar lambdas) this ledger does
    # not model. Assert agreement within a documented tolerance, not equality.
    ratio = ledger_dense_forward_flops_per_token / nanochat_dense_forward_flops_per_token
    assert 0.85 <= ratio <= 1.15, (
        f"ledger={ledger_dense_forward_flops_per_token} vs "
        f"nanochat={nanochat_dense_forward_flops_per_token}, ratio={ratio}"
    )
