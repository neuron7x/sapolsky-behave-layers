from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from cwc.governance.evidence_closure import ClosureError, EvidenceClosureLedger
from cwc.governance.materialization_closure import _assert_repository_identity


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc.stdout.strip()


def _repo(tmp_path: Path) -> tuple[Path, str, str]:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "test")
    (repo / ".gitignore").write_text("eval_bundle/\n")
    (repo / "tracked.txt").write_text("canonical")
    _git(repo, "add", ".gitignore", "tracked.txt")
    _git(repo, "commit", "-q", "-m", "fixture")
    return repo, _git(repo, "rev-parse", "HEAD"), _git(repo, "rev-parse", "HEAD^{tree}")


def _ledger(repo: Path, commit: str, tree: str) -> EvidenceClosureLedger:
    return EvidenceClosureLedger(
        repository_root=repo,
        ledger_path=repo / "eval_bundle" / "ledger.json",
        generation_id="g1",
        repo_commit=commit,
        repo_tree=tree,
    )


def test_repository_identity_accepts_exact_clean_tree_and_ignored_runtime_evidence(tmp_path: Path):
    repo, commit, tree = _repo(tmp_path)
    ledger = _ledger(repo, commit, tree)
    (repo / "eval_bundle").mkdir()
    (repo / "eval_bundle" / "runtime.json").write_text("ignored")
    _assert_repository_identity(ledger)


def test_repository_identity_rejects_dirty_tracked_tree(tmp_path: Path):
    repo, commit, tree = _repo(tmp_path)
    ledger = _ledger(repo, commit, tree)
    (repo / "tracked.txt").write_text("mutated")
    with pytest.raises(ClosureError, match="clean"):
        _assert_repository_identity(ledger)


def test_repository_identity_rejects_wrong_commit_binding(tmp_path: Path):
    repo, commit, tree = _repo(tmp_path)
    ledger = _ledger(repo, "0" * 40, tree)
    with pytest.raises(ClosureError, match="HEAD"):
        _assert_repository_identity(ledger)
