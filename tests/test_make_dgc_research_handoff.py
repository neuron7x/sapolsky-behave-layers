from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from scripts.make_dgc_research_handoff import HandoffError, build_handoff, verify_handoff


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "DGC Test")
    (root / "a.txt").write_text("alpha\n")
    (root / "nested").mkdir()
    (root / "nested" / "b.txt").write_text("beta\n")
    _git(root, "add", ".")
    _git(root, "commit", "-q", "-m", "fixture")
    return root


def test_builder_uses_committed_blobs_not_dirty_worktree(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    (root / "a.txt").write_text("DIRTY\n")
    out = tmp_path / "handoff.zip"
    state = build_handoff(root, out)
    verified = verify_handoff(out)
    assert verified["git_commit"] == state["git_commit"]
    import zipfile
    with zipfile.ZipFile(out) as archive:
        assert archive.read("a.txt") == b"alpha\n"


def test_double_build_is_byte_reproducible(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    a = tmp_path / "a.zip"
    b = tmp_path / "b.zip"
    build_handoff(root, a)
    build_handoff(root, b)
    assert hashlib.sha256(a.read_bytes()).digest() == hashlib.sha256(b.read_bytes()).digest()


def test_tampered_archive_fails_verification(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    out = tmp_path / "handoff.zip"
    build_handoff(root, out)
    import zipfile
    with zipfile.ZipFile(out, "a") as archive:
        archive.writestr("a.txt", "tampered")
    with pytest.raises(HandoffError):
        verify_handoff(out)
