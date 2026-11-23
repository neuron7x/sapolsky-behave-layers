"""Independent A6 export roundtrip; reads source, writes only a fresh output path."""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess

OLD = "5d579a20a16700ae0cbec9daf8640edecf8603f3"
ROOT = "artifacts/cneh-exp-01-a3"
NESTED = ROOT + "/wheel-bytecheck/pre-final-v2"
MAP = {
    ROOT + "/SHA256SUMS": ROOT + "/PROVENANCE_ORIGINAL_SHA256SUMS_5d579a2.txt",
    NESTED + "/SHA256SUMS": NESTED + "/PROVENANCE_ORIGINAL_SHA256SUMS_5d579a2.txt",
    NESTED + "/negative-member/module.py": NESTED + "/negative-member/module.bin",
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--head", required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    out = args.out.resolve()
    if out == repo or repo in out.parents:
        raise ValueError("output must be outside source checkout")
    def git(*arguments):
        return subprocess.check_output(["git", "--no-replace-objects", "-C", str(repo), *arguments])
    if git("rev-parse", "HEAD").decode().strip() != args.head or git("status", "--porcelain"):
        raise ValueError("expected clean exact source head")
    out.mkdir(parents=True, exist_ok=False)
    inventory = []
    for entry in git("ls-tree", "-r", "-z", OLD, "--", ROOT).split(b"\0"):
        if not entry:
            continue
        metadata, encoded_path = entry.split(b"\t", 1)
        mode, kind, oid = metadata.decode().split()
        relative = encoded_path.decode()
        if kind != "blob" or mode not in ("100644", "100755"):
            raise ValueError("unsupported original object type")
        source = repo / MAP.get(relative, relative)
        if source.is_symlink() or not source.is_file():
            raise ValueError("source must be a regular file")
        if bool(source.stat().st_mode & 0o111) != (mode == "100755"):
            raise ValueError("source executable mode changed: " + relative)
        current = source.read_bytes()
        original = git("cat-file", "blob", oid)
        if current != original:
            raise ValueError("roundtrip payload differs from original Git object: " + relative)
        destination = out / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(current)
        destination.chmod(0o755 if mode == "100755" else 0o644)
        inventory.append({"path": relative, "mode": mode, "sha256": hashlib.sha256(current).hexdigest()})
    if len(inventory) != 434:
        raise ValueError("unexpected original evidence inventory")
    observed = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file())
    if observed != sorted(row["path"] for row in inventory):
        raise ValueError("restored file roster mismatch")
    manifest_results = []
    for manifest in sorted(out.rglob("SHA256SUMS")):
        cwd = out if re.search(rb"^[0-9a-fA-F]{64} [ *]artifacts/", manifest.read_bytes(), re.M) else manifest.parent
        result = subprocess.run(["sha256sum", "-c", str(manifest)], cwd=cwd, capture_output=True)
        manifest_results.append({"path": manifest.relative_to(out).as_posix(), "exit_code": result.returncode})
        if result.returncode:
            raise ValueError("restored manifest failed: " + str(manifest))
    parsed = []
    for source in sorted((repo / "artifacts").rglob("*.py")):
        ast.parse(source.read_bytes(), filename=str(source))
        parsed.append(source.relative_to(repo).as_posix())
    fixture = out / (NESTED + "/negative-member/module.py")
    original_fixture = fixture.read_bytes()
    try:
        fixture.write_bytes(original_fixture + b"\n# independent roundtrip negative control\n")
        negative = subprocess.run(["sha256sum", "-c", "SHA256SUMS"], cwd=out / ROOT, capture_output=True)
        if negative.returncode == 0:
            raise ValueError("roundtrip negative control was not rejected")
    finally:
        fixture.write_bytes(original_fixture)
    if git("rev-parse", "HEAD").decode().strip() != args.head or git("status", "--porcelain"):
        raise ValueError("source changed during verification")
    result = {
        "schema": "independent-cneh-a6-roundtrip-v1", "status": "PASS", "head": args.head,
        "original_commit": OLD, "restored_files": len(inventory),
        "restored_inventory_sha256": hashlib.sha256(json.dumps(inventory, sort_keys=True).encode()).hexdigest(),
        "manifest_results": manifest_results, "negative_exit_code": negative.returncode,
        "current_python_artifacts_parsed": len(parsed), "source_status_after": "clean",
        "reconstructed_directory": str(out), "mapping": MAP,
        "verifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    os.umask(0o022)
    main()
