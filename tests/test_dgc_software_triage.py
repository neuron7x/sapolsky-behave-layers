from __future__ import annotations

from experiments.dgc_04_software_triage.run import ORDER, TASKS


def test_dgc04_workload_and_order_are_frozen() -> None:
    assert ORDER == ("A", "H", "C", "S", "I")
    assert [task.task_id for task in TASKS] == [
        "CLEAN", "A", "H", "C", "S", "I", "A+H", "C+S", "H+I", "A+C+S", "ALL"
    ]
    assert len(TASKS) == 11
