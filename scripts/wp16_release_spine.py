"""WP16 clean-room release & reproduction spine (Act CWC-ASCEND-2026-01, G0/G1).

Regenerates the release provenance artifacts at the CURRENT commit, entirely machine-derived
from real state -- no hand-maintained claim lists or package lists (those drift; the audit's
'advertised rigor > enforced rigor' + fractal hardcoded-list defect). Sources of truth:
  * git                 -> commit, tree, upstream (master merge-base)
  * claim_registry.json -> supported/narrowed/not_supported/not_tested claim lists + counts
  * uv.lock             -> full transitive dependency closure (name+version) for the SBOM
  * artifacts/**        -> evidence bundle count (SHA256SUMS closures)

Writes: RELEASE_MANIFEST.json, SBOM.spdx.json, and re-stamps CITATION.cff version/date.
Deterministic given (commit, registry, lock). Usage:
  PYTHONPATH=. python scripts/wp16_release_spine.py [--date YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

# Best-effort SPDX license map for the direct runtime set; transitive deps carry NOASSERTION
# (the authoritative, hash-pinned closure is uv.lock -- the SBOM points there for full detail).
_LICENSE = {
    "torch": "BSD-3-Clause", "numpy": "BSD-3-Clause", "tiktoken": "MIT", "pyarrow": "Apache-2.0",
    "psutil": "BSD-3-Clause", "filelock": "Unlicense", "wandb": "MIT", "rustbpe": "MIT",
    "kernels": "Apache-2.0", "python": "PSF-2.0",
}


def _sh(cmd: str) -> str:
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=ROOT).stdout.strip()


def _lock_packages() -> list[dict[str, str]]:
    """Parse uv.lock [[package]] blocks -> [{name, version}], sorted. Regex, no toml dep (py3.10)."""
    text = (ROOT / "uv.lock").read_text(encoding="utf-8")
    pkgs = []
    for block in text.split("[[package]]")[1:]:
        head = block.split("[[")[0]
        nm = re.search(r'^\s*name\s*=\s*"([^"]+)"', head, re.MULTILINE)
        vs = re.search(r'^\s*version\s*=\s*"([^"]+)"', head, re.MULTILINE)
        if nm and vs:
            pkgs.append({"name": nm.group(1), "version": vs.group(1)})
    return sorted(pkgs, key=lambda p: p["name"])


def _claims() -> dict[str, list[str]]:
    reg = json.loads((ROOT / "claim_registry.json").read_text())
    buckets: dict[str, list[str]] = {"SUPPORTED": [], "SUPPORTED_NARROWED": [],
                                     "NOT_SUPPORTED": [], "NOT_TESTED": []}
    for c in reg["claims"]:
        buckets.setdefault(c["status"], []).append(c["claim_id"])
    return {k: sorted(v) for k, v in buckets.items()}


def _evidence_bundles() -> int:
    return len(list((ROOT / "artifacts").rglob("SHA256SUMS")))


def build_manifest() -> dict[str, Any]:
    claims = _claims()
    commit = _sh("git rev-parse HEAD")
    return {
        "project": "Cognitive Wiring Core",
        "act": "CWC-ASCEND-2026-01 / WP16 clean-room release spine",
        "version": f"1.1.0-{commit[:7]}",
        "git_commit": commit,
        "git_tree": _sh("git rev-parse HEAD^{tree}"),
        "git_branch": _sh("git rev-parse --abbrev-ref HEAD"),
        "upstream_commit": _sh("git rev-parse master 2>/dev/null") or "unknown",
        "generated_from": ["git", "claim_registry.json", "uv.lock", "artifacts/**/SHA256SUMS"],
        "note": "Machine-derived at the current commit; claim lists come from claim_registry.json "
                "(not hand-maintained) and the dependency closure from uv.lock. Source+evidence "
                "archives with per-archive SHA-256 are built by scripts/make_release.py.",
        "claim_counts": {k: len(v) for k, v in claims.items()},
        "supported_claims": claims["SUPPORTED"],
        "narrowed_claims": claims["SUPPORTED_NARROWED"],
        "not_supported_claims": claims["NOT_SUPPORTED"],
        "not_tested_claims": claims["NOT_TESTED"],
        "evidence_bundles": _evidence_bundles(),
        "prohibited_claims": [
            "autonomous adaptive routing at scale", "compute-equivalent Pareto on real workloads",
            "energy efficiency", "independent replication", "deployment-ready",
            "architectural advantage at scale",
        ],
        "gate_status": {"CWC-L7-real-pareto": "NOT_TESTED (cloud-blocked)",
                        "CWC-L8-replication": "NOT_TESTED (needs independent operator)"},
    }


def build_sbom() -> dict[str, Any]:
    commit = _sh("git rev-parse HEAD")
    pkgs = _lock_packages()
    py = _sh(".venv/bin/python -V 2>/dev/null").replace("Python ", "") or "3.10"
    spdx_pkgs = [{"SPDXID": "SPDXRef-Package-python", "name": "python", "versionInfo": py,
                  "licenseDeclared": "PSF-2.0"}]
    for p in pkgs:
        spdx_pkgs.append({
            "SPDXID": f"SPDXRef-Package-{re.sub(r'[^A-Za-z0-9.-]', '-', p['name'])}",
            "name": p["name"], "versionInfo": p["version"],
            "licenseDeclared": _LICENSE.get(p["name"], "NOASSERTION"),
        })
    return {
        "spdxVersion": "SPDX-2.3", "dataLicense": "CC0-1.0", "name": "cognitive-wiring-core",
        "documentNamespace": f"cwc/sbom/{commit[:7]}",
        "creationInfo": {
            "created": _sh("git show -s --format=%cI HEAD"),
            "creators": ["Tool: CWC-wp16_release_spine.py", "Person: Yaroslav Vasylenko"],
            "comment": "Machine-derived from uv.lock at HEAD. Authoritative hash-pinned closure: uv.lock.",
        },
        "packages": spdx_pkgs,
        "package_count": len(spdx_pkgs),
        "note": "Full transitive closure with content hashes lives in uv.lock (authoritative).",
    }


def restamp_citation(date: str) -> bool:
    cff = ROOT / "CITATION.cff"
    if not cff.exists():
        return False
    commit = _sh("git rev-parse HEAD")
    text = cff.read_text()
    text = re.sub(r'^version:.*$', f'version: "1.1.0-{commit[:7]}"', text, flags=re.MULTILINE)
    text = re.sub(r'^date-released:.*$', f'date-released: "{date}"', text, flags=re.MULTILINE)
    cff.write_text(text)
    return True


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=_sh("git show -s --format=%cs HEAD"))
    args = ap.parse_args()
    manifest = build_manifest()
    sbom = build_sbom()
    (ROOT / "RELEASE_MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (ROOT / "SBOM.spdx.json").write_text(json.dumps(sbom, indent=2) + "\n")
    cff = restamp_citation(args.date)
    print(f"WP16 release-spine regenerated at {manifest['git_commit'][:9]}:")
    print(f"  RELEASE_MANIFEST.json  claims={manifest['claim_counts']}  "
          f"evidence_bundles={manifest['evidence_bundles']}")
    print(f"  SBOM.spdx.json         packages={sbom['package_count']} (from uv.lock)")
    print(f"  CITATION.cff           {'re-stamped' if cff else 'ABSENT'}")


if __name__ == "__main__":
    main()
