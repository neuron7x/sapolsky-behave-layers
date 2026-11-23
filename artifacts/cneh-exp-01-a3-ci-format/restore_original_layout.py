"""Restore the exact pre-migration A3 evidence layout without executing its data."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess

ORIGINAL = "5d579a20a16700ae0cbec9daf8640edecf8603f3"
PREFIX = "artifacts/cneh-exp-01-a3"
NESTED = PREFIX + "/wheel-bytecheck/pre-final-v2"
ALIASES = {
    PREFIX + "/SHA256SUMS": PREFIX + "/PROVENANCE_ORIGINAL_SHA256SUMS_5d579a2.txt",
    NESTED + "/SHA256SUMS": NESTED + "/PROVENANCE_ORIGINAL_SHA256SUMS_5d579a2.txt",
    NESTED + "/negative-member/module.py": NESTED + "/negative-member/module.bin",
}


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def safe(root: Path, relative: str) -> Path:
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("unsafe restoration path")
    result = root / path
    if result.is_symlink() or not result.is_file() or not result.resolve().is_relative_to(root):
        raise ValueError("missing or nonregular restoration source")
    if any(p.is_symlink() for p in result.parents if p != root and root in p.parents):
        raise ValueError("symlinked restoration parent")
    return result


def restore(repo: Path, out: Path) -> dict:
    repo = repo.resolve()
    out = Path(os.path.abspath(out))
    if out.is_relative_to(repo) or any(p.is_symlink() for p in (out, *out.parents)):
        raise ValueError("restoration must use a new external nonsymlink directory")
    out.mkdir(parents=True, exist_ok=False)
    rows = subprocess.check_output(["git", "ls-tree", "-r", "-z", ORIGINAL, "--", PREFIX], cwd=repo)
    inventory = {}
    sources = {}
    for row in rows.split(b"\0"):
        if not row:
            continue
        metadata, encoded = row.split(b"\t", 1)
        mode, kind, oid = metadata.decode().split()
        path = encoded.decode()
        if kind != "blob" or mode not in ("100644", "100755") or not path.startswith(PREFIX + "/"):
            raise ValueError("unexpected original Git entry")
        source = safe(repo, ALIASES.get(path, path))
        raw = source.read_bytes()
        original = subprocess.check_output(["git", "cat-file", "blob", oid], cwd=repo)
        if raw != original or bool(source.stat().st_mode & 0o111) != (mode == "100755"):
            raise ValueError("migration changed historical bytes or executable mode: " + path)
        target = out / path[len(PREFIX) + 1:]
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(raw)
        target.chmod(0o755 if mode == "100755" else 0o644)
        if not stat.S_ISREG(target.stat().st_mode) or target.read_bytes() != original:
            raise ValueError("restored file differs from trusted original")
        inventory[path] = {"git_blob_sha1": oid, "sha256": digest(raw), "mode": mode}
        sources[path] = source
    if len(inventory) != 434:
        raise ValueError("incomplete original A3 inventory")
    manifests = []
    for manifest in sorted(out.rglob("SHA256SUMS")):
        expected = {}
        for line in manifest.read_text().splitlines():
            value, name = line.split("  ", 1)
            if name in expected or digest(safe(manifest.parent, name).read_bytes()) != value:
                raise ValueError("restored manifest mismatch")
            expected[name] = value
        actual = {p.relative_to(manifest.parent).as_posix() for p in manifest.parent.rglob("*")
                  if p.is_file() and p != manifest}
        if set(expected) != actual:
            raise ValueError("restored manifest roster mismatch")
        manifests.append({"path": manifest.relative_to(out).as_posix(), "sha256": digest(manifest.read_bytes())})
    if any(digest(source.read_bytes()) != inventory[path]["sha256"] for path, source in sources.items()):
        raise ValueError("migration source changed during restoration")
    return {"schema": "cneh-a6-lossless-layout-restoration-v1", "status": "PASS",
            "original_commit": ORIGINAL, "source_head": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip(),
            "restored_files": len(inventory), "all_bytes_and_modes_match_original_git": True,
            "inventory_sha256": digest(json.dumps(inventory, sort_keys=True).encode()),
            "restored_manifests": manifests, "aliases": ALIASES,
            "scientific_promotion_authorized": False, "original_qualification": "BLOCKED_CODEQL"}


if __name__ == "__main__":
    os.umask(0o022)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    arguments = parser.parse_args()
    print(json.dumps(restore(arguments.repo, arguments.out), indent=2))
