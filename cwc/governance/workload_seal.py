from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True, slots=True)
class WorkloadSeal:
    family_id: str
    expected_task_count: int
    task_count: int
    task_manifest_sha256: str
    file_tree_sha256: str
    file_count: int
    total_bytes: int


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def seal_materialized_workload(
    *, family_id: str, root: Path, task_ids: Iterable[str], expected_task_count: int
) -> WorkloadSeal:
    family = str(family_id).strip()
    if not family:
        raise ValueError("family_id required")
    if not root.is_dir():
        raise ValueError("materialized workload root must be a directory")
    if expected_task_count <= 0:
        raise ValueError("expected_task_count must be > 0")

    tasks = tuple(sorted(str(x).strip() for x in task_ids if str(x).strip()))
    if len(tasks) != len(set(tasks)):
        raise ValueError("task IDs must be unique")
    if len(tasks) != expected_task_count:
        raise ValueError(
            f"task count mismatch: expected {expected_task_count}, observed {len(tasks)}"
        )
    task_manifest = _sha256_bytes(
        json.dumps(tasks, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )

    rows: list[tuple[str, int, str]] = []
    total_bytes = 0
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        rel = path.relative_to(root).as_posix()
        if rel in {"WORKLOAD_SEAL.json", "SHA256SUMS"}:
            continue
        size = path.stat().st_size
        digest = _sha256_file(path)
        rows.append((rel, size, digest))
        total_bytes += size
    if not rows:
        raise ValueError("materialized workload contains no payload files")
    tree_digest = _sha256_bytes(
        json.dumps(rows, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )
    return WorkloadSeal(
        family_id=family,
        expected_task_count=expected_task_count,
        task_count=len(tasks),
        task_manifest_sha256=task_manifest,
        file_tree_sha256=tree_digest,
        file_count=len(rows),
        total_bytes=total_bytes,
    )
