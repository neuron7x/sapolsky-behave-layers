from __future__ import annotations

import json
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
    verify_p19_external_verifier_regression_receipt,
)


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


def _build(root: Path):
    _surface(root)
    stdout = root / "evidence/regression/stdout.bin"
    stderr = root / "evidence/regression/stderr.bin"
    stdout.parent.mkdir(parents=True, exist_ok=True)
    stdout.write_bytes(b"99 passed in 2.00s\n")
    stderr.write_bytes(b"")
    receipt = build_p19_external_verifier_regression_receipt(
        repository_root=root,
        source_commit="1" * 40,
        source_tree="2" * 40,
        command_argv=CANONICAL_REGRESSION_COMMAND,
        stdout_path=stdout.relative_to(root),
        stderr_path=stderr.relative_to(root),
        exit_code=0,
    )
    path = root / "evidence/regression/receipt.json"
    path.write_bytes(canonical_json_bytes(receipt.document) + b"\n")
    return path, receipt.document


def test_canonical_regression_receipt_replays_current_runtime_tests_and_transcript(tmp_path: Path):
    path, doc = _build(tmp_path)
    loaded = verify_p19_external_verifier_regression_receipt(path, repository_root=tmp_path)
    assert loaded == doc
    assert loaded["all_regression_tests_passed"] is True
    assert loaded["exit_code"] == 0
    assert loaded["activation_authorized"] is False


def test_nonzero_exit_code_cannot_build_green_regression_receipt(tmp_path: Path):
    _surface(tmp_path)
    stdout = tmp_path / "stdout.bin"
    stderr = tmp_path / "stderr.bin"
    stdout.write_bytes(b"failed\n")
    stderr.write_bytes(b"trace\n")
    with pytest.raises(P19ExternalVerifierRegressionError, match="exit code must be zero"):
        build_p19_external_verifier_regression_receipt(
            repository_root=tmp_path,
            source_commit="1" * 40,
            source_tree="2" * 40,
            command_argv=CANONICAL_REGRESSION_COMMAND,
            stdout_path=stdout.relative_to(tmp_path),
            stderr_path=stderr.relative_to(tmp_path),
            exit_code=1,
        )


def test_substituted_test_command_is_rejected(tmp_path: Path):
    _surface(tmp_path)
    stdout = tmp_path / "stdout.bin"
    stderr = tmp_path / "stderr.bin"
    stdout.write_bytes(b"PASS\n")
    stderr.write_bytes(b"")
    with pytest.raises(P19ExternalVerifierRegressionError, match="differs from canonical"):
        build_p19_external_verifier_regression_receipt(
            repository_root=tmp_path,
            source_commit="1" * 40,
            source_tree="2" * 40,
            command_argv=("python", "-m", "pytest", "-q", "tests/test_easy.py"),
            stdout_path=stdout.relative_to(tmp_path),
            stderr_path=stderr.relative_to(tmp_path),
            exit_code=0,
        )


def test_runtime_mutation_after_regression_invalidates_receipt(tmp_path: Path):
    path, _ = _build(tmp_path)
    (tmp_path / VERIFIER_ENTRYPOINT).write_text("print('post-regression mutation')\n", encoding="utf-8")
    with pytest.raises(P19ExternalVerifierRegressionError, match="runtime bytes differ"):
        verify_p19_external_verifier_regression_receipt(path, repository_root=tmp_path)


def test_test_suite_mutation_after_regression_invalidates_receipt(tmp_path: Path):
    path, _ = _build(tmp_path)
    (tmp_path / REGRESSION_TEST_FILES[0]).write_text("# post-regression mutation\n", encoding="utf-8")
    with pytest.raises(P19ExternalVerifierRegressionError, match="test bytes differ"):
        verify_p19_external_verifier_regression_receipt(path, repository_root=tmp_path)


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
