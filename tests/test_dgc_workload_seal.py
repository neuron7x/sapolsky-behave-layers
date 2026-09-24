import hashlib
import os

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


def test_symlink_is_bound_as_link_not_external_target_content(tmp_path):
    root = tmp_path / "workload"
    root.mkdir()
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"secret-v1")
    os.symlink(outside, root / "link")
    before = seal_materialized_workload(
        family_id="F", root=root, task_ids=("t1",), expected_task_count=1
    )
    outside.write_bytes(b"secret-v2-with-different-size")
    after = seal_materialized_workload(
        family_id="F", root=root, task_ids=("t1",), expected_task_count=1
    )
    assert before.file_tree_sha256 == after.file_tree_sha256
    assert before.total_bytes == len(os.fsencode(str(outside)))
    assert before.file_count == 1


def test_symlink_target_string_change_changes_tree_digest(tmp_path):
    root = tmp_path / "workload"
    root.mkdir()
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.write_text("same")
    second.write_text("same")
    link = root / "link"
    os.symlink(first, link)
    a = seal_materialized_workload(family_id="F", root=root, task_ids=("t1",), expected_task_count=1)
    link.unlink()
    os.symlink(second, link)
    b = seal_materialized_workload(family_id="F", root=root, task_ids=("t1",), expected_task_count=1)
    assert a.file_tree_sha256 != b.file_tree_sha256


def test_file_mode_change_changes_tree_digest(tmp_path):
    path = tmp_path / "tool.sh"
    path.write_text("#!/bin/sh\nexit 0\n")
    path.chmod(0o644)
    a = seal_materialized_workload(family_id="F", root=tmp_path, task_ids=("t1",), expected_task_count=1)
    path.chmod(0o755)
    b = seal_materialized_workload(family_id="F", root=tmp_path, task_ids=("t1",), expected_task_count=1)
    assert a.file_tree_sha256 != b.file_tree_sha256


def test_fifo_is_rejected(tmp_path):
    if not hasattr(os, "mkfifo"):
        pytest.skip("mkfifo unavailable")
    os.mkfifo(tmp_path / "pipe")
    with pytest.raises(ValueError, match="unsupported evidence filesystem object"):
        seal_materialized_workload(family_id="F", root=tmp_path, task_ids=("t1",), expected_task_count=1)


def test_symlink_root_is_rejected(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "x").write_text("x")
    link = tmp_path / "root-link"
    link.symlink_to(root, target_is_directory=True)
    with pytest.raises(ValueError, match="real directory"):
        seal_materialized_workload(family_id="F", root=link, task_ids=("t1",), expected_task_count=1)
