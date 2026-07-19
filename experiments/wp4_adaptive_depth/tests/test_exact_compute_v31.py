from experiments.wp4_adaptive_depth.src.runner_exact_compute_v31 import (
    FROZEN_TOTAL_HOPS,
    run_seed,
)


def test_frozen_totals_match_protocol_formula():
    weights = {
        "uniform": [1] * 8,
        "easy_skew": [5, 4, 3, 2, 1, 1, 1, 1],
        "hard_skew": [1, 1, 1, 1, 2, 3, 4, 5],
        "bimodal": [4, 1, 0.5, 0.5, 0.5, 0.5, 1, 4],
        "extreme_easy": [12, 8, 4, 2, 1, 1, 1, 1],
        "extreme_hard": [1, 1, 1, 1, 2, 4, 8, 12],
        "mid_peak": [1, 2, 6, 10, 10, 6, 2, 1],
    }
    derived = {
        name: round(4096 * sum((i + 1) * value for i, value in enumerate(row)) / sum(row))
        for name, row in weights.items()
    }
    assert derived == FROZEN_TOTAL_HOPS


def test_v31_rejects_nonfrozen_batch_size():
    try:
        run_seed(200, allocation_replicates=32, batch_size=128, device="cpu")
    except ValueError as exc:
        assert "batch_size=4096" in str(exc)
    else:
        raise AssertionError("v3.1 accepted a nonfrozen batch size")
