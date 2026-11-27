from __future__ import annotations

import hashlib
import os
import re
import stat
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

REQUIRED_PRODUCT_EVIDENCE_FILES = (
    "PREREGISTRATION.md",
    "CLAIM_BOUNDARY.md",
    "BASELINES.md",
    "environment.lock",
    "task_manifest.json",
    "model_manifest.json",
    "raw_results.jsonl",
    "aggregate_results.json",
    "statistical_report.json",
    "economics.json",
    "faults.json",
    "independent_replication.json",
    "PRODUCT_VERDICT.md",
    "SHA256SUMS",
)

MANIFEST_PROFILE = "cwc-dgc-sha256sums/1"
MAX_MANIFEST_BYTES = 256 * 1024
MAX_PAYLOAD_FILES = 1024
MAX_PAYLOAD_BYTES = 128 * 1024 * 1024
MAX_TOTAL_PAYLOAD_BYTES = 512 * 1024 * 1024
_MANIFEST_NAME = "SHA256SUMS"
_REQUIRED_PAYLOAD = REQUIRED_PRODUCT_EVIDENCE_FILES[:-1]
_ROW = re.compile(r"([0-9a-f]{64}) [ *](.+)")
_COMPONENT = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._-]{0,127}")
_RESERVED = {"con", "prn", "aux", "nul"} | {
    f"{prefix}{number}" for prefix in ("com", "lpt") for number in range(1, 10)
}


@dataclass(frozen=True, slots=True)
class EvidenceBundleVerification:
    complete: bool
    missing_files: tuple[str, ...]
    hash_mismatches: tuple[str, ...]
    unhashed_files: tuple[str, ...]
    manifest_sha256: str | None = None
    manifest_profile: str = MANIFEST_PROFILE


class _InvalidBundle(ValueError):
    pass


def _parse_manifest(content: bytes) -> dict[str, str]:
    declared: dict[str, str] = {}
    paths: dict[str, tuple[str, bool]] = {}
    for line in content.decode("ascii").split("\n"):
        if not line:
            continue
        match = _ROW.fullmatch(line)
        if match is None or len(declared) >= MAX_PAYLOAD_FILES:
            raise _InvalidBundle("invalid manifest row or payload count")
        digest, name = match.groups()
        parts = name.split("/")
        if len(parts) > 8 or any(
            not _COMPONENT.fullmatch(part) or part.endswith(".") or part.split(".")[0].lower() in _RESERVED
            for part in parts
        ) or parts[0].lower() == _MANIFEST_NAME.lower():
            raise _InvalidBundle("noncanonical manifest path")

        for index in range(1, len(parts) + 1):
            prefix = "/".join(parts[:index])
            payload = index == len(parts)
            previous = paths.get(prefix.lower())
            if previous is not None and (payload or previous != (prefix, False)):
                raise _InvalidBundle("duplicate or aliased manifest path")
            paths[prefix.lower()] = (prefix, payload)
        declared[name] = digest
    return declared


def _file_fingerprint(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev, metadata.st_ino, metadata.st_mode, metadata.st_nlink,
        metadata.st_size, metadata.st_mtime_ns, metadata.st_ctime_ns,
    )


def _regular_file_at(directory: int, name: str) -> bool:
    try:
        return stat.S_ISREG(os.stat(name, dir_fd=directory, follow_symlinks=False).st_mode)
    except FileNotFoundError:
        return False


@contextmanager
def _open_payload(directory: int, name: str, byte_limit: int) -> Iterator[BinaryIO]:
    parts = name.split("/")
    parents: list[tuple[int, str, os.stat_result]] = []
    with ExitStack() as cleanup:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            cleanup.callback(os.close, child)
            parents.append((directory, part, os.fstat(child)))
            directory = child

        leaf = parts[-1]
        metadata = os.stat(leaf, dir_fd=directory, follow_symlinks=False)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1 or metadata.st_size > byte_limit:
            raise _InvalidBundle("payload must be a bounded, unaliased regular file")
        fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        cleanup.callback(os.close, fd)
        expected = _file_fingerprint(metadata)
        if _file_fingerprint(os.fstat(fd)) != expected:
            raise _InvalidBundle("payload changed while opening")
        handle = cleanup.enter_context(os.fdopen(fd, "rb", closefd=False))
        yield handle
        if (
            _file_fingerprint(os.fstat(fd)) != expected
            or _file_fingerprint(os.stat(leaf, dir_fd=directory, follow_symlinks=False)) != expected
        ):
            raise _InvalidBundle("payload changed while reading")
        for parent, part, observed in parents:
            current = os.stat(part, dir_fd=parent, follow_symlinks=False)
            if not stat.S_ISDIR(current.st_mode) or (current.st_dev, current.st_ino) != (
                observed.st_dev, observed.st_ino,
            ):
                raise _InvalidBundle("payload parent changed while reading")


