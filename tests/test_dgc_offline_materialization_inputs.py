from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "dgc_materialize_external_sources.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("dgc_materialize_external_sources_offline", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _clean_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "test")
    (repo / ".gitignore").write_text("ignored.bin\n")
    (repo / "tracked.txt").write_text("tracked")
    _git(repo, "add", ".gitignore", "tracked.txt")
    _git(repo, "commit", "-q", "-m", "fixture")
    return repo


def test_offline_copy_contains_only_tracked_files(tmp_path: Path):
    module = _load_module()
    repo = _clean_repo(tmp_path)
    (repo / "ignored.bin").write_bytes(b"must-not-leak")
    destination = tmp_path / "export"
    module._copy_clean_tracked_tree(repo, destination)
    assert (destination / "tracked.txt").read_text() == "tracked"
    assert (destination / ".gitignore").is_file()
    assert not (destination / "ignored.bin").exists()
    assert not (destination / ".git").exists()


def test_offline_copy_rejects_untracked_input(tmp_path: Path):
    module = _load_module()
    repo = _clean_repo(tmp_path)
    (repo / "untracked.txt").write_text("contamination")
    with pytest.raises(RuntimeError, match="must be clean"):
        module._copy_clean_tracked_tree(repo, tmp_path / "export")


def test_offline_copy_rejects_modified_tracked_input(tmp_path: Path):
    module = _load_module()
    repo = _clean_repo(tmp_path)
    (repo / "tracked.txt").write_text("mutated")
    with pytest.raises(RuntimeError, match="must be clean"):
        module._copy_clean_tracked_tree(repo, tmp_path / "export")
