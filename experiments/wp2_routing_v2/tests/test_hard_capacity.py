import torch
from experiments.wp2_routing_v2.src.controller import topk_mask
from experiments.wp2_routing_v2.src.typed_graph import TypedCognitiveGraph
from experiments.wp2_routing_v2.src.task_semantic_route import generate_batch

def test_topk_exact():
    need = torch.rand(64)
    m = topk_mask(need, 32)
    assert m.sum().item() == 32

def test_graph_respects_capacity():
    torch.manual_seed(0)
    g = TypedCognitiveGraph().eval()
    gg = torch.Generator().manual_seed(0)
    tok, st, canon, kind = generate_batch(64, gg)
    with torch.no_grad():
        out, state, trace = g(tok, capacity=32)
    assert trace.semantic_mask.sum().item() == 32
    assert trace.active_cost.sum().item() == 32  # 1 per semantic sample
