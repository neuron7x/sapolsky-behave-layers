"""Content-addressed, privacy-aware intake for untrusted evidence trees."""

from __future__ import annotations

import hashlib
import os
from collections import Counter, defaultdict
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

CHUNK_SIZE = 1024 * 1024
RESTRICTED_MARKERS = (
    "особист",
    "автобіограф",
    "щоден",
    "conversations.json",
    "chat.html",
    "digital-identity",
    "private",
    "secret",
    "credentials",
)
VENDOR_SEGMENTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "site-packages",
}
VENDOR_PREFIXES = ("dist-",)
ARCHIVE_SUFFIXES = {
    ".7z",
    ".bz2",
    ".gz",
    ".rar",
    ".tar",
    ".tgz",
    ".xz",
    ".zip",
}


def classify_path(relative_path: str) -> str:
    """Conservatively assign one non-overlapping intake class from path metadata."""
    folded = relative_path.casefold()
    parts = set(Path(folded).parts)
    if any(marker in folded for marker in RESTRICTED_MARKERS):
        return "restricted"
    if parts & VENDOR_SEGMENTS or any(part.startswith(VENDOR_PREFIXES) for part in parts):
        return "vendor"
    if "archive" in folded or Path(folded).suffix in ARCHIVE_SUFFIXES:
        return "archive"
    return "candidate"


def hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def _walk(root: Path) -> Iterator[tuple[str, Path, str]]:
    """Yield every regular file and symlink without following directory symlinks."""
    for current, dirs, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        retained_dirs = []
        for name in sorted(dirs):
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink():
                yield relative, path, "symlink"
            else:
                retained_dirs.append(name)
        dirs[:] = retained_dirs
        for name in sorted(files):
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            yield relative, path, "symlink" if path.is_symlink() else "file"


def audit_tree(
    root: Path,
    *,
    record: Callable[[dict[str, Any]], None] | None = None,
    progress: Callable[[int, int], None] | None = None,
    progress_every: int = 10_000,
) -> dict[str, Any]:
    """Hash every regular file and return aggregate provenance without content."""
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise NotADirectoryError(root)
    category_files: Counter[str] = Counter()
    category_bytes: Counter[str] = Counter()
    digest_instances: dict[str, list[tuple[int, int, int]]] = defaultdict(list)
    corpus = hashlib.sha256()
    file_count = byte_count = symlink_count = error_count = 0
    errors: Counter[str] = Counter()

    for relative, path, kind in _walk(root):
        if kind == "symlink":
            symlink_count += 1
            if record is not None:
                record({"path": relative, "kind": "symlink", "category": "quarantined"})
            continue
        file_count += 1
        category = classify_path(relative)
        try:
            before = path.stat()
            digest = hash_file(path)
            after = path.stat()
            before_identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            after_identity = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            if before_identity != after_identity:
                raise RuntimeError("file changed while hashing")
            size = after.st_size
        except (OSError, RuntimeError) as exc:
            error_count += 1
            errors[type(exc).__name__] += 1
            if record is not None:
                record({"path": relative, "kind": "error", "category": category, "error": type(exc).__name__})
            continue
        byte_count += size
        category_files[category] += 1
        category_bytes[category] += size
        digest_instances[digest].append((size, after.st_dev, after.st_ino))
        corpus.update(relative.encode("utf-8", errors="surrogateescape"))
        corpus.update(b"\0")
        corpus.update(str(size).encode())
        corpus.update(b"\0")
        corpus.update(digest.encode())
        corpus.update(b"\n")
        if record is not None:
            record({"path": relative, "kind": "file", "category": category, "size": size, "sha256": digest})
        if progress is not None and file_count % progress_every == 0:
            progress(file_count, byte_count)

    duplicate_files = duplicate_bytes = 0
    for instances in digest_instances.values():
        if len(instances) > 1:
            duplicate_files += len(instances) - 1
            physical_copies = {(device, inode) for _, device, inode in instances}
            duplicate_bytes += max(len(physical_copies) - 1, 0) * instances[0][0]
    return {
        "schema_version": 1,
        "algorithm": "sha256",
        "complete": error_count == 0,
        "root": root.name,
        "corpus_sha256": corpus.hexdigest(),
        "file_count": file_count,
        "hashed_file_count": file_count - error_count,
        "byte_count": byte_count,
        "symlink_count": symlink_count,
        "error_count": error_count,
        "error_types": dict(sorted(errors.items())),
        "category_file_count": dict(sorted(category_files.items())),
        "category_byte_count": dict(sorted(category_bytes.items())),
        "duplicate_file_count": duplicate_files,
        "duplicate_reclaimable_bytes": duplicate_bytes,
    }
