from __future__ import annotations

import json
from pathlib import Path

import pytest

import cwc.governance.benchmark_runtime as runtime
from cwc.governance.benchmark_runtime import BenchmarkRuntimeError, verify_benchmark_runtime
from cwc.governance.materialization_transaction import sha256_file


COMMIT = "1" * 40
TREE = "2" * 40
LOCK = "3" * 40


def _fixture(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    manifests = repo / "manifests"
    manifests.mkdir()
    manifest = manifests / "runtime.json"
    doc = {
        "schema": "DGC_BENCHMARK_RUNTIME_MANIFEST_V1",
        "family_id": "TERMINAL_BENCH_2_1",
        "runtime_name": "harbor",
        "runtime_version": "0.23.0",
        "repository": "harbor-framework/harbor",
        "repository_commit": COMMIT,
        "repository_tree": TREE,
        "lock_file_path": "uv.lock",
        "lock_file_blob_oid": LOCK,
        "invocation": ["uv", "run", "--frozen", "harbor"],
        "root_environment_variable": "DGC_BENCHMARK_RUNTIME_ROOT",
        "local_materialization_required": True,
    }
    manifest.write_text(json.dumps(doc, sort_keys=True) + "\n", encoding="utf-8")
    execution = {
        "components": [{
            "component": "benchmark_runtime_manifest",
            "path": "manifests/runtime.json",
            "sha256": sha256_file(manifest),
            "bytes": manifest.stat().st_size,
            "schema": "DGC_BENCHMARK_RUNTIME_MANIFEST_V1",
        }]
    }
    checkout = tmp_path / "runtime"
    checkout.mkdir()
    (checkout / "uv.lock").write_text("lock\n", encoding="utf-8")
    return repo, manifest, execution, checkout


def _identity(*, commit=COMMIT, tree=TREE, lock=LOCK, dirty=""):
    def capture(root: Path, *args: str) -> str:
        if args == ("rev-parse", "HEAD"):
            return commit
        if args == ("rev-parse", "HEAD^{tree}"):
            return tree
        if args == ("rev-parse", "HEAD:uv.lock"):
            return lock
        if args == ("status", "--porcelain=v1", "--untracked-files=all"):
            return dirty
        raise AssertionError(args)
    return capture


def test_exact_runtime_identity_is_admitted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo, _, execution, checkout = _fixture(tmp_path)
    monkeypatch.setattr(runtime, "_capture", _identity())
    verified = verify_benchmark_runtime(
        repository_root=repo,
        execution_freeze=execution,
        runtime_root=checkout,
        family_id="TERMINAL_BENCH_2_1",
    )
    assert verified.repository_commit == COMMIT
    assert verified.repository_tree == TREE
    assert verified.lock_file_blob_oid == LOCK
    assert verified.invocation == ("uv", "run", "--frozen", "harbor")
    assert len(verified.manifest_sha256) == 64


@pytest.mark.parametrize(
    ("capture", "message"),
    [
        (_identity(commit="4" * 40), "commit mismatch"),
        (_identity(tree="4" * 40), "tree mismatch"),
        (_identity(lock="4" * 40), "lock blob mismatch"),
        (_identity(dirty=" M uv.lock"), "must be clean"),
    ],
)
def test_runtime_identity_drift_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capture, message: str
):
    repo, _, execution, checkout = _fixture(tmp_path)
    monkeypatch.setattr(runtime, "_capture", capture)
    with pytest.raises(BenchmarkRuntimeError, match=message):
        verify_benchmark_runtime(
            repository_root=repo,
            execution_freeze=execution,
            runtime_root=checkout,
            family_id="TERMINAL_BENCH_2_1",
        )


def test_manifest_byte_drift_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo, manifest, execution, checkout = _fixture(tmp_path)
    doc = json.loads(manifest.read_text())
    doc["runtime_version"] = "tampered"
    manifest.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setattr(runtime, "_capture", _identity())
    with pytest.raises(BenchmarkRuntimeError, match="manifest bytes differ"):
        verify_benchmark_runtime(
            repository_root=repo,
            execution_freeze=execution,
            runtime_root=checkout,
            family_id="TERMINAL_BENCH_2_1",
        )


def test_runtime_root_symlink_is_rejected(tmp_path: Path):
    repo, _, execution, checkout = _fixture(tmp_path)
    alias = tmp_path / "runtime-alias"
    alias.symlink_to(checkout, target_is_directory=True)
    with pytest.raises(BenchmarkRuntimeError, match="root symlink rejected"):
        verify_benchmark_runtime(
            repository_root=repo,
            execution_freeze=execution,
            runtime_root=alias,
            family_id="TERMINAL_BENCH_2_1",
        )


def test_family_substitution_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    repo, _, execution, checkout = _fixture(tmp_path)
    monkeypatch.setattr(runtime, "_capture", _identity())
    with pytest.raises(BenchmarkRuntimeError, match="family mismatch"):
        verify_benchmark_runtime(
            repository_root=repo,
            execution_freeze=execution,
            runtime_root=checkout,
            family_id="SWE_BENCH_VERIFIED",
        )
