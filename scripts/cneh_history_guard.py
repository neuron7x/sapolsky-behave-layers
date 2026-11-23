"""Offline preservation of CNEH scientific inputs and Git-anchored evidence.

Current checksums do not authenticate history. The CLI's anchor commits are fixed;
only the checkout bytes, file types, historical rosters and ledger append are tested.
No scientific qualification or independent replication is asserted.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess

ROOT = Path(__file__).resolve().parents[1]
ORIGINAL = "4ccb02e7da16c4a65573e8e7c7e98a0b8456119b"
A1 = "a65ab49681bc748acb71cde9abe5bc99a4045ab3"
A2 = "f5625363f72be3652d6b6e6fbfad1ceeac57e857"
A2_CI = "ff4dc6a77124ae3575788a2b953cbbc2f4872d2a"
LEDGER = "docs/lab/EXPERIMENT_LEDGER.jsonl"


@dataclass(frozen=True)
class Anchor:
    commit: str
    path: str
    tree: bool = False
    exact_roster: bool = False


ANCHORS = tuple(Anchor(ORIGINAL, "experiments/cneh_exp_01/" + name) for name in (
    "protocol.json", "PREREGISTRATION.md", "frozen_sources.lock", "CNEH-04-DC_Formal_Specification.md",
)) + (
    Anchor(ORIGINAL, "artifacts", tree=True),
    Anchor(A1, "artifacts/cneh-exp-01-a1", tree=True, exact_roster=True),
    Anchor(A2, "artifacts/cneh-exp-01-a2", tree=True, exact_roster=True),
    Anchor(A2_CI, "artifacts/cneh-exp-01-a2-ci", tree=True, exact_roster=True),
)


class HistoryViolation(ValueError):
    """An expected historical invariant was not established."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def git(repo: Path, *args: str, data: bytes | None = None) -> bytes:
    env = dict(os.environ)
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_NAMESPACE",
                "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES"):
        env.pop(key, None)
    env.update(GIT_NO_REPLACE_OBJECTS="1", GIT_GRAFT_FILE=os.devnull, GIT_OPTIONAL_LOCKS="0")
    result = subprocess.run(["git", "--no-replace-objects", "-C", str(repo), *args],
                            input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    if result.returncode:
        raise HistoryViolation(f"Git {args[0]} failed ({result.returncode}): {result.stderr.decode(errors='replace').strip()}")
    return result.stdout


def relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise HistoryViolation("unsafe historical path")
    return path


def regular_file(repo: Path, relative: str, mode: str | None = None) -> Path:
    parts = relative_path(relative).parts
    current = repo
    for part in parts[:-1]:
        current /= part
        if not stat.S_ISDIR(current.lstat().st_mode):
            raise HistoryViolation(f"historical parent is not a real directory: {relative}")
    path = current / parts[-1]
    observed = path.lstat()
    if not stat.S_ISREG(observed.st_mode):
        raise HistoryViolation(f"historical path is not a regular file: {relative}")
    if mode is not None and bool(observed.st_mode & 0o111) != (mode == "100755"):
        raise HistoryViolation(f"historical executable mode changed: {relative}")
    return path


def file_digest(path: Path) -> str:
    # O_NOFOLLOW also closes the final-component symlink gap after lstat.
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(descriptor, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise HistoryViolation("historical descriptor is not a regular file")
        result = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
        return result.hexdigest()


def object_digest(kind: str, raw: bytes) -> str:
    return hashlib.sha1(kind.encode() + b" " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def require_commit(repo: Path, commit: str, head: str) -> None:
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise HistoryViolation("historical commit must be an exact SHA")
    raw = git(repo, "cat-file", "commit", commit)
    if object_digest("commit", raw) != commit:
        raise HistoryViolation("historical commit object digest mismatch")
    git(repo, "merge-base", "--is-ancestor", commit, head)


def entries(repo: Path, anchor: Anchor) -> dict[str, tuple[str, str]]:
    relative_path(anchor.path)
    result = {}
    for row in git(repo, "ls-tree", "-r", "-z", anchor.commit, "--", anchor.path).split(b"\0"):
        if not row:
            continue
        metadata, raw_path = row.split(b"\t", 1)
        mode, kind, oid = metadata.decode().split()
        path = raw_path.decode()
        relative_path(path)
        if kind != "blob" or mode not in ("100644", "100755"):
            raise HistoryViolation(f"unsupported historical Git path type: {path}")
        if path in result:
            raise HistoryViolation("duplicate historical Git path")
        result[path] = (mode, oid)
    if not result or (not anchor.tree and set(result) != {anchor.path}):
        raise HistoryViolation(f"missing or empty historical anchor: {anchor.path}")
    if anchor.tree and any(not path.startswith(anchor.path + "/") for path in result):
        raise HistoryViolation("historical root is not a tree")
    return result


def blob_digests(repo: Path, object_ids: set[str]) -> dict[str, str]:
    ordered = sorted(object_ids)
    raw = git(repo, "cat-file", "--batch", data="".join(oid + "\n" for oid in ordered).encode())
    offset = 0
    result = {}
    for oid in ordered:
        end = raw.index(b"\n", offset)
        actual, kind, size_text = raw[offset:end].decode().split()
        size = int(size_text)
        start = end + 1
        content = raw[start:start + size]
        if actual != oid or kind != "blob" or len(content) != size or raw[start + size:start + size + 1] != b"\n":
            raise HistoryViolation("invalid Git blob response")
        if object_digest("blob", content) != oid:
            raise HistoryViolation("historical blob object digest mismatch")
        result[oid] = digest(content)
        offset = start + size + 1
    if offset != len(raw):
        raise HistoryViolation("unexpected Git blob response bytes")
    return result


def current_roster(repo: Path, relative: str) -> set[str]:
    root = repo / relative_path(relative)
    if not stat.S_ISDIR(root.lstat().st_mode):
        raise HistoryViolation(f"historical root is not a real directory: {relative}")
    result = set()
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs:
            if not stat.S_ISDIR((Path(directory) / name).lstat().st_mode):
                raise HistoryViolation("symlink or invalid directory in historical root")
        for name in files:
            path = Path(directory) / name
            if not stat.S_ISREG(path.lstat().st_mode):
                raise HistoryViolation("symlink or invalid file in historical root")
            result.add(path.relative_to(repo).as_posix())
    return result


def ledger_rows(raw: bytes) -> list[dict]:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise HistoryViolation("duplicate JSON key in ledger")
            result[key] = value
        return result
    def invalid(value):
        raise HistoryViolation("nonfinite JSON ledger value: " + value)
    def finite(value):
        number = float(value)
        if not math.isfinite(number):
            raise HistoryViolation("nonfinite JSON ledger number")
        return number
    rows = [json.loads(line, object_pairs_hook=pairs, parse_constant=invalid, parse_float=finite)
            for line in raw.splitlines()]
    if not rows or any(not isinstance(row, dict) or not isinstance(row.get("run_id"), str) or not row["run_id"] for row in rows):
        raise HistoryViolation("empty or invalid ledger row")
    if len({row["run_id"] for row in rows}) != len(rows):
        raise HistoryViolation("duplicate ledger run_id")
    return rows


def verify_history(repo: Path, *, anchors: tuple[Anchor, ...] = ANCHORS,
                   ledger_commit: str = A2, ledger_path: str = LEDGER) -> dict:
    repo = repo.resolve()
    if not anchors:
        raise HistoryViolation("historical anchor roster is empty")
    top = Path(git(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    if top != repo or git(repo, "rev-parse", "--is-shallow-repository").strip() != b"false":
        raise HistoryViolation("repository root and complete Git history required")
    head = git(repo, "rev-parse", "HEAD").decode().strip()
    for commit in sorted({anchor.commit for anchor in anchors} | {ledger_commit}):
        require_commit(repo, commit, head)
    inventories = [(anchor, entries(repo, anchor)) for anchor in anchors]
    ledger_entry = entries(repo, Anchor(ledger_commit, ledger_path))
    hashes = blob_digests(repo, {oid for _, rows in inventories for _, oid in rows.values()} | {row[1] for row in ledger_entry.values()})
    receipts = []
    protected = set()
    for anchor, rows in inventories:
        if anchor.exact_roster and current_roster(repo, anchor.path) != set(rows):
            raise HistoryViolation(f"historical file roster changed: {anchor.path}")
        bound = {}
        for relative, (mode, oid) in rows.items():
            observed = file_digest(regular_file(repo, relative, mode))
            if observed != hashes[oid]:
                raise HistoryViolation(f"historical byte mismatch: {relative}; trusted={hashes[oid]}, actual={observed}")
            bound[relative] = observed
            protected.add(relative)
        receipts.append({"commit": anchor.commit, "path": anchor.path, "exact_roster": anchor.exact_roster,
                         "files": len(rows), "files_sha256": digest(canonical(bound))})
    mode, oid = ledger_entry[ledger_path]
    original = git(repo, "cat-file", "blob", oid)
    if digest(original) != hashes[oid]:
        raise HistoryViolation("historical ledger object changed during verification")
    current = regular_file(repo, ledger_path, mode).read_bytes()
    previous_rows, present_rows = ledger_rows(original), ledger_rows(current)
    # The canonical regenerator sorts bundles: new records can interleave. Keep
    # every old row byte-exact and in its old relative order, rather than require
    # the whole old file to remain a byte prefix of the regenerated registry.
    old_ids = {row["run_id"] for row in previous_rows}
    preserved = [(row["run_id"], line) for row, line in zip(present_rows, current.splitlines())
                 if row["run_id"] in old_ids]
    expected = [(row["run_id"], line) for row, line in zip(previous_rows, original.splitlines())]
    if preserved != expected:
        raise HistoryViolation("historical ledger was deleted, rewritten or reordered")
    if git(repo, "rev-parse", "HEAD").decode().strip() != head:
        raise HistoryViolation("HEAD changed during history verification")
    return {"schema": "cneh-history-guard-v1", "status": "PASS", "head_sha": head,
            "anchors": receipts, "protected_files": len(protected),
            "ledger": {"commit": ledger_commit, "path": ledger_path, "historical_rows": len(previous_rows),
                       "current_rows": len(present_rows), "appended_rows": len(present_rows) - len(previous_rows),
                       "historical_sha256": digest(original), "current_sha256": digest(current),
                       "preservation_rule": "EXACT_OLD_ROWS_AND_RELATIVE_ORDER; NEW_ROWS_MAY_INTERLEAVE"},
            "guard_sha256": digest(Path(__file__).read_bytes()), "scientific_promotion_authorized": False,
            "independent_replication": "NOT_TESTED"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        report = verify_history(args.repo)
    except (HistoryViolation, OSError, ValueError) as error:
        print(json.dumps({"schema": "cneh-history-guard-v1", "status": "FAIL", "error": str(error),
                          "scientific_promotion_authorized": False, "independent_replication": "NOT_TESTED"}))
        return 1
    print(canonical(report).decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
