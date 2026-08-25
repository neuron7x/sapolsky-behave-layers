from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path


class GitTreeReconstructionError(RuntimeError):
    """Raised when a filesystem payload cannot be represented as a canonical Git tree."""


def _git_object_oid(object_type: str, payload: bytes) -> str:
    if object_type not in {"blob", "tree"}:
        raise ValueError("unsupported Git object type")
    header = f"{object_type} {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


def git_blob_oid_bytes(payload: bytes) -> str:
    return _git_object_oid("blob", bytes(payload))


def git_blob_oid_path(path: Path) -> str:
    candidate = Path(path)
    if candidate.is_symlink():
        return git_blob_oid_bytes(os.fsencode(os.readlink(candidate)))
    if not candidate.is_file():
        raise GitTreeReconstructionError("Git blob path must be a regular file or symlink")
    return git_blob_oid_bytes(candidate.read_bytes())


@dataclass(frozen=True, slots=True)
class GitTreeReconstruction:
    root_tree_oid: str
    tree_count: int
    blob_count: int


def reconstruct_git_tree(root: Path) -> GitTreeReconstruction:
    """Reconstruct a Git SHA-1 tree directly from published working-tree bytes.

    No repository metadata or Git object database is consulted. Regular-file content,
    executable mode, symlink target bytes, directory structure and Git tree ordering are
    all bound into the resulting object id. Special filesystem objects and any `.git`
    path component are rejected fail-closed.
    """

    supplied_root = Path(root)
    if supplied_root.is_symlink() or not supplied_root.is_dir():
        raise GitTreeReconstructionError("Git tree root must be a real directory")
    root = supplied_root.resolve()

    def walk(directory: Path) -> tuple[str, int, int]:
        encoded_entries: list[tuple[bytes, bytes]] = []
        tree_count = 1
        blob_count = 0

        try:
            children = list(directory.iterdir())
        except OSError as exc:
            raise GitTreeReconstructionError(f"cannot enumerate payload directory: {directory}") from exc

        for path in children:
            if path.name == ".git":
                raise GitTreeReconstructionError("published payload must not contain .git metadata")
            try:
                st = path.lstat()
            except OSError as exc:
                raise GitTreeReconstructionError(f"cannot stat payload object: {path}") from exc

            name = os.fsencode(path.name)
            if b"\x00" in name or b"/" in name:
                raise GitTreeReconstructionError("filesystem name cannot be represented in a Git tree")

            if stat.S_ISDIR(st.st_mode):
                child_oid, child_trees, child_blobs = walk(path)
                mode = b"40000"
                oid_bytes = bytes.fromhex(child_oid)
                sort_key = name + b"/"
                tree_count += child_trees
                blob_count += child_blobs
            elif stat.S_ISLNK(st.st_mode):
                try:
                    target = os.fsencode(os.readlink(path))
                except OSError as exc:
                    raise GitTreeReconstructionError(f"cannot read symlink target: {path}") from exc
                mode = b"120000"
                oid_bytes = bytes.fromhex(git_blob_oid_bytes(target))
                sort_key = name
                blob_count += 1
            elif stat.S_ISREG(st.st_mode):
                try:
                    payload = path.read_bytes()
                except OSError as exc:
                    raise GitTreeReconstructionError(f"cannot read payload file: {path}") from exc
                mode = b"100755" if st.st_mode & 0o111 else b"100644"
                oid_bytes = bytes.fromhex(git_blob_oid_bytes(payload))
                sort_key = name
                blob_count += 1
            else:
                raise GitTreeReconstructionError(f"unsupported filesystem object in Git payload: {path}")

            encoded_entries.append((sort_key, mode + b" " + name + b"\0" + oid_bytes))

        encoded_entries.sort(key=lambda row: row[0])
        tree_payload = b"".join(entry for _, entry in encoded_entries)
        return _git_object_oid("tree", tree_payload), tree_count, blob_count

    root_oid, tree_count, blob_count = walk(root)
    return GitTreeReconstruction(root_oid, tree_count, blob_count)
