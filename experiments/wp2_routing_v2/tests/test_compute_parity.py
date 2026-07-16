from experiments.wp2_routing_v2.src.compute import (direct_path_flops, semantic_path_cost,
    controller_flops, total_batch_flops, parity_ratio)

def test_semantic_more_expensive_than_direct():
    assert semantic_path_cost() > direct_path_flops()

def test_controller_overhead_small():
    tot = total_batch_flops(64, 32)
    assert 64 * controller_flops() / tot <= 0.05

def test_random_vs_learned_same_budget_parity():
    # both route exactly K=32 semantic -> identical total FLOPs
    a = total_batch_flops(64, 32)
    b = total_batch_flops(64, 32)
    assert parity_ratio(a, b) <= 0.01
