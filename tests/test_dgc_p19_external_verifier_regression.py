from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes
from cwc.governance.p19_external_verification_contract import (
    CANONICAL_REGRESSION_COMMAND,
    REGRESSION_TEST_FILES,
    VERIFIER_ENTRYPOINT,
    VERIFIER_RUNTIME_DEPENDENCIES,
)
from cwc.governance.p19_external_verifier_regression import (
    P19ExternalVerifierRegressionError,
    build_p19_external_verifier_regression_receipt,
    current_repository_identity,
    verify_p19_external_verifier_regression_receipt,
)


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def _surface(root: Path) -> None:
    entry = root / VERIFIER_ENTRYPOINT
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text("print('verifier')\n", encoding="utf-8")
    for rel in VERIFIER_RUNTIME_DEPENDENCIES:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# runtime {rel}\n", encoding="utf-8")
    for rel in REGRESSION_TEST_FILES:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# test {rel}\n", encoding="utf-8")


def _init_repo(root: Path) -> tuple[str, str]:
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.org"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "DGC Test"], check=True)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "freeze verifier regression surface"], check=True)
    return current_repository_identity(root)


def _prepared(root: Path) -> tuple[str, str]:
    _surface(root)
    return _init_repo(root)


def _build(root: Path):
    source_commit, source_tree = _prepared(root)
    stdout = root / "evidence/regression/stdout.bin"
    stderr = root / "evidence/regression/stderr.bin"
    stdout.parent.mkdir(parents=True, exist_ok=True)
    stdout.write_bytes(b"99 passed in 2.00s\n")
    stderr.write_bytes(b"")
    receipt = build_p19_external_verifier_regression_receipt(
        repository_root=root,
        source_commit=source_commit,
        source_tree=source_tree,
        command_argv=CANONICAL_REGRESSION_COMMAND,
        stdout_path=stdout.relative_to(root),
        stderr_path=stderr.relative_to(root),
        exit_code=0,
    )
    path = root / "evidence/regression/receipt.json"
    path.write_bytes(canonical_json_bytes(receipt.document) + b"\n")
    return path, receipt.document


def test_canonical_regression_receipt_replays_current_git_runtime_tests_and_transcript(tmp_path: Path):
    path, doc = _build(tmp_path)
    loaded = verify_p19_external_verifier_regression_receipt(path, repository_root=tmp_path)
    assert loaded == doc
    assert loaded["all_regression_tests_passed"] is True
    assert loaded["exit_code"] == 0
    assert loaded["activation_authorized"] is False
    assert (loaded["source_commit"], loaded["source_tree"]) == current_repository_identity(tmp_path)


def test_nonzero_exit_code_cannot_build_green_regression_receipt(tmp_path: Path):
    source_commit, source_tree = _prepared(tmp_path)
    stdout = tmp_path / "stdout.bin"
    stderr = tmp_path / "stderr.bin"
    stdout.write_bytes(b"failed\n")
    stderr.write_bytes(b"trace\n")
    with pytest.raises(P19ExternalVerifierRegressionError, match="exit code must be zero"):
        build_p19_external_verifier_regression_receipt(
            repository_root=tmp_path,
            source_commit=source_commit,
            source_tree=source_tree,
            command_argv=CANONICAL_REGRESSION_COMMAND,
            stdout_path=stdout.relative_to(tmp_path),
            stderr_path=stderr.relative_to(tmp_path),
            exit_code=1,
        )


def test_substituted_test_command_is_rejected(tmp_path: Path):
    source_commit, source_tree = _prepared(tmp_path)
    stdout = tmp_path / "stdout.bin"
    stderr = tmp_path / "stderr.bin"
    stdout.write_bytes(b"PASS\n")
    stderr.write_bytes(b"")
    with pytest.raises(P19ExternalVerifierRegressionError, match="differs from canonical"):
        build_p19_external_verifier_regression_receipt(
            repository_root=tmp_path,
            source_commit=source_commit,
            source_tree=source_tree,
            command_argv=("python", "-m", "pytest", "-q", "tests/test_easy.py"),
            stdout_path=stdout.relative_to(tmp_path),
            stderr_path=stderr.relative_to(tmp_path),
            exit_code=0,
        )


def test_forged_source_commit_is_rejected_even_with_current_runtime_bytes(tmp_path: Path):
    _, source_tree = _prepared(tmp_path)
    stdout = tmp_path / "stdout.bin"
    stderr = tmp_path / "stderr.bin"
    stdout.write_bytes(b"PASS\n")
    stderr.write_bytes(b"")
    with pytest.raises(P19ExternalVerifierRegressionError, match="source commit differs"):
        build_p19_external_verifier_regression_receipt(
            repository_root=tmp_path,
            source_commit="1" * 40,
            source_tree=source_tree,
            command_argv=CANONICAL_REGRESSION_COMMAND,
            stdout_path=stdout.relative_to(tmp_path),
            stderr_path=stderr.relative_to(tmp_path),
            exit_code=0,
        )


def test_forged_source_tree_is_rejected_even_with_current_runtime_bytes(tmp_path: Path):
    source_commit, _ = _prepared(tmp_path)
    stdout = tmp_path / "stdout.bin"
    stderr = tmp_path / "stderr.bin"
    stdout.write_bytes(b"PASS\n")
    stderr.write_bytes(b"")
    with pytest.raises(P19ExternalVerifierRegressionError, match="source tree differs"):
        build_p19_external_verifier_regression_receipt(
            repository_root=tmp_path,
            source_commit=source_commit,
            source_tree="2" * 40,
            command_argv=CANONICAL_REGRESSION_COMMAND,
            stdout_path=stdout.relative_to(tmp_path),
            stderr_path=stderr.relative_to(tmp_path),
            exit_code=0,
        )


