from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import tempfile
import zipfile
from pathlib import Path, PurePosixPath

SCHEMA = "DGC_RESEARCH_HANDOFF_V1"
BUILDER_VERSION = "1"
ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)


class HandoffError(RuntimeError):
    pass


def _run_git(root: Path, *args: str, text: bool = True) -> str | bytes:
    proc = subprocess.run(
        ["git", *args], cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
    )
    if proc.returncode != 0:
        raise HandoffError(proc.stderr.decode("utf-8", errors="replace").strip() or "git command failed")
    return proc.stdout.decode("utf-8") if text else proc.stdout


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git_identity(root: Path, ref: str) -> tuple[str, str]:
    commit = str(_run_git(root, "rev-parse", f"{ref}^{{commit}}")).strip()
    tree = str(_run_git(root, "rev-parse", f"{ref}^{{tree}}")).strip()
    return commit, tree


def _tracked_paths(root: Path, commit: str) -> list[str]:
    raw = _run_git(root, "ls-tree", "-r", "--name-only", "-z", commit, text=False)
    assert isinstance(raw, bytes)
    paths = [part.decode("utf-8") for part in raw.split(b"\0") if part]
    if not paths or len(paths) != len(set(paths)):
        raise HandoffError("tracked population is empty or contains duplicate paths")
    return sorted(paths)


def build_handoff(root: Path, output: Path, *, ref: str = "HEAD") -> dict[str, object]:
    root = root.resolve()
    commit, tree = _git_identity(root, ref)
    paths = _tracked_paths(root, commit)
    files: list[dict[str, object]] = []
    blob_cache: dict[str, bytes] = {}
    for path in paths:
        posix = PurePosixPath(path)
        if posix.is_absolute() or ".." in posix.parts:
            raise HandoffError(f"unsafe tracked path: {path}")
        blob = _run_git(root, "show", f"{commit}:{path}", text=False)
        assert isinstance(blob, bytes)
        blob_cache[path] = blob
        files.append({"path": path, "bytes": len(blob), "sha256": _sha256(blob)})

    state = {
        "schema": SCHEMA,
        "builder_version": BUILDER_VERSION,
        "git_commit": commit,
        "git_tree": tree,
        "tracked_file_count": len(files),
        "tracked_population_digest": _sha256(
            json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ),
        "files": files,
        "product_qualified": False,
        "interpretation": "Exact Git-object research handoff; not a product qualification receipt.",
    }
    metadata = json.dumps(state, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8") + b"\n"

    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix="dgc-handoff-", suffix=".zip", dir=output.parent, delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for path in paths:
                info = zipfile.ZipInfo(path, ZIP_EPOCH)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, blob_cache[path])
            info = zipfile.ZipInfo("CURRENT_HANDOFF/EXACT_SOURCE_MANIFEST.json", ZIP_EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, metadata)
        os.replace(tmp_path, output)
    finally:
        tmp_path.unlink(missing_ok=True)
    return state


def verify_handoff(path: Path) -> dict[str, object]:
    with zipfile.ZipFile(path, "r") as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise HandoffError("archive contains duplicate names")
        manifest_name = "CURRENT_HANDOFF/EXACT_SOURCE_MANIFEST.json"
        if manifest_name not in names:
            raise HandoffError("exact-source manifest missing")
        state = json.loads(archive.read(manifest_name))
        if state.get("schema") != SCHEMA:
            raise HandoffError("unsupported manifest schema")
        expected = {entry["path"]: entry for entry in state["files"]}
        actual = set(names) - {manifest_name}
        if actual != set(expected):
            raise HandoffError("archive tracked population differs from manifest")
        for name, entry in expected.items():
            blob = archive.read(name)
            if len(blob) != entry["bytes"] or _sha256(blob) != entry["sha256"]:
                raise HandoffError(f"archive blob mismatch: {name}")
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description="Build an exact, deterministic non-promoting DGC research handoff.")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ref", default="HEAD")
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    try:
        state = verify_handoff(args.output) if args.verify_only else build_handoff(args.root, args.output, ref=args.ref)
        if not args.verify_only:
            verify_handoff(args.output)
    except (HandoffError, OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        print(json.dumps({"status": "FAIL", "reason": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps({
        "status": "PASS",
        "git_commit": state["git_commit"],
        "git_tree": state["git_tree"],
        "tracked_file_count": state["tracked_file_count"],
        "tracked_population_digest": state["tracked_population_digest"],
        "product_qualified": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
