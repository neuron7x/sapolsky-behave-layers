from experiments.wp4_adaptive_depth.src.runner_exact_compute_v3 import (
    ALL_DISTRIBUTIONS,
    run_seed,
)


def test_v3_small_run_obeys_frozen_contract():
    result = run_seed(100, allocation_replicates=2, batch_size=32, device="cpu")
    assert result["protocol_commit"] == "6245a6d"
    assert set(result["distributions"]) == set(ALL_DISTRIBUTIONS)
    for cell in result["distributions"].values():
        assert cell["exact_compute_contract"] is True
        assert cell["total_hops_each_primary_arm"] == cell["adaptive"]["total_hops"]
        assert set(cell["noisy_halt_secondary"]) == {"0.01", "0.05", "0.1"}
