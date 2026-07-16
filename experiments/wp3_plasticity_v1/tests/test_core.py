import copy
import torch
import torch.nn.functional as F
from cwc.plasticity.registry import ParameterGroupRegistry
from cwc.plasticity.optimizer import PlasticityOptimizer
from cwc.plasticity.contracts import AdaptationMode, PlasticityDecision
from experiments.wp3_plasticity_v1.src.model import GroupedModel, VOCAB
from experiments.wp3_plasticity_v1.src.benchmark import base_batch

def _reg(m): return ParameterGroupRegistry.from_model(m)

def test_registry_full_coverage_no_dup():
    torch.manual_seed(0); m = GroupedModel()
    reg = _reg(m)
    covered, total = reg.coverage(m)
    assert covered == total  # 100% coverage
    # no param in two groups
    seen = set()
    for s in reg.specs:
        for n in s.parameter_names:
            assert n not in seen; seen.add(n)

def test_registry_deterministic_ids():
    torch.manual_seed(0); a = _reg(GroupedModel())
    torch.manual_seed(123); b = _reg(GroupedModel())  # different weights, same structure
    assert a.checksum() == b.checksum()  # ids independent of object identity/values

def _decision(reg, mask_val):
    G = reg.n_groups()
    return PlasticityDecision(group_mask=torch.full((G,), mask_val, dtype=torch.bool),
        lr_multiplier=torch.ones(G), consolidation=torch.zeros(G),
        max_update_norm=torch.zeros(G), replay_fraction=0.0,
        mode=AdaptationMode.UPDATE_EXISTING, selected_cost=G if mask_val else 0, budget=G)

def test_gate_f_zero_mask_byte_identical():
    torch.manual_seed(0); m = GroupedModel()
    before = {n: p.detach().clone() for n, p in m.named_parameters()}
    named = dict(m.named_parameters())
    popt = PlasticityOptimizer(torch.optim.AdamW(m.parameters(), lr=1e-2), _reg(m), named)
    ref = {n: p.detach().clone() for n, p in named.items()}
    g = torch.Generator().manual_seed(0); x, y = base_batch(32, g)
    popt.zero_grad(); F.cross_entropy(m(x).reshape(-1, VOCAB), y.reshape(-1)).backward()
    popt.apply_and_step(_decision(_reg(m), False), ref)  # zero mask
    for n, p in m.named_parameters():
        assert torch.equal(p, before[n]), f"{n} changed under zero mask"

def test_gate_f_full_mask_equivalent_to_adamw():
    torch.manual_seed(0); m1 = GroupedModel()
    m2 = copy.deepcopy(m1)
    g = torch.Generator().manual_seed(0); x, y = base_batch(32, g)
    # plain AdamW
    o1 = torch.optim.AdamW(m1.parameters(), lr=1e-2)
    o1.zero_grad(); F.cross_entropy(m1(x).reshape(-1, VOCAB), y.reshape(-1)).backward(); o1.step()
    # plasticity full mask
    named = dict(m2.named_parameters())
    popt = PlasticityOptimizer(torch.optim.AdamW(m2.parameters(), lr=1e-2), _reg(m2), named)
    ref = {n: p.detach().clone() for n, p in named.items()}
    popt.zero_grad(); F.cross_entropy(m2(x).reshape(-1, VOCAB), y.reshape(-1)).backward()
    popt.apply_and_step(_decision(_reg(m2), True), ref)
    for (n1, p1), (n2, p2) in zip(m1.named_parameters(), m2.named_parameters()):
        assert torch.allclose(p1, p2, atol=1e-6), f"{n1} differs from AdamW"

def test_budget_violation_raises():
    torch.manual_seed(0); m = GroupedModel(); reg = _reg(m); named = dict(m.named_parameters())
    popt = PlasticityOptimizer(torch.optim.AdamW(m.parameters()), reg, named)
    G = reg.n_groups()
    bad = PlasticityDecision(group_mask=torch.ones(G, dtype=torch.bool), lr_multiplier=torch.ones(G),
        consolidation=torch.zeros(G), max_update_norm=torch.zeros(G), replay_fraction=0.0,
        mode=AdaptationMode.UPDATE_EXISTING, selected_cost=G, budget=1)  # budget 1 < G
    try:
        popt.apply_and_step(bad, {})
        assert False, "should raise"
    except ValueError:
        pass
