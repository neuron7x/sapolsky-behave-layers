import torch
from experiments.wp4_adaptive_depth.src.task_hops import generate_batch, MAX_M
from experiments.wp4_adaptive_depth.src.substrate import run_policy

def _batch(seed=0, w=None):
    g=torch.Generator().manual_seed(seed)
    return generate_batch(512, g, "cpu", m_weights=w)

def test_static_solved_equals_P_m_le_K():
    tb,vv,st,tg,m=_batch(0)
    g=torch.Generator().manual_seed(1)
    for K in [2,4,6]:
        r=run_policy("static",K,tb,vv,st,tg,m,g)
        assert abs(r["solved"]-(m<=K).float().mean().item())<1e-6

def test_adaptive_solves_all_at_avg_Em():
    tb,vv,st,tg,m=_batch(0)
    g=torch.Generator().manual_seed(1)
    r=run_policy("adaptive",0,tb,vv,st,tg,m,g)
    assert r["solved"]==1.0                       # halt-on-converge reaches absorber
    assert abs(r["avg_hops"]-m.float().mean().item())<1e-6  # uses exactly E[m] compute

def test_adaptive_equals_oracle():
    tb,vv,st,tg,m=_batch(2)
    g=torch.Generator().manual_seed(1)
    a=run_policy("adaptive",5,tb,vv,st,tg,m,g)
    o=run_policy("oracle",5,tb,vv,st,tg,m,g)
    assert a["solved"]==o["solved"]==1.0

def test_jensen_gap_equals_theory():
    tb,vv,st,tg,m=_batch(3)
    K=int(round(m.float().mean().item()))
    g=torch.Generator().manual_seed(1)
    gap=run_policy("adaptive",K,tb,vv,st,tg,m,g)["solved"]-run_policy("static",K,tb,vv,st,tg,m,g)["solved"]
    assert abs(gap-(m>K).float().mean().item())<1e-6   # exact Jensen gap
