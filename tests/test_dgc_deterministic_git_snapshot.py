from __future__ import annotations

import subprocess
import tarfile
from pathlib import Path

import pytest

from cwc.governance.deterministic_git_snapshot import (
    DeterministicGitSnapshotError,
    create_deterministic_git_snapshot,
)


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def _repo(tmp_path: Path) -> tuple[Path, str]:
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.org"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "DGC Test"], check=True)
    (root / "regular.txt").write_text("regular\n", encoding="utf-8")
    executable = root / "run.sh"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    (root / "nested").mkdir()
    (root / "nested/target.txt").write_text("target\n", encoding="utf-8")
    (root / "nested/link").symlink_to("target.txt")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "snapshot"], check=True)
    return root, _git(root, "rev-parse", "HEAD")


def test_git_object_snapshot_is_byte_identical_and_metadata_normalized(tmp_path: Path):
    root, commit = _repo(tmp_path)
    one = tmp_path / "one.tar.gz"
    two = tmp_path / "two.tar.gz"
    first = create_deterministic_git_snapshot(repository_root=root, commit=commit, destination=one)
    second = create_deterministic_git_snapshot(repository_root=root, commit=commit, destination=two)
    assert first.archive_sha256 == second.archive_sha256
    assert one.read_bytes() == two.read_bytes()
    assert first.commit == commit
    assert first.tree == _git(root, "rev-parse", "HEAD^{tree}")
    assert first.entry_population_digest == second.entry_population_digest
    assert first.symlink_count == 1
    with tarfile.open(one, "r:gz") as archive:
        members = {row.name: row for row in archive.getmembers()}
        assert members["regular.txt"].mode == 0o644
        assert members["run.sh"].mode == 0o755
        assert members["nested/link"].issym()
        assert members["nested/link"].linkname == "target.txt"
        assert all(row.mtime == 0 and row.uid == 0 and row.gid == 0 for row in members.values())


def test_symlink_that_escapes_archive_root_fails_closed(tmp_path: Path):
    root, _ = _repo(tmp_path)
    (root / "nested/link").unlink()
    (root / "nested/link").symlink_to("../../outside")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "unsafe link"], check=True)
    with pytest.raises(DeterministicGitSnapshotError, match="escapes archive root"):
        create_deterministic_git_snapshot(
            repository_root=root,
            commit=_git(root, "rev-parse", "HEAD"),
            destination=tmp_path / "unsafe.tar.gz",
        )


def test_absolute_symlink_target_fails_closed(tmp_path: Path):
    root, _ = _repo(tmp_path)
    (root / "nested/link").unlink()
    (root / "nested/link").symlink_to("/etc/passwd")
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "absolute link"], check=True)
    with pytest.raises(DeterministicGitSnapshotError, match="absolute symlink"):
        create_deterministic_git_snapshot(
            repository_root=root,
            commit=_git(root, "rev-parse", "HEAD"),
            destination=tmp_path / "absolute.tar.gz",
        )


def test_gitlink_submodule_object_is_not_a_self_contained_source_snapshot(tmp_path: Path):
    root, commit = _repo(tmp_path)
    subprocess.run(
        ["git", "-C", str(root), "update-index", "--add", "--cacheinfo", f"160000,{commit},vendor/submodule"],
        check=True,
    )
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "gitlink"], check=True)
    with pytest.raises(DeterministicGitSnapshotError, match="submodules/special objects rejected"):
        create_deterministic_git_snapshot(
            repository_root=root,
            commit=_git(root, "rev-parse", "HEAD"),
            destination=tmp_path / "gitlink.tar.gz",
        )
