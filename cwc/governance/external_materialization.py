from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 compatibility for the canonical product CI.
    import tomli as tomllib

_SHA256_RE = re.compile(r"^sha256:([0-9a-f]{64})$")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_sha256(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class TerminalDatasetManifest:
    dataset_name: str
    task_count: int
    tasks: tuple[tuple[str, str], ...]
    canonical_task_digest: str


def parse_terminal_dataset_manifest(text: str, *, expected_count: int) -> TerminalDatasetManifest:
    data = tomllib.loads(text)
    dataset = data.get("dataset")
    if not isinstance(dataset, dict) or not str(dataset.get("name", "")).strip():
        raise ValueError("terminal dataset name missing")
    raw_tasks = data.get("tasks")
    if not isinstance(raw_tasks, list):
        raise ValueError("terminal tasks list missing")
    rows: list[tuple[str, str]] = []
    names: set[str] = set()
    for row in raw_tasks:
        if not isinstance(row, dict):
            raise ValueError("invalid terminal task row")
        name = str(row.get("name", "")).strip()
        digest = str(row.get("digest", "")).strip()
        if not name or name in names:
            raise ValueError("terminal task names must be non-empty and unique")
        match = _SHA256_RE.fullmatch(digest)
        if match is None:
            raise ValueError(f"invalid terminal task digest for {name}")
        names.add(name)
        rows.append((name, match.group(1)))
    if len(rows) != expected_count:
        raise ValueError(f"terminal task count mismatch: expected {expected_count}, observed {len(rows)}")
    ordered = tuple(sorted(rows))
    return TerminalDatasetManifest(
        dataset_name=str(dataset["name"]).strip(),
        task_count=len(ordered),
        tasks=ordered,
        canonical_task_digest=canonical_sha256(ordered),
    )


def _git(root: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc.stdout.strip()


@dataclass(frozen=True, slots=True)
class TerminalGitVerification:
    commit: str
    repository_tree: str
    tasks_tree: str
    dataset_manifest_blob: str


def verify_terminal_git_checkout(
    root: Path,
    *,
    expected_commit: str,
    expected_repository_tree: str,
    expected_tasks_tree: str,
    expected_dataset_manifest_blob: str,
) -> TerminalGitVerification:
    observed = TerminalGitVerification(
        commit=_git(root, "rev-parse", "HEAD"),
        repository_tree=_git(root, "rev-parse", "HEAD^{tree}"),
        tasks_tree=_git(root, "rev-parse", "HEAD:tasks"),
        dataset_manifest_blob=_git(root, "rev-parse", "HEAD:tasks/dataset.toml"),
    )
    expected = TerminalGitVerification(
        expected_commit,
        expected_repository_tree,
        expected_tasks_tree,
        expected_dataset_manifest_blob,
    )
    if observed != expected:
        raise ValueError(f"Terminal-Bench Git identity mismatch: observed={observed} expected={expected}")
    return observed


@dataclass(frozen=True, slots=True)
class SweParquetVerification:
    bytes_size: int
    sha256: str
    row_count: int
    instance_ids: tuple[str, ...]
    task_manifest_sha256: str


def verify_swe_parquet(
    path: Path,
    *,
    expected_sha256: str,
    expected_bytes: int | None,
    expected_count: int,
) -> SweParquetVerification:
    size = path.stat().st_size
    if expected_bytes is not None and size != expected_bytes:
        raise ValueError(f"SWE parquet byte-size mismatch: expected {expected_bytes}, observed {size}")
    digest = sha256_file(path)
    if digest != expected_sha256:
        raise ValueError(f"SWE parquet SHA-256 mismatch: expected {expected_sha256}, observed {digest}")
    try:
        import pyarrow.parquet as pq
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "pyarrow is required to verify SWE row count and instance_id manifest; refusing MATERIALIZED_VERIFIED"
        ) from exc
    table = pq.read_table(path, columns=["instance_id"])
    ids = tuple(sorted(str(x.as_py()).strip() for x in table.column("instance_id")))
    if len(ids) != expected_count or len(set(ids)) != expected_count or any(not x for x in ids):
        raise ValueError(
            f"SWE task manifest mismatch: expected {expected_count} unique IDs, observed {len(ids)} rows/{len(set(ids))} unique"
        )
    return SweParquetVerification(
        bytes_size=size,
        sha256=digest,
        row_count=len(ids),
        instance_ids=ids,
        task_manifest_sha256=canonical_sha256(ids),
    )
