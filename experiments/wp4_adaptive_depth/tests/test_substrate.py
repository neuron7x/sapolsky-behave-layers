import torch

from experiments.wp4_adaptive_depth.src.runner import stable_distribution_seed
from experiments.wp4_adaptive_depth.src.substrate import allocate_input_blind_exact, run_policy
from experiments.wp4_adaptive_depth.src.task_hops import generate_batch


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
    K=round(m.float().mean().item())
    g=torch.Generator().manual_seed(1)
    gap=run_policy("adaptive",K,tb,vv,st,tg,m,g)["solved"]-run_policy("static",K,tb,vv,st,tg,m,g)["solved"]
    assert abs(gap-(m>K).float().mean().item())<1e-6   # exact Jensen gap

def test_distribution_seed_is_stable_and_namespaced():
    assert stable_distribution_seed(0, "uniform") == stable_distribution_seed(0, "uniform")
    assert stable_distribution_seed(0, "uniform") != stable_distribution_seed(1, "uniform")
    assert stable_distribution_seed(0, "uniform") != stable_distribution_seed(0, "bimodal")


def test_input_blind_exact_allocator_conserves_integer_budget():
    for batch_size, total in [(1, 0), (7, 31), (512, 2307)]:
        alloc = allocate_input_blind_exact(
            batch_size, total, torch.Generator().manual_seed(9), torch.device("cpu")
        )
        assert len(alloc) == batch_size
        assert int(alloc.sum()) == total
        assert int(alloc.max()) - int(alloc.min()) <= 1


def test_random_exact_matches_adaptive_total_compute():
    table, values, start, target, m = _batch(5)
    adaptive = run_policy(
        "adaptive", 0, table, values, start, target, m, torch.Generator().manual_seed(1)
    )
    baseline = run_policy(
        "random_exact", 0, table, values, start, target, m,
        torch.Generator().manual_seed(2), total_hops=adaptive["total_hops"]
    )
    assert baseline["total_hops"] == adaptive["total_hops"]
    assert baseline["avg_hops"] == adaptive["avg_hops"]


def test_input_blind_exact_allocator_rejects_invalid_contracts():
    gen = torch.Generator().manual_seed(0)
    for batch_size, total in [(0, 1), (2, -1)]:
        try:
            allocate_input_blind_exact(batch_size, total, gen, torch.device("cpu"))
        except ValueError:
            pass
        else:
            raise AssertionError("invalid exact-allocation contract was accepted")


def test_adaptive_halt_fails_closed_on_nonconvergent_cycle():
    table, values, start, target, m = _batch(7)
    # Force example 0 into a two-cycle, violating the absorbing-task contract.
    first = int(start[0])
    second = (first + 1) % table.shape[1]
    table[0, first] = second
    table[0, second] = first
    try:
        run_policy(
            "adaptive", 0, table, values, start, target, m,
            torch.Generator().manual_seed(1)
        )
    except RuntimeError as exc:
        assert "did not converge" in str(exc)
    else:
        raise AssertionError("nonconvergent adaptive execution did not fail closed")
