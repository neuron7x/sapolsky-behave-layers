from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from cwc.governance.git_tree_reconstruction import (
    GitTreeReconstructionError,
    git_blob_oid_path,
    reconstruct_git_tree,
)


def _git(*args: str, cwd: Path) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc.stdout.strip()


@pytest.mark.skipif(shutil.which("git") is None, reason="git executable unavailable")
def test_reconstructed_tree_matches_git_for_modes_symlinks_and_nested_directories(tmp_path: Path):
    repo = tmp_path / "repo"
    _git("init", "-q", str(repo), cwd=tmp_path)
    _git("config", "user.email", "test@example.invalid", cwd=repo)
    _git("config", "user.name", "DGC Test", cwd=repo)

    (repo / "plain.txt").write_text("plain\n", encoding="utf-8")
    executable = repo / "run.sh"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    nested = repo / "tasks"
    nested.mkdir()
    (nested / "dataset.toml").write_text("[dataset]\nname='synthetic'\n", encoding="utf-8")
    os.symlink("plain.txt", repo / "plain-link")

    _git("add", ".", cwd=repo)
    _git("commit", "-qm", "fixture", cwd=repo)

    expected_root = _git("rev-parse", "HEAD^{tree}", cwd=repo)
    expected_tasks = _git("rev-parse", "HEAD:tasks", cwd=repo)
    expected_manifest = _git("rev-parse", "HEAD:tasks/dataset.toml", cwd=repo)

    # The published external generation deliberately removes .git metadata.
    shutil.rmtree(repo / ".git")

    assert reconstruct_git_tree(repo).root_tree_oid == expected_root
    assert reconstruct_git_tree(repo / "tasks").root_tree_oid == expected_tasks
    assert git_blob_oid_path(repo / "tasks" / "dataset.toml") == expected_manifest


def test_executable_mode_is_part_of_reconstructed_tree_identity(tmp_path: Path):
    root = tmp_path / "payload"
    root.mkdir()
    path = root / "tool"
    path.write_text("same bytes", encoding="utf-8")
    path.chmod(0o644)
    nonexec = reconstruct_git_tree(root).root_tree_oid
    path.chmod(0o755)
    executable = reconstruct_git_tree(root).root_tree_oid
    assert executable != nonexec


def test_git_tree_reconstruction_rejects_dot_git_and_special_objects(tmp_path: Path):
    root = tmp_path / "payload"
    root.mkdir()
    (root / ".git").mkdir()
    with pytest.raises(GitTreeReconstructionError, match=".git"):
        reconstruct_git_tree(root)

    (root / ".git").rmdir()
    fifo = root / "fifo"
    if hasattr(os, "mkfifo"):
        os.mkfifo(fifo)
        with pytest.raises(GitTreeReconstructionError, match="unsupported filesystem object"):
            reconstruct_git_tree(root)
