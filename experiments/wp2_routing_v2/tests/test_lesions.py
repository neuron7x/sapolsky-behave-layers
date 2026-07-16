import torch
from experiments.wp2_routing_v2.src.typed_graph import TypedCognitiveGraph, LESIONS
from experiments.wp2_routing_v2.src.task_semantic_route import generate_batch

def test_all_lesions_run():
    torch.manual_seed(0)
    g = TypedCognitiveGraph().eval()
    gg = torch.Generator().manual_seed(0)
    tok, st, canon, kind = generate_batch(16, gg)
    allm = torch.ones(16, dtype=torch.bool)
    for les in LESIONS:
        with torch.no_grad():
            out, state, trace = g(tok, capacity=16, forced_mask=allm, lesion=les)
        assert torch.isfinite(out).all()

def test_subject_object_swap_changes_state():
    torch.manual_seed(0)
    g = TypedCognitiveGraph().eval()
    gg = torch.Generator().manual_seed(3)
    tok, st, canon, kind = generate_batch(16, gg)
    allm = torch.ones(16, dtype=torch.bool)
    with torch.no_grad():
        _, s_intact, _ = g(tok, capacity=16, forced_mask=allm, lesion="none")
        _, s_swap, _ = g(tok, capacity=16, forced_mask=allm, lesion="subject_object_swapped")
    assert torch.equal(s_swap.subject, s_intact.object)
