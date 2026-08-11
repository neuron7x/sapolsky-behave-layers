from __future__ import annotations

from experiments.real_transfer_01 import temporal_gate


def test_real_transfer01_temporal_git_order_is_strict() -> None:
    result = temporal_gate.analyze()
    assert result["verdict"] == "PASS", result
    assert result["scientific_status"] == "NOT_TESTED"
    assert [stage["name"] for stage in result["stages"]] == [
        "PARENT_PREREG",
        "AMENDMENT_001",
        "AMENDMENT_002",
        "IMPLEMENTATION",
    ]
    assert all(check["strict_ancestor"] for check in result["order_checks"])


def test_real_transfer01_temporal_self_test_kills_order_mutations() -> None:
    assert temporal_gate.self_test()
