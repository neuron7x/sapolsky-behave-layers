"""Canonical dual-sided admission gate, including critic and fresh-process replay."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast

from cwc.governance.planner_admission import critic_planner_document, verify_planner_document
from cwc.governance.verifier_qualification import (
    Action,
    ArtifactQuality,
    Category,
    VerificationDecision,
    VerifierFixture,
    canonical_bytes,
    digest,
    qualify_verifier,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/dual_sided_planner.json"
FIXTURE_SHA256 = "6e1b90074632ca2e31adea51df56ea686847201c56440406c6024a19e431c261"


def load_fixtures() -> tuple[VerifierFixture, ...]:
    if FIXTURES.is_symlink():
        raise ValueError("fixture symlink rejected")
    raw = FIXTURES.read_bytes()
    if digest(raw) != FIXTURE_SHA256:
        raise ValueError("frozen fixture bytes changed; review the oracle and fixture pin explicitly")
    doc = json.loads(raw)
    if doc["schema"] != "CWC_FROZEN_PLANNER_FIXTURES_V1":
        raise ValueError("unknown fixture schema")
    return tuple(
        VerifierFixture(
            row["fixture_id"],
            cast(Category, row["category"]),
            row["payload"].encode("utf-8"),
            VerificationDecision(
                cast(ArtifactQuality, row["expected"]["artifact_quality"]),
                cast(Action, row["expected"]["action"]),
                row["expected"]["selected_action"],
            ),
        )
        for row in doc["fixtures"]
    )


def mutation_controls(fixtures: tuple[VerifierFixture, ...]) -> dict[str, bool]:
    def promoted(raw: bytes) -> VerificationDecision:
        result = verify_planner_document(raw)
        return VerificationDecision("PASS", "SUBMIT", "A") if result.action == "ESCALATE" else result

    def crashed(_: bytes) -> VerificationDecision:
        raise RuntimeError("deliberate verifier crash")

    mutants: dict[str, Callable[[bytes], VerificationDecision]] = {
        "reject_all": lambda _: VerificationDecision("FAIL", "STOP"),
        "accept_all": lambda _: VerificationDecision("PASS", "SUBMIT", "A"),
        "contradiction_to_submit": promoted,
        "crashed_verifier": crashed,
    }
    return {
        name: qualify_verifier(mutant, critic_planner_document, fixtures)["verdict"] == "FAIL"
        for name, mutant in mutants.items()
    }


def worker_report() -> dict[str, object]:
    fixtures = load_fixtures()
    report = qualify_verifier(verify_planner_document, critic_planner_document, fixtures)
    controls = mutation_controls(fixtures)
    return {
        "qualification": report,
        "mutation_controls": controls,
        "verdict": "PASS" if report["verdict"] == "PASS" and all(controls.values()) else "FAIL",
    }


def source_identity() -> dict[str, object]:
    paths = sorted(
        {
            *(p.relative_to(ROOT).as_posix() for p in (ROOT / "cwc").rglob("*.py")),
            "scripts/dual_sided_verifier_gate.py",
            "tests/test_dual_sided_verifier.py",
            "tests/fixtures/dual_sided_planner.json",
            "Makefile.cwc",
            "pyproject.toml",
            "cwc-requirements-dev.txt",
        }
    )
    manifest = []
    for rel in paths:
        path = ROOT / rel
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"source must be a regular file: {rel}")
        raw = path.read_bytes()
        manifest.append({"path": rel, "bytes": len(raw), "sha256": digest(raw)})

    def git(*args: str) -> str:
        return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True, timeout=10).strip()

    return {
        "source_commit": git("rev-parse", "HEAD"),
        "source_tree": git("rev-parse", "HEAD^{tree}"),
        "tracked_worktree_dirty": bool(git("status", "--porcelain", "--untracked-files=no")),
        "manifest": manifest,
        "worktree_content_sha256": digest(canonical_bytes(manifest)),
    }


def replay_report() -> dict[str, object]:
    before = source_identity()
    reports = []
    for seed in ("1", "947"):
        env = dict(os.environ, PYTHONHASHSEED=seed, PYTHONPATH=str(ROOT))
        result = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--worker"],
            cwd=ROOT,
            env=env,
            capture_output=True,
            check=False,
            timeout=45,
        )
        if result.returncode != 0 or result.stderr:
            raise RuntimeError(f"worker failed, exit={result.returncode}; no replay evidence accepted")
        reports.append(json.loads(result.stdout))
    after = source_identity()
    if before != after:
        raise RuntimeError("source bytes or Git identity changed during replay")
    matched = canonical_bytes(reports[0]) == canonical_bytes(reports[1])
    payload: dict[str, object] = {
        "schema": "CWC_DUAL_SIDED_VERIFIER_REPLAY_V1",
        "source": before,
        "runtime": {"implementation": platform.python_implementation(), "version": platform.python_version()},
        "replay": {"process_count": 2, "python_hash_seeds": ["1", "947"], "matched": matched},
        "worker": reports[0],
        "product_qualified": False,
        "verdict": "PASS" if matched and all(r["verdict"] == "PASS" for r in reports) else "FAIL",
    }
    return {**payload, "evidence_sha256": digest(canonical_bytes(payload))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--output-dir", type=Path, help="write a content-addressed receipt, never overwrite evidence")
    args = parser.parse_args()
    try:
        if args.worker:
            report = worker_report()
            print(canonical_bytes(report).decode("utf-8"))
        else:
            report = replay_report()
            if args.output_dir:
                args.output_dir.mkdir(parents=True, exist_ok=True)
                target = args.output_dir / f"{report['evidence_sha256']}.json"
                raw = canonical_bytes(report) + b"\n"
                if target.exists():
                    if target.is_symlink() or target.read_bytes() != raw:
                        raise ValueError("immutable evidence collision")
                else:
                    with target.open("xb") as handle:
                        handle.write(raw)
                print(f"DUAL-SIDED-VERIFIER-RECEIPT: {target}")
            print(f"DUAL-SIDED-VERIFIER: {report['verdict']}")
            print(f"DUAL-SIDED-VERIFIER-EVIDENCE-SHA256: {report['evidence_sha256']}")
        return 0 if report["verdict"] == "PASS" else 1
    except (OSError, ValueError, TypeError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"DUAL-SIDED-VERIFIER: FAIL ({type(exc).__name__}: {exc})", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
