from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from cwc.governance.materialization_transaction import canonical_json_bytes, file_manifest


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


def seal_materialized_workload(
    *, family_id: str, root: Path, task_ids: Iterable[str], expected_task_count: int
) -> WorkloadSeal:
    family = str(family_id).strip()
    if not family:
        raise ValueError("family_id required")
    supplied_root = Path(root)
    if supplied_root.is_symlink() or not supplied_root.is_dir():
        raise ValueError("materialized workload root must be a real directory")
    root = supplied_root.resolve()
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

    rows = file_manifest(root, excluded_names=frozenset({"WORKLOAD_SEAL.json", "SHA256SUMS"}))
    if not rows:
        raise ValueError("materialized workload contains no payload files")
    # V2 tree semantics bind path, object kind, POSIX mode, byte/link-target length,
    # and SHA-256 without dereferencing symlinks.
    tree_digest = _sha256_bytes(canonical_json_bytes(rows))
    total_bytes = sum(size for _, _, _, size, _ in rows)
    return WorkloadSeal(
        family_id=family,
        expected_task_count=expected_task_count,
        task_count=len(tasks),
        task_manifest_sha256=task_manifest,
        file_tree_sha256=tree_digest,
        file_count=len(rows),
        total_bytes=total_bytes,
    )
