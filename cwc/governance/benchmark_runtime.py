from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.materialization_transaction import sha256_file


class BenchmarkRuntimeError(RuntimeError):
    pass


def _git_oid(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 40 or any(ch not in "0123456789abcdef" for ch in text):
        raise BenchmarkRuntimeError(f"{name} must be a 40-char Git object id")
    return text


def _safe_file(root: Path, value: object) -> tuple[Path, str]:
    rel = Path(str(value))
    if not str(value) or rel.is_absolute() or ".." in rel.parts:
        raise BenchmarkRuntimeError("benchmark runtime manifest path must be repository-relative")
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise BenchmarkRuntimeError(f"benchmark runtime manifest symlink rejected: {rel.as_posix()}")
    resolved = (root / rel).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise BenchmarkRuntimeError("benchmark runtime manifest escapes repository root") from exc
    if not resolved.is_file():
        raise BenchmarkRuntimeError("benchmark runtime manifest file missing")
    return resolved, rel.as_posix()


def _capture(runtime_root: Path, *args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(runtime_root), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise BenchmarkRuntimeError("benchmark runtime Git identity cannot be verified") from exc
    return proc.stdout.strip()


@dataclass(frozen=True, slots=True)
class VerifiedBenchmarkRuntime:
    family_id: str
    runtime_name: str
    runtime_version: str
    repository: str
    repository_commit: str
    repository_tree: str
    lock_file_path: str
    lock_file_blob_oid: str
    invocation: tuple[str, ...]
    manifest_sha256: str
    runtime_root: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "family_id": self.family_id,
            "runtime_name": self.runtime_name,
            "runtime_version": self.runtime_version,
            "repository": self.repository,
            "repository_commit": self.repository_commit,
            "repository_tree": self.repository_tree,
            "lock_file_path": self.lock_file_path,
            "lock_file_blob_oid": self.lock_file_blob_oid,
            "invocation": list(self.invocation),
            "manifest_sha256": self.manifest_sha256,
            "runtime_root": self.runtime_root,
        }


def verify_benchmark_runtime(
    *,
    repository_root: Path,
    execution_freeze: Mapping[str, object],
    runtime_root: Path,
    family_id: str,
) -> VerifiedBenchmarkRuntime:
    root = Path(repository_root).resolve()
    runtime = Path(runtime_root)
    if runtime.is_symlink():
        raise BenchmarkRuntimeError("benchmark runtime root symlink rejected")
    runtime = runtime.resolve()
    if not runtime.is_dir():
        raise BenchmarkRuntimeError("benchmark runtime root missing")

    rows = execution_freeze.get("components")
    if not isinstance(rows, list):
        raise BenchmarkRuntimeError("execution component population missing")
    matches = [
        row for row in rows
        if isinstance(row, Mapping) and row.get("component") == "benchmark_runtime_manifest"
    ]
    if len(matches) != 1:
        raise BenchmarkRuntimeError("exactly one benchmark runtime component required")
    row = dict(matches[0])
    manifest_path, manifest_rel = _safe_file(root, row.get("path"))
    manifest_sha = str(row.get("sha256", "")).strip().lower()
    if len(manifest_sha) != 64 or any(ch not in "0123456789abcdef" for ch in manifest_sha):
        raise BenchmarkRuntimeError("benchmark runtime component sha256 malformed")
    if sha256_file(manifest_path) != manifest_sha:
        raise BenchmarkRuntimeError("benchmark runtime manifest bytes differ from execution freeze")
    if manifest_rel != row.get("path"):
        raise BenchmarkRuntimeError("benchmark runtime manifest path is non-canonical")

    try:
        doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise BenchmarkRuntimeError("invalid benchmark runtime manifest JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != "DGC_BENCHMARK_RUNTIME_MANIFEST_V1":
        raise BenchmarkRuntimeError("unexpected benchmark runtime manifest schema")
    family = str(family_id).strip()
    if not family or doc.get("family_id") != family:
        raise BenchmarkRuntimeError("benchmark runtime family mismatch")

    commit = _git_oid("repository_commit", doc.get("repository_commit"))
    tree = _git_oid("repository_tree", doc.get("repository_tree"))
    lock_blob = _git_oid("lock_file_blob_oid", doc.get("lock_file_blob_oid"))
    lock_rel = Path(str(doc.get("lock_file_path", "")))
    if not str(lock_rel) or lock_rel.is_absolute() or ".." in lock_rel.parts:
        raise BenchmarkRuntimeError("benchmark runtime lock path invalid")
    lock = runtime / lock_rel
    current = runtime
    for part in lock_rel.parts:
        current = current / part
        if current.is_symlink():
            raise BenchmarkRuntimeError("benchmark runtime lock path symlink rejected")
    if not lock.is_file():
        raise BenchmarkRuntimeError("benchmark runtime lock file missing")

    observed_commit = _capture(runtime, "rev-parse", "HEAD")
    observed_tree = _capture(runtime, "rev-parse", "HEAD^{tree}")
    observed_lock_blob = _capture(runtime, "rev-parse", f"HEAD:{lock_rel.as_posix()}")
    dirty = _capture(runtime, "status", "--porcelain=v1", "--untracked-files=all")
    if dirty:
        raise BenchmarkRuntimeError("benchmark runtime checkout must be clean")
    if observed_commit != commit:
        raise BenchmarkRuntimeError("benchmark runtime commit mismatch")
    if observed_tree != tree:
        raise BenchmarkRuntimeError("benchmark runtime tree mismatch")
    if observed_lock_blob != lock_blob:
        raise BenchmarkRuntimeError("benchmark runtime lock blob mismatch")

    invocation = doc.get("invocation")
    if (
        not isinstance(invocation, list)
        or not invocation
        or not all(isinstance(x, str) and x.strip() for x in invocation)
    ):
        raise BenchmarkRuntimeError("benchmark runtime invocation malformed")

    return VerifiedBenchmarkRuntime(
        family_id=family,
        runtime_name=str(doc.get("runtime_name", "")).strip(),
        runtime_version=str(doc.get("runtime_version", "")).strip(),
        repository=str(doc.get("repository", "")).strip(),
        repository_commit=commit,
        repository_tree=tree,
        lock_file_path=lock_rel.as_posix(),
        lock_file_blob_oid=lock_blob,
        invocation=tuple(invocation),
        manifest_sha256=manifest_sha,
        runtime_root=str(runtime),
    )
