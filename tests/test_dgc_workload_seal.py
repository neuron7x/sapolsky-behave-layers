import pytest

from cwc.governance.workload_seal import seal_materialized_workload


def test_materialized_workload_seal_is_deterministic(tmp_path):
    (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "b.txt").write_text("b\n", encoding="utf-8")
    a = seal_materialized_workload(
        family_id="F", root=tmp_path, task_ids=("t2", "t1"), expected_task_count=2
    )
    b = seal_materialized_workload(
        family_id="F", root=tmp_path, task_ids=("t1", "t2"), expected_task_count=2
    )
    assert a == b
    assert a.file_count == 2


def test_task_count_mismatch_fails_closed(tmp_path):
    (tmp_path / "x").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        seal_materialized_workload(
            family_id="F", root=tmp_path, task_ids=("t1",), expected_task_count=2
        )


def test_duplicate_task_id_fails_closed(tmp_path):
    (tmp_path / "x").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError):
        seal_materialized_workload(
            family_id="F", root=tmp_path, task_ids=("t1", "t1"), expected_task_count=2
        )


def test_payload_tamper_changes_tree_digest(tmp_path):
    path = tmp_path / "x"
    path.write_text("one", encoding="utf-8")
    before = seal_materialized_workload(
        family_id="F", root=tmp_path, task_ids=("t1",), expected_task_count=1
    )
    path.write_text("two", encoding="utf-8")
    after = seal_materialized_workload(
        family_id="F", root=tmp_path, task_ids=("t1",), expected_task_count=1
    )
    assert before.file_tree_sha256 != after.file_tree_sha256
