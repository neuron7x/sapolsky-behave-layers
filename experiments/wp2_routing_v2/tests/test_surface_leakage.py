import torch
from experiments.wp2_routing_v2.src.leakage_probe import audit, _logistic_auroc
from experiments.wp2_routing_v2.src.surface_matched_task import generate_batch, VOCAB

def test_original_benchmark_leaks():
    r = audit(n=1500, seed=0)
    assert r["length"] > 0.9 and r["histogram"] > 0.9   # confirmed surface leakage

def test_matched_task_well_formed():
    g = torch.Generator().manual_seed(1)
    tok, tgt, far = generate_batch(300, g)
    for b in range(300):
        assert (tok[b] == tgt[b]).sum().item() == 2      # exactly one duplicated value

def test_matched_task_surface_clean():
    g = torch.Generator().manual_seed(2)
    tok, tgt, far = generate_batch(2000, g)
    length = (tok >= 0).sum(1).float()
    hist = torch.stack([(tok == v).sum(1).float() for v in range(VOCAB)], dim=1)
    assert _logistic_auroc(length, far.long()) < 0.6     # length cannot classify
    assert _logistic_auroc(hist, far.long()) < 0.65      # histogram near chance
