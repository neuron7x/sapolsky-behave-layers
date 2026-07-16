import torch
from experiments.wp2_routing_v2.src.typed_graph import TypedCognitiveGraph
from experiments.wp2_routing_v2.src.task_semantic_route import generate_batch
from experiments.wp2_routing_v2.src.compute import semantic_path_cost, direct_path_flops

def _g_and_batch(seed=0, B=64):
    torch.manual_seed(seed)
    g = TypedCognitiveGraph().eval()
    gen = torch.Generator().manual_seed(seed)
    tok, st, canon, kind = generate_batch(B, gen)
    return g, tok

def test_sparse_matches_dense():
    g, tok = _g_and_batch()
    K = 32
    mask = torch.zeros(64, dtype=torch.bool); mask[:K] = True
    with torch.no_grad():
        dense, _, _ = g(tok, capacity=K, forced_mask=mask)
        sparse, _, proc = g.forward_sparse(tok, capacity=K, forced_mask=mask)
    assert torch.allclose(dense, sparse, atol=1e-5)          # identical result
    assert proc["semantic"] == K and proc["direct"] == 64 - K

def test_processed_counts_track_capacity():
    g, tok = _g_and_batch()
    for K in (0, 16, 48, 64):
        mask = torch.zeros(64, dtype=torch.bool); mask[:K] = True
        with torch.no_grad():
            _, _, proc = g.forward_sparse(tok, capacity=K, forced_mask=mask)
        assert proc["semantic"] == K                          # only K semantic executions
        # measured FLOPs of the executed kernels scale with K
        flops = proc["semantic"] * semantic_path_cost() + proc["direct"] * direct_path_flops()
        assert flops == K * semantic_path_cost() + (64 - K) * direct_path_flops()

def test_empty_semantic_batch():
    g, tok = _g_and_batch()
    mask = torch.zeros(64, dtype=torch.bool)                  # all direct
    with torch.no_grad():
        out, _, proc = g.forward_sparse(tok, capacity=0, forced_mask=mask)
    assert proc["semantic"] == 0 and out is not None and torch.isfinite(out).all()

def test_empty_direct_batch():
    g, tok = _g_and_batch()
    mask = torch.ones(64, dtype=torch.bool)                   # all semantic
    with torch.no_grad():
        out, _, proc = g.forward_sparse(tok, capacity=64, forced_mask=mask)
    assert proc["direct"] == 0 and out is not None and torch.isfinite(out).all()

def test_gradient_only_to_executed_path():
    torch.manual_seed(0)
    g = TypedCognitiveGraph().train()
    gen = torch.Generator().manual_seed(0)
    tok, st, canon, kind = generate_batch(8, gen)
    mask = torch.ones(8, dtype=torch.bool)                    # all semantic -> direct gets NO grad
    out, _, _ = g.forward_sparse(tok, capacity=8, forced_mask=mask)
    out.sum().backward()
    direct_grad = any(p.grad is not None and p.grad.abs().sum() > 0 for p in g.direct.parameters())
    semantic_grad = any(p.grad is not None and p.grad.abs().sum() > 0 for p in g.semantic.parameters())
    assert semantic_grad and not direct_grad                  # only executed path gets gradient
