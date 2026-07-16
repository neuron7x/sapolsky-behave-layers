import torch
from experiments.wp2_routing_v2.src.task_semantic_route import generate_batch
from experiments.wp2_routing_v2.src.typed_graph import TypedCognitiveGraph

def test_task_deterministic():
    a = generate_batch(16, torch.Generator().manual_seed(5), "train", 0.5)
    b = generate_batch(16, torch.Generator().manual_seed(5), "train", 0.5)
    assert torch.equal(a[0], b[0]) and torch.equal(a[2], b[2])

def test_graph_forward_deterministic():
    torch.manual_seed(0)
    g = TypedCognitiveGraph().eval()
    tok, st, canon, kind = generate_batch(16, torch.Generator().manual_seed(7))
    with torch.no_grad():
        o1, _, t1 = g(tok, capacity=8)
        o2, _, t2 = g(tok, capacity=8)
    assert torch.equal(o1, o2) and torch.equal(t1.semantic_mask, t2.semantic_mask)
