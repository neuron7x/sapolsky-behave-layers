from __future__ import annotations

from scripts.via_status import resolve


def test_status_propagates_v1_block_to_all_descendants() -> None:
    status = resolve()
    assert status["prior_kill_rule_active"] is True
    assert status["current_scientific_frontier"] == "VIA-V1"
    assert status["levels"][0]["status"] == "BLOCKED"
    assert all(level["status"] == "BLOCKED_BY_ANCESTOR" for level in status["levels"][1:])
