from experiments.wp4_adaptive_depth.src.runner_exact_compute_pilot import run_pilot


def test_exact_compute_pilot_contract():
    result = run_pilot([0, 1], allocation_replicates=3, batch_size=64, device="cpu")
    assert result["status"] == "EXPLORATORY_PILOT_NOT_PREREGISTERED"
    rows = result["rows"]
    assert len(rows) == 8
    assert all(row["total_hops_each_policy"] > 0 for row in rows)
    assert all(0.0 <= row["input_blind_exact_solved_mean"] <= 1.0 for row in rows)
    assert all(item["exact_total_compute"] for item in result["summary"].values())
