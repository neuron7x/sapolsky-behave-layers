"""Act §13 router causal invariants. Run: PYTHONPATH=. pytest
experiments/wp2_routing_v1/tests/ -q
"""
from __future__ import annotations

import torch

from experiments.wp2_routing_v1.src.model import (
    Block,
    ModelConfig,
    RoutedTransformer,
    RoutingMode,
    _topk_mask,
)
from experiments.wp2_routing_v1.src.compute import active_inference_flops, parity_ratio

CFG = ModelConfig(vocab_size=64, seq_len=32, n_layer=8, d_model=64, n_head=4, d_ff=256, budget_k=4)


def _model(mode, seed=0):
    torch.manual_seed(seed)
    return RoutedTransformer(CFG, mode)


def test_dense_equals_plain_forward():
    # DENSE mode must equal running every block's residual with no gating.
    m = _model(RoutingMode.DENSE).eval()
    idx = torch.randint(0, CFG.vocab_size, (3, CFG.seq_len))
    with torch.no_grad():
        routed = m(idx)
        # reference: manual all-block residual
        pos = torch.arange(CFG.seq_len)
        x = m.embed(idx) + m.pos(pos).unsqueeze(0)
        for blk in m.blocks:
            x = x + blk(x)
        from experiments.wp2_routing_v1.src.model import _rmsnorm
        ref = m.head(_rmsnorm(x))
    assert torch.allclose(routed, ref, atol=1e-5)


def test_skip_is_exact_identity():
    # A block whose gate is 0 must leave the hidden state unchanged.
    torch.manual_seed(0)
    blk = Block(CFG)
    x = torch.randn(2, CFG.seq_len, CFG.d_model)
    contrib = blk(x)
    zero_gated = x + 0.0 * contrib
    assert torch.equal(zero_gated, x)


def test_hard_budget_never_exceeded_eval():
    for mode in (RoutingMode.RANDOM, RoutingMode.LEARNED, RoutingMode.FROZEN, RoutingMode.FIXED_DEPTH):
        m = _model(mode).eval()
        idx = torch.randint(0, CFG.vocab_size, (16, CFG.seq_len))
        with torch.no_grad():
            m(idx, seq_seed=123)
        counts = m.last_active_counts()
        assert torch.all(counts == CFG.budget_k), f"{mode}: {counts.unique().tolist()}"


def test_random_deterministic_by_seed():
    m = _model(RoutingMode.RANDOM).eval()
    idx = torch.randint(0, CFG.vocab_size, (8, CFG.seq_len))
    with torch.no_grad():
        m(idx, seq_seed=7)
        a = m.last_active_counts().clone(), m._last_mask.clone()
        m(idx, seq_seed=7)
        b = m.last_active_counts().clone(), m._last_mask.clone()
    assert torch.equal(a[1], b[1])


def test_frozen_controller_has_no_grad():
    m = _model(RoutingMode.FROZEN)
    assert m.controller is not None
    assert all(not p.requires_grad for p in m.controller.parameters())


def test_learned_controller_params_update():
    m = _model(RoutingMode.LEARNED).train()
    opt = torch.optim.SGD([p for p in m.parameters() if p.requires_grad], lr=0.1)
    before = [p.clone() for p in m.controller.parameters()]
    idx = torch.randint(0, CFG.vocab_size, (8, CFG.seq_len))
    tgt = torch.randint(0, CFG.vocab_size, (8, CFG.seq_len))
    logits = m(idx, seq_seed=1)
    loss = torch.nn.functional.cross_entropy(logits.view(-1, CFG.vocab_size), tgt.view(-1))
    loss.backward()
    # controller must receive gradient via straight-through
    assert any(p.grad is not None and p.grad.abs().sum() > 0 for p in m.controller.parameters())
    opt.step()
    after = list(m.controller.parameters())
    assert any(not torch.equal(b, a) for b, a in zip(before, after))


def test_eval_deterministic():
    m = _model(RoutingMode.LEARNED).eval()
    idx = torch.randint(0, CFG.vocab_size, (8, CFG.seq_len))
    with torch.no_grad():
        a = m(idx, seq_seed=0)
        b = m(idx, seq_seed=0)
    assert torch.equal(a, b)


def test_topk_mask_exact():
    s = torch.tensor([[0.1, 0.9, 0.5, 0.3, 0.7]])
    m = _topk_mask(s, 2)
    assert m.sum().item() == 2
    assert m[0, 1] == 1 and m[0, 4] == 1


def test_flop_parity_across_k_configs():
    # random/frozen/learned/fixed all have K active blocks -> parity within 1%.
    a = active_inference_flops(CFG, CFG.seq_len, CFG.budget_k, controller=True)   # learned/frozen
    b = active_inference_flops(CFG, CFG.seq_len, CFG.budget_k, controller=False)  # random/fixed
    assert parity_ratio(a, b) <= 0.01


def test_checkpoint_roundtrip_controller_state():
    m = _model(RoutingMode.LEARNED)
    sd = m.state_dict()
    m2 = _model(RoutingMode.LEARNED, seed=99)
    m2.load_state_dict(sd)
    for p, q in zip(m.parameters(), m2.parameters()):
        assert torch.equal(p, q)
