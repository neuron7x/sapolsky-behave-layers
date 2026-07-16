"""Build clean release archives (G0): source (no .git / caches) + evidence,
each with a SHA-256, plus RELEASE_MANIFEST.json. Deterministic file order.
Usage: PYTHONPATH=. .venv/bin/python scripts/make_release.py --out /tmp/cwc-release
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE = {".git", ".venv", "__pycache__", ".pytest_cache", ".mypy_cache",
           ".ruff_cache", ".hypothesis", ".coverage"}


def _sh(cmd: str) -> str:
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=ROOT).stdout.strip()


def _clean_files(subdirs: list[str]) -> list[Path]:
    out = []
    for sub in subdirs:
        for p in sorted((ROOT / sub).rglob("*")):
            if p.is_file() and not any(part in EXCLUDE or part.endswith(".pyc") for part in p.parts):
                out.append(p)
    return out


def _tar(files: list[Path], dest: Path) -> str:
    with tarfile.open(dest, "w:gz") as tf:
        for f in files:
            tf.add(f, arcname=str(f.relative_to(ROOT)))
    return hashlib.sha256(dest.read_bytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("/tmp/cwc-release"))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    commit = _sh("git rev-parse HEAD")
    src = _clean_files(["cwc", "experiments", "scripts", "docs", "schemas", "tests",
                        "nanochat", "containers"]) + [ROOT / f for f in
                        ("Makefile.cwc", "uv.lock", "pyproject.toml", "ruff.toml", "mypy.ini",
                         "SYSTEM.md", "CITATION.cff", "claim_registry.json") if (ROOT / f).exists()]
    ev = _clean_files(["artifacts"])
    src_sha = _tar(src, args.out / f"cwc-source-{commit[:7]}.tar.gz")
    ev_sha = _tar(ev, args.out / f"cwc-evidence-{commit[:7]}.tar.gz")
    manifest = {
        "project": "Cognitive Wiring Core", "version": "1.0.0", "git_commit": commit,
        "git_tree": _sh("git rev-parse HEAD^{tree}"),
        "upstream_commit": _sh("git rev-parse master"),
        "source_archive_sha256": src_sha, "evidence_archive_sha256": ev_sha,
        "source_files": len(src), "evidence_files": len(ev),
        "supported_claims": ["CWC-L0-measurement", "CWC-L1-identifiability",
                             "CWC-L2-routing-causality (NARROWED)", "CWC-L2p-jensen-gap"],
        "prohibited_claims": ["autonomous adaptive routing", "compute-equivalent Pareto",
                              "general adaptive intelligence", "energy efficiency"],
    }
    (args.out / "RELEASE_MANIFEST.json").write_text(json.dumps(manifest, indent=2))
    sums = "\n".join(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}"
                     for p in sorted(args.out.glob("*")) if p.name != "SHA256SUMS")
    (args.out / "SHA256SUMS").write_text(sums + "\n")
    print(f"release: {args.out} | source {len(src)} files sha {src_sha[:12]} "
          f"| evidence {len(ev)} files sha {ev_sha[:12]}")


if __name__ == "__main__":
    main()
