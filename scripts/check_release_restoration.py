"""Exercise the release entry point twice and independently verify restored Git bytes."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, detail: str) -> None:
    if not condition:
        raise ValueError(detail)


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def check() -> None:
    commit = git("rev-parse", "HEAD").decode("ascii").strip()
    tree = git("rev-parse", f"{commit}^{{tree}}").decode("ascii").strip()
    expected = {}
    for raw in git("ls-tree", "-rz", commit).split(b"\0"):
        if raw:
            meta, path = raw.split(b"\t", 1)
            mode, kind, blob = meta.decode("ascii").split()
            require(kind == "blob" and mode in {"100644", "100755"}, f"unsupported snapshot mode {mode}")
            expected[path.decode("utf-8")] = (int(mode, 8) & 0o777, blob)
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        first, second, restored = root / "first", root / "second", root / "restore"
        for dest in (first, second):
            subprocess.run(
                [sys.executable, str(ROOT / "scripts/make_release.py"), "--out", str(dest)], check=True,
            )
            subprocess.run(["sha256sum", "--strict", "--check", "SHA256SUMS"], cwd=dest, check=True)
        names = {path.name for path in first.iterdir()}
        require(len(names) == 4 and names == {path.name for path in second.iterdir()}, "output roster mismatch")
        require(all(sha256(first / name) == sha256(second / name) for name in names), "build bytes diverge")
        doc = json.loads((first / "RELEASE_MANIFEST.json").read_text(encoding="utf-8"))
        require((doc["git_commit"], doc["git_tree"]) == (commit, tree), "release identity mismatch")
        restored.mkdir()
        seen: set[str] = set()
        for archive_path in sorted(first.glob("*.tar.gz")):
            with tarfile.open(archive_path, "r:gz") as archive:
                for member in archive.getmembers():
                    if member.isdir():
                        continue
                    require(member.isfile() and member.name in expected and member.name not in seen,
                            f"unexpected archive member: {member.name}")
                    require(member.name.startswith("artifacts/") == archive_path.name.startswith("cwc-evidence-"),
                            f"archive partition mismatch: {member.name}")
                    seen.add(member.name)
                archive.extractall(restored, filter="data")
        require(seen == set(expected), "release omits tracked paths")
        actual = {p.relative_to(restored).as_posix() for p in restored.rglob("*") if p.is_file()}
        require(actual == seen, "restore roster mismatch")
        for name, (mode, blob) in expected.items():
            path = restored / name
            raw = path.read_bytes()
            git_blob = hashlib.sha1(f"blob {len(raw)}\0".encode("ascii") + raw, usedforsecurity=False).hexdigest()
            require(git_blob == blob and path.stat().st_mode & 0o777 == mode, f"restore mismatch: {name}")
        dirty = root / "dirty"
        git("worktree", "add", "--detach", str(dirty), commit)
        try:
            with (dirty / "README.md").open("ab") as stream:
                stream.write(b"\n")
            rejected = subprocess.run(
                [sys.executable, str(dirty / "scripts/make_release.py"), "--out", str(root / "rejected")],
                capture_output=True, text=True, check=False,
            )
            require(rejected.returncode == 2 and "clean tracked checkout" in rejected.stderr,
                    "dirty release did not fail for the expected reason")
            require(not (root / "rejected").exists(), "dirty release produced output")
        finally:
            git("worktree", "remove", "--force", str(dirty))
    print("RELEASE NEGATIVE CONTROL PASS: dirty tracked bytes rejected with exit 2")
    print(f"RELEASE RESTORE PASS: {len(expected)} exact Git blobs and modes; two identical builds")


if __name__ == "__main__":
    check()
