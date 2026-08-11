"""Git first-add temporal gate for REAL-TRANSFER-01.

This is a pre-execution governance gate.  It proves only that the frozen parent
preregistration and both disclosed pre-execution amendments entered Git before the
benchmark implementation.  It does not promote scientific authority and it does not
substitute for source/model/result provenance.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

ROOT = Path(__file__).resolve().parents[2]

STAGES: tuple[tuple[str, str], ...] = (
    ("PARENT_PREREG", "experiments/real_transfer_01/PREREGISTRATION.md"),
    ("AMENDMENT_001", "experiments/real_transfer_01/PRE_EXECUTION_AMENDMENT_001.md"),
    ("AMENDMENT_002", "experiments/real_transfer_01/PRE_EXECUTION_AMENDMENT_002.md"),
    ("IMPLEMENTATION", "experiments/real_transfer_01/contract.py"),
)


@dataclass(frozen=True, slots=True)
class Stage:
    name: str
    path: str
    first_add_commit: str

    def to_json(self) -> dict[str, str]:
        return {
            "name": self.name,
            "path": self.path,
            "first_add_commit": self.first_add_commit,
        }


def _git(*args: str, root: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=False
    )


def first_add(path: str, *, root: Path = ROOT) -> str | None:
    run = _git("log", "--diff-filter=A", "--format=%H", "--reverse", "--", path, root=root)
    if run.returncode != 0:
        return None
    commits = [line.strip() for line in run.stdout.splitlines() if line.strip()]
    return commits[0] if commits else None


def strict_ancestor(a: str, b: str, *, root: Path = ROOT) -> bool:
    if not a or not b or a == b:
        return False
    return _git("merge-base", "--is-ancestor", a, b, root=root).returncode == 0


def validate_order(
    commits: Sequence[str],
    *,
    is_strict_ancestor: Callable[[str, str], bool],
) -> tuple[bool, list[dict[str, str | bool]]]:
    if len(commits) < 2:
        return False, []
    checks: list[dict[str, str | bool]] = []
    ok = True
    for left, right in zip(commits, commits[1:]):
        passed = bool(is_strict_ancestor(left, right))
        checks.append({"earlier": left, "later": right, "strict_ancestor": passed})
        ok = ok and passed
    return ok, checks


def analyze(*, root: Path = ROOT) -> dict[str, object]:
    resolved: list[Stage] = []
    missing: list[str] = []
    for name, path in STAGES:
        commit = first_add(path, root=root)
        if commit is None:
            missing.append(path)
        else:
            resolved.append(Stage(name=name, path=path, first_add_commit=commit))

    if missing:
        return {
            "gate": "REAL_TRANSFER_01_TEMPORAL_PREEXECUTION",
            "verdict": "FAIL",
            "authority": "GOVERNANCE_ONLY_NO_SCIENTIFIC_PROMOTION",
            "missing_first_add": missing,
            "stages": [stage.to_json() for stage in resolved],
            "order_checks": [],
        }

    commits = [stage.first_add_commit for stage in resolved]
    ok, checks = validate_order(
        commits,
        is_strict_ancestor=lambda a, b: strict_ancestor(a, b, root=root),
    )
    return {
        "gate": "REAL_TRANSFER_01_TEMPORAL_PREEXECUTION",
        "verdict": "PASS" if ok else "FAIL",
        "authority": "GOVERNANCE_ONLY_NO_SCIENTIFIC_PROMOTION",
        "stages": [stage.to_json() for stage in resolved],
        "order_checks": checks,
        "scientific_status": "NOT_TESTED",
    }


def self_test() -> bool:
    rank = {"p": 0, "a1": 1, "a2": 2, "impl": 3}
    ancestor = lambda a, b: rank[a] < rank[b]
    good, _ = validate_order(["p", "a1", "a2", "impl"], is_strict_ancestor=ancestor)
    same, _ = validate_order(["p", "a1", "a1", "impl"], is_strict_ancestor=ancestor)
    swapped, _ = validate_order(["p", "a2", "a1", "impl"], is_strict_ancestor=ancestor)
    short, _ = validate_order(["p"], is_strict_ancestor=ancestor)
    reversed_all, _ = validate_order(["impl", "a2", "a1", "p"], is_strict_ancestor=ancestor)
    return good and not same and not swapped and not short and not reversed_all


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        passed = self_test()
        print(f"REAL-TRANSFER-01 TEMPORAL SELF-TEST: {'PASS 5/5' if passed else 'FAIL'}")
        return 0 if passed else 2
    result = analyze()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(
            "REAL-TRANSFER-01 TEMPORAL GATE: "
            f"{result['verdict']} scientific_status={result.get('scientific_status', 'NOT_TESTED')}"
        )
        for stage in result.get("stages", []):
            print(f"  {stage['name']}: {stage['first_add_commit']} {stage['path']}")
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