def _hash_payload(handle: BinaryIO, limit: int) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    while chunk := handle.read(min(1 << 20, limit - size + 1)):
        size += len(chunk)
        if size > limit:
            raise _InvalidBundle("payload size exceeded its read limit")
        digest.update(chunk)
    return digest.hexdigest(), size


def _verify_at(directory: int, expected_manifest_sha256: str | None) -> EvidenceBundleVerification:
    missing = tuple(name for name in REQUIRED_PRODUCT_EVIDENCE_FILES if not _regular_file_at(directory, name))
    if _MANIFEST_NAME in missing:
        return EvidenceBundleVerification(False, missing, (), ())

    try:
        with _open_payload(directory, _MANIFEST_NAME, MAX_MANIFEST_BYTES) as handle:
            content = handle.read(MAX_MANIFEST_BYTES + 1)
        if len(content) > MAX_MANIFEST_BYTES:
            raise _InvalidBundle("manifest byte limit exceeded")
        declared = _parse_manifest(content)
    except (OSError, _InvalidBundle, UnicodeError):
        return EvidenceBundleVerification(False, missing, ("MALFORMED_SHA256SUMS",), ())

    manifest_sha256 = hashlib.sha256(content).hexdigest()
    if expected_manifest_sha256 is not None and manifest_sha256 != expected_manifest_sha256:
        return EvidenceBundleVerification(False, missing, (_MANIFEST_NAME,), (), manifest_sha256)

    unhashed = tuple(name for name in _REQUIRED_PAYLOAD if name not in declared and name not in missing)
    if missing or unhashed:
        return EvidenceBundleVerification(False, missing, (), unhashed, manifest_sha256)

    remaining = MAX_TOTAL_PAYLOAD_BYTES
    mismatches: list[str] = []
    for name, expected in sorted(declared.items()):
        try:
            limit = min(remaining, MAX_PAYLOAD_BYTES)
            with _open_payload(directory, name, limit) as handle:
                actual, size = _hash_payload(handle, limit)
        except (OSError, _InvalidBundle):
            mismatches.append(name)
            break
        remaining -= size
        if actual != expected:
            mismatches.append(name)
    return EvidenceBundleVerification(not mismatches, (), tuple(mismatches), (), manifest_sha256)


def verify_evidence_bundle(
    root: Path, *, expected_manifest_sha256: str | None = None,
) -> EvidenceBundleVerification:
    """Check the V1 manifest-declared payload in a caller-selected local POSIX directory.

    Entries use portable relative ASCII paths and the standard SHA256SUMS row
    syntax. Unlisted staging files are outside the package. Directory-relative
    descriptors confine traversal, and metadata checks detect changes during
    individual reads. A stable release snapshot requires immutable staging.
    Supply the raw manifest digest from a trusted outer receipt to bind the
    roster and bytes. Completeness alone establishes byte integrity.
    """
    if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
        return EvidenceBundleVerification(False, REQUIRED_PRODUCT_EVIDENCE_FILES, ("UNSUPPORTED_FILESYSTEM",), ())
    try:
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except FileNotFoundError:
        return EvidenceBundleVerification(False, REQUIRED_PRODUCT_EVIDENCE_FILES, (), ())
    except OSError:
        return EvidenceBundleVerification(False, REQUIRED_PRODUCT_EVIDENCE_FILES, ("INVALID_BUNDLE_ROOT",), ())
    try:
        return _verify_at(directory, expected_manifest_sha256)
    except OSError:
        return EvidenceBundleVerification(False, REQUIRED_PRODUCT_EVIDENCE_FILES, ("BUNDLE_IO_ERROR",), ())
    finally:
        os.close(directory)
