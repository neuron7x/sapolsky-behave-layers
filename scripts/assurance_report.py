"""Emit a machine-readable, commit-bound engineering assurance report."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections.abc import Callable
from pathlib import Path

from scripts import (
    architecture_gate,
    assurance_attack,
    build_sbom,
    complexity_gate,
    dependency_integrity_gate,
    hermeticity_gate,
    inference_integrity_gate,
)

ROOT = Path(__file__).resolve().parents[1]


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def build_report(root: Path = ROOT) -> dict[str, object]:
    checks: list[tuple[str, Callable[[], list[str]]]] = [
        ("architecture", lambda: architecture_gate.validate(root)),
        ("hermeticity", lambda: hermeticity_gate.validate(root)),
        ("complexity", lambda: complexity_gate.validate(root)),
        ("dependency_integrity", lambda: dependency_integrity_gate.validate(root)),
        ("sbom", lambda: build_sbom.validate(root)),
        ("inference_integrity", lambda: inference_integrity_gate.validate(root)),
        ("assurance_attacks", assurance_attack.validate),
    ]
    results = []
    for name, check in checks:
        errors = check()
        results.append({"name": name, "status": "pass" if not errors else "fail", "errors": errors})
    lock_sha = hashlib.sha256((root / "uv.lock").read_bytes()).hexdigest()
    status = "pass" if all(item["status"] == "pass" for item in results) else "fail"
    dependency_report = dependency_integrity_gate.audit(root)
    return {
        "schema_version": 2,
        "status": status,
        "git_commit": _git(root, "rev-parse", "HEAD"),
        "git_tree": _git(root, "rev-parse", "HEAD^{tree}"),
        "uv_lock_sha256": lock_sha,
        "checks": results,
        "limitations": {
            "vulnerability_status": dependency_report.metrics["vulnerability_status"],
            "dependency_integrity_warnings": list(dependency_report.warnings),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("assurance-build/ASSURANCE_REPORT.json"))
    args = parser.parse_args()
    report = build_report()
    path = args.output if args.output.is_absolute() else ROOT / args.output
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    status = str(report["status"])
    print(f"ASSURANCE-REPORT: {status.upper()} -> {path}")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
