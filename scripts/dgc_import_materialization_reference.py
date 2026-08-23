from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path

from cwc.governance.external_evidence_reference import reference_bytes, verify_materialization_generation

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_EVIDENCE_ROOT = ROOT / "eval_bundle"


def _capture(*args: str) -> str:
    proc = subprocess.run(
        args,
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return proc.stdout.strip()


def _repo_identity() -> tuple[str, str]:
    commit = _capture("git", "rev-parse", "HEAD")
    tree = _capture("git", "rev-parse", "HEAD^{tree}")
    dirty = _capture("git", "status", "--porcelain=v1", "--untracked-files=all")
    if dirty:
        raise RuntimeError("repository must be clean before importing external evidence reference")
    return commit, tree


def _runtime_output(path: Path) -> Path:
    resolved = path.resolve()
    runtime_root = RUNTIME_EVIDENCE_ROOT.resolve()
    try:
        resolved.relative_to(runtime_root)
    except ValueError as exc:
        raise ValueError("reference output must be inside ignored eval_bundle runtime root") from exc
    if resolved.exists():
        raise FileExistsError("reference output already exists; references are immutable")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify an external DGC materialization generation and mint a small repo-local subject reference."
    )
    parser.add_argument("--generation-root", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    commit, tree = _repo_identity()
    reference = verify_materialization_generation(
        Path(args.generation_root),
        expected_repository_commit=commit,
        expected_repository_tree=tree,
    )
    output = _runtime_output(Path(args.output))
    output.parent.mkdir(parents=True, exist_ok=True)
    data = reference_bytes(reference)
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        output.unlink(missing_ok=True)
        raise
    print(
        json.dumps(
            {
                "status": "PASS",
                "reference": str(output.relative_to(ROOT)),
                "reference_digest": reference.digest,
                "subject_publication_manifest_sha256": reference.publication_manifest_sha256,
                "product_promotion_authorized": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
