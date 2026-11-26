"""Build source and evidence archives from the same clean Git commit."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from hashlib import file_digest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_COMMIT = "92d63d4e8bb4df75c3b71618f31ddde2378b2bcd"


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], cwd=ROOT)


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return file_digest(stream, "sha256").hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("/tmp/cwc-release"))
    args = parser.parse_args()
    commit = git("rev-parse", "HEAD").decode("ascii").strip()
    if git("status", "--porcelain", "--untracked-files=no").strip():
        parser.error("release snapshot requires a clean tracked checkout")
    tree = git("rev-parse", f"{commit}^{{tree}}").decode("ascii").strip()
    claims = json.loads(git("show", f"{commit}:claim_registry.json"))["claims"]
    entries = git("ls-tree", "-r", "-z", "--name-only", commit).split(b"\0")[:-1]
    evidence_count = sum(path.startswith(b"artifacts/") for path in entries)
    names = f"cwc-source-{commit[:7]}.tar.gz", f"cwc-evidence-{commit[:7]}.tar.gz"
    out = args.out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and (not out.is_dir() or any(out.iterdir())):
        parser.error("release output must be a new or empty directory")
    with TemporaryDirectory(prefix=".cwc-release-", dir=out.parent) as tmp:
        stage = Path(tmp)
        scopes = ((".", ":(exclude)artifacts"), ("artifacts",))
        for name, paths in zip(names, scopes, strict=True):
            git("-c", "tar.umask=0022", "archive", "--format=tar.gz",
                f"--output={stage / name}", commit, "--", *paths)
        hashes = {name: sha256(stage / name) for name in names}
        manifest = {
            "project": "Cognitive Wiring Core", "version": f"snapshot-{commit[:12]}",
            "git_commit": commit, "git_tree": tree, "upstream_commit": UPSTREAM_COMMIT,
            "source_archive_sha256": hashes[names[0]], "evidence_archive_sha256": hashes[names[1]],
            "source_files": len(entries) - evidence_count, "evidence_files": evidence_count,
            "supported_claims": sorted(c["claim_id"] for c in claims if c["status"] == "SUPPORTED"),
            "narrowed_claims": sorted(c["claim_id"] for c in claims if c["status"] == "SUPPORTED_NARROWED"),
            "prohibited_claims": sorted({v for c in claims for v in c.get("prohibited_extrapolations", [])}),
        }
        manifest_path = stage / "RELEASE_MANIFEST.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        hashes[manifest_path.name] = sha256(manifest_path)
        (stage / "SHA256SUMS").write_text(
            "".join(f"{digest}  {name}\n" for name, digest in sorted(hashes.items())), encoding="ascii",
        )
        os.replace(stage, out)
    print(f"RELEASE SNAPSHOT: {commit} {tree} ({len(entries)} tracked files)")


if __name__ == "__main__":
    main()
