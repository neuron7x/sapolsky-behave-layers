from __future__ import annotations

import gzip
import io
import posixpath
import subprocess
import tarfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file

SCHEMA = "DGC_DETERMINISTIC_GIT_SNAPSHOT_V1"
ALLOWED_BLOB_MODES = frozenset({"100644", "100755", "120000"})


class DeterministicGitSnapshotError(RuntimeError):
    pass


def _run(root: Path, *args: str, text: bool = False) -> bytes | str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=text,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise DeterministicGitSnapshotError(f"git command failed: {' '.join(args)}") from exc
    return proc.stdout


def _oid(name: str, value: str) -> str:
    text = value.strip().lower()
    if len(text) != 40 or any(ch not in "0123456789abcdef" for ch in text):
        raise DeterministicGitSnapshotError(f"{name} must be lowercase 40-hex Git object id")
    return text


def _safe_path(raw: bytes) -> str:
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise DeterministicGitSnapshotError("Git snapshot path must be UTF-8") from exc
    if "\n" in text or "\r" in text or "\x00" in text:
        raise DeterministicGitSnapshotError("Git snapshot path contains control separator")
    path = PurePosixPath(text)
    if not text or path.is_absolute() or ".." in path.parts:
        raise DeterministicGitSnapshotError("Git snapshot path escapes archive root")
    return path.as_posix()


def _safe_symlink_target(path: str, target_bytes: bytes) -> str:
    try:
        target = target_bytes.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise DeterministicGitSnapshotError(f"symlink target is not UTF-8: {path}") from exc
    if not target or "\x00" in target or "\n" in target or "\r" in target:
        raise DeterministicGitSnapshotError(f"invalid symlink target: {path}")
    target_path = PurePosixPath(target)
    if target_path.is_absolute():
        raise DeterministicGitSnapshotError(f"absolute symlink target rejected: {path}")
    combined = posixpath.normpath(posixpath.join(posixpath.dirname(path), target))
    if combined == ".." or combined.startswith("../"):
        raise DeterministicGitSnapshotError(f"symlink target escapes archive root: {path}")
    return target


@dataclass(frozen=True, slots=True)
class GitSnapshotEntry:
    path: str
    mode: str
    blob_oid: str
    bytes: int
    symlink: bool
    entry_digest: str


@dataclass(frozen=True, slots=True)
class DeterministicGitSnapshot:
    commit: str
    tree: str
    entries: tuple[GitSnapshotEntry, ...]
    entry_population_digest: str
    file_count: int
    symlink_count: int
    archive_sha256: str
    archive_bytes: int

    @property
    def document(self) -> dict[str, object]:
        return {"schema": SCHEMA, **asdict(self)}


def _entries(root: Path, commit: str) -> tuple[tuple[str, str, str], ...]:
    raw = _run(root, "ls-tree", "-r", "-z", commit, text=False)
    assert isinstance(raw, bytes)
    rows: list[tuple[str, str, str]] = []
    for record in raw.split(b"\x00"):
        if not record:
            continue
        if b"\t" not in record:
            raise DeterministicGitSnapshotError("malformed git ls-tree record")
        meta, raw_path = record.split(b"\t", 1)
        try:
            mode_b, kind_b, oid_b = meta.split()
            mode = mode_b.decode("ascii")
            kind = kind_b.decode("ascii")
            oid = oid_b.decode("ascii")
        except (ValueError, UnicodeDecodeError) as exc:
            raise DeterministicGitSnapshotError("malformed git tree metadata") from exc
        path = _safe_path(raw_path)
        if kind != "blob" or mode not in ALLOWED_BLOB_MODES:
            raise DeterministicGitSnapshotError(
                f"unsupported Git tree object (submodules/special objects rejected): {mode} {kind} {path}"
            )
        rows.append((path, mode, _oid("blob oid", oid)))
    if not rows:
        raise DeterministicGitSnapshotError("Git snapshot contains no files")
    return tuple(sorted(rows, key=lambda row: row[0]))


def create_deterministic_git_snapshot(
    *,
    repository_root: Path,
    commit: str,
    destination: Path,
) -> DeterministicGitSnapshot:
    root = Path(repository_root).resolve()
    commit_oid_raw = _run(root, "rev-parse", f"{commit}^{{commit}}", text=True)
    tree_oid_raw = _run(root, "rev-parse", f"{commit}^{{tree}}", text=True)
    assert isinstance(commit_oid_raw, str) and isinstance(tree_oid_raw, str)
    commit_oid = _oid("commit", commit_oid_raw)
    tree_oid = _oid("tree", tree_oid_raw)

    entry_records: list[GitSnapshotEntry] = []
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as raw_out:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_out, mtime=0, compresslevel=9) as gz:
            with tarfile.open(fileobj=gz, mode="w", format=tarfile.PAX_FORMAT) as archive:
                for path, mode, blob_oid in _entries(root, commit_oid):
                    blob = _run(root, "cat-file", "blob", blob_oid, text=False)
                    assert isinstance(blob, bytes)
                    info = tarfile.TarInfo(name=path)
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.mtime = 0
                    symlink = mode == "120000"
                    if symlink:
                        info.type = tarfile.SYMTYPE
                        info.mode = 0o777
                        info.size = 0
                        info.linkname = _safe_symlink_target(path, blob)
                        archive.addfile(info)
                    else:
                        info.type = tarfile.REGTYPE
                        info.mode = 0o755 if mode == "100755" else 0o644
                        info.size = len(blob)
                        archive.addfile(info, io.BytesIO(blob))
                    payload = {
                        "path": path,
                        "mode": mode,
                        "blob_oid": blob_oid,
                        "bytes": len(blob),
                        "symlink": symlink,
                    }
                    entry_records.append(GitSnapshotEntry(
                        **payload,
                        entry_digest=sha256_bytes(canonical_json_bytes(payload)),
                    ))

    ordered = tuple(entry_records)
    population_digest = sha256_bytes(canonical_json_bytes([asdict(row) for row in ordered]))
    return DeterministicGitSnapshot(
        commit=commit_oid,
        tree=tree_oid,
        entries=ordered,
        entry_population_digest=population_digest,
        file_count=len(ordered),
        symlink_count=sum(row.symlink for row in ordered),
        archive_sha256=sha256_file(destination),
        archive_bytes=destination.stat().st_size,
    )
