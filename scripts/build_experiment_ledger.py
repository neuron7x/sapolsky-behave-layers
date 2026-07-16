"""Generate docs/lab/EXPERIMENT_LEDGER.jsonl from the REAL evidence bundles on disk
(one record per artifacts/*/ that carries a verdict.json + SHA256SUMS). The ledger is
append-only in spirit; this regenerator is idempotent and deterministic (sorted).

Run: PYTHONPATH=. .venv/bin/python scripts/build_experiment_ledger.py
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts"
OUT = ROOT / "docs/lab/EXPERIMENT_LEDGER.jsonl"


def _sha_of_sums(d: Path) -> str:
    p = d / "SHA256SUMS"
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.exists() else ""


def main() -> None:
    head = subprocess.run("git rev-parse HEAD", shell=True, cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()
    records = []
    for d in sorted(ART.rglob("verdict.json")):
        bundle = d.parent
        rel = bundle.relative_to(ROOT).as_posix()
        try:
            v = json.loads(d.read_text())
        except json.JSONDecodeError:
            v = {}
        records.append({
            "run_id": rel.replace("/", ":"),
            "artifact_path": rel,
            "verdict": v.get("verdict", v.get("status", "SEE_verdict.json")),
            "experiment": v.get("experiment", bundle.name),
            "n_seeds": v.get("n_seeds"),
            "git_commit_current": head,
            "sha256sums_hash": _sha_of_sums(bundle),
            "has_checksums": (bundle / "SHA256SUMS").exists(),
        })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    print(f"ledger: {len(records)} records -> {OUT.relative_to(ROOT)}")
    for r in records:
        print(f"  {r['artifact_path']}: {r['verdict']}")


if __name__ == "__main__":
    main()