def test_tracked_dirty_worktree_cannot_build_regression_receipt(tmp_path: Path):
    source_commit, source_tree = _prepared(tmp_path)
    (tmp_path / VERIFIER_ENTRYPOINT).write_text("print('dirty')\n", encoding="utf-8")
    stdout = tmp_path / "stdout.bin"
    stderr = tmp_path / "stderr.bin"
    stdout.write_bytes(b"PASS\n")
    stderr.write_bytes(b"")
    with pytest.raises(P19ExternalVerifierRegressionError, match="clean tracked Git worktree"):
        build_p19_external_verifier_regression_receipt(
            repository_root=tmp_path,
            source_commit=source_commit,
            source_tree=source_tree,
            command_argv=CANONICAL_REGRESSION_COMMAND,
            stdout_path=stdout.relative_to(tmp_path),
            stderr_path=stderr.relative_to(tmp_path),
            exit_code=0,
        )


def test_runtime_mutation_after_regression_invalidates_receipt(tmp_path: Path):
    path, _ = _build(tmp_path)
    (tmp_path / VERIFIER_ENTRYPOINT).write_text("print('post-regression mutation')\n", encoding="utf-8")
    with pytest.raises(P19ExternalVerifierRegressionError, match="clean tracked Git worktree"):
        verify_p19_external_verifier_regression_receipt(path, repository_root=tmp_path)


def test_test_suite_mutation_after_regression_invalidates_receipt(tmp_path: Path):
    path, _ = _build(tmp_path)
    (tmp_path / REGRESSION_TEST_FILES[0]).write_text("# post-regression mutation\n", encoding="utf-8")
    with pytest.raises(P19ExternalVerifierRegressionError, match="clean tracked Git worktree"):
        verify_p19_external_verifier_regression_receipt(path, repository_root=tmp_path)


def test_append_only_descendant_commit_preserves_historical_regression_validity(tmp_path: Path):
    path, doc = _build(tmp_path)
    marker = tmp_path / "evidence/activation/witness.txt"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text("append-only witness\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", marker.relative_to(tmp_path).as_posix()], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "append activation witness"], check=True)
    loaded = verify_p19_external_verifier_regression_receipt(path, repository_root=tmp_path)
    assert loaded["source_commit"] == doc["source_commit"]
    assert _git(tmp_path, "rev-parse", "HEAD") != doc["source_commit"]


def test_committed_runtime_mutation_in_descendant_invalidates_historical_regression(tmp_path: Path):
    path, _ = _build(tmp_path)
    (tmp_path / VERIFIER_ENTRYPOINT).write_text("print('changed after verifier freeze')\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", VERIFIER_ENTRYPOINT], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "illegal runtime mutation"], check=True)
    with pytest.raises(P19ExternalVerifierRegressionError, match="runtime bytes differ"):
        verify_p19_external_verifier_regression_receipt(path, repository_root=tmp_path)


def test_strict_same_checkout_mode_rejects_descendant_commit(tmp_path: Path):
    path, _ = _build(tmp_path)
    marker = tmp_path / "marker.txt"
    marker.write_text("next\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "marker.txt"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "move checkout"], check=True)
    with pytest.raises(P19ExternalVerifierRegressionError, match="source commit differs"):
        verify_p19_external_verifier_regression_receipt(
            path,
            repository_root=tmp_path,
            allow_descendant_checkout=False,
        )


def test_stdout_mutation_after_regression_invalidates_receipt(tmp_path: Path):
    path, doc = _build(tmp_path)
    (tmp_path / str(doc["stdout_path"])).write_bytes(b"forged PASS\n")
    with pytest.raises(P19ExternalVerifierRegressionError, match="stdout bytes differ"):
        verify_p19_external_verifier_regression_receipt(path, repository_root=tmp_path)


def test_receipt_cannot_self_authorize_activation_even_with_recomputed_digest(tmp_path: Path):
    path, doc = _build(tmp_path)
    doc["activation_authorized"] = True
    keys = (
        "regression_generation", "source_commit", "source_tree", "canonical_command_argv",
        "runtime_manifest", "runtime_manifest_digest", "test_manifest", "test_manifest_digest",
        "method_map_digest", "stdout_path", "stdout_sha256", "stdout_bytes", "stderr_path",
        "stderr_sha256", "stderr_bytes", "exit_code", "all_regression_tests_passed",
        "execution_provenance_scope",
    )
    doc["receipt_digest"] = sha256_bytes(canonical_json_bytes({key: doc[key] for key in keys}))
    path.write_bytes(canonical_json_bytes(doc) + b"\n")
    with pytest.raises(P19ExternalVerifierRegressionError, match="cannot itself authorize activation"):
        verify_p19_external_verifier_regression_receipt(path, repository_root=tmp_path)


def test_noncanonical_receipt_bytes_are_rejected(tmp_path: Path):
    path, doc = _build(tmp_path)
    path.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")
    with pytest.raises(P19ExternalVerifierRegressionError, match="canonical JSON bytes"):
        verify_p19_external_verifier_regression_receipt(path, repository_root=tmp_path)
