"""Current-tree preregistration temporal-integrity gate.

Unlike the sealed historical WP12 audit, this gate follows the *current* hypothesis
registry, resolves each claim's currently bound verdict, and verifies Git first-add
ordering for experiment-local and research-level preregistrations.

The gate is governance only: it never upgrades scientific authority. Historical
same-commit protocols are accepted only when their retrospective status was already
explicitly disclosed in the repository. A new undisclosed same-commit or any
result-before-prereg ordering fails closed.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml

ROOT = Path(__file__).resolve().parents[1]
HYPOTHESES = Path("docs/methodology/HYPOTHESIS_REGISTRY.yaml")
CLAIMS = Path("claim_registry.json")
WP12_VERDICT = Path("artifacts/wp12-prereg-integrity/verdict.json")

# WP12 cannot temporally certify itself: its preregistration and verdict first entered
# Git together. The current gate therefore treats that exact historical meta-claim as
# disclosed-but-not-preregistered, never as strict-ancestor evidence.
SELF_AUDIT_HYPOTHESIS = "H-RIGOR7"

# Historical negative whose registry points at the frozen evidence directory rather
# than an independently timestamped preregistration. It may remain a negative record,
# but it cannot count as confirmatory temporal evidence.
HISTORICAL_NEGATIVE_WITHOUT_PREREG = "H-fractal"

EXPLICIT_RETROSPECTIVE_MARKERS = (
    "retrospective protocol",
    "historical-status correction",
    "not independently timestamped evidence",
)


@dataclass(frozen=True, slots=True)
class TemporalCheck:
    hypothesis_id: str
    claim_id: str
    status: str
    preregistration_paths: tuple[str, ...]
    verdict_path: str | None
    prereg_commit: str | None
    result_commit: str | None
    classification: str
    disclosed: bool
    ok: bool
    reason: str

    def to_json(self) -> dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "claim_id": self.claim_id,
            "status": self.status,
            "preregistration_paths": list(self.preregistration_paths),
            "verdict_path": self.verdict_path,
            "prereg_commit": self.prereg_commit,
            "result_commit": self.result_commit,
            "classification": self.classification,
            "disclosed": self.disclosed,
            "ok": self.ok,
            "reason": self.reason,
        }


def _git(*args: str, root: Path = ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=root, text=True, capture_output=True, check=False
    )


def _first_add(path: str, *, root: Path = ROOT) -> str | None:
    run = _git("log", "--diff-filter=A", "--format=%H", "--reverse", "--", path, root=root)
    commits = [line.strip() for line in run.stdout.splitlines() if line.strip()]
    return commits[0] if commits else None


def _is_strict_ancestor(a: str, b: str, *, root: Path = ROOT) -> bool:
    if a == b:
        return False
    return _git("merge-base", "--is-ancestor", a, b, root=root).returncode == 0


def _earliest(commits: Iterable[str], *, root: Path = ROOT) -> str:
    values = list(commits)
    if not values:
        raise ValueError("at least one commit required")
    best = values[0]
    for candidate in values[1:]:
        if _is_strict_ancestor(candidate, best, root=root):
            best = candidate
    return best


def _split_paths(value: Any) -> tuple[str, ...]:
    if not isinstance(value, str):
        return ()
    return tuple(part.strip() for part in value.split(";") if part.strip())


def _load(root: Path) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]], set[str]]:
    hypotheses_payload = yaml.safe_load((root / HYPOTHESES).read_text(encoding="utf-8"))
    hypotheses = list(hypotheses_payload.get("hypotheses", []))
    claims_payload = json.loads((root / CLAIMS).read_text(encoding="utf-8"))
    claims = {item["claim_id"]: item for item in claims_payload.get("claims", [])}
    wp12 = json.loads((root / WP12_VERDICT).read_text(encoding="utf-8"))
    disclosed_dirs = set(map(str, wp12.get("retrospective_allowlist", [])))
    return hypotheses, claims, disclosed_dirs


def _has_explicit_retrospective_marker(paths: tuple[str, ...], *, root: Path) -> bool:
    for rel in paths:
        path = root / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace").lower()
        if any(marker in text for marker in EXPLICIT_RETROSPECTIVE_MARKERS):
            return True
    return False


def _wp12_discloses(paths: tuple[str, ...], disclosed_dirs: set[str]) -> bool:
    for rel in paths:
        parts = Path(rel).parts
        if len(parts) >= 2 and parts[0] == "experiments" and parts[1] in disclosed_dirs:
            return True
    return False


def _decision(classification: str, *, disclosed: bool, status: str) -> tuple[bool, str]:
    if classification == "STRICT_ANCESTOR":
        return True, "preregistration first-add is a strict ancestor of bound verdict first-add"
    if classification == "NOT_TESTED":
        return True, "claim has no scientific verdict by design"
    if classification == "SAME_COMMIT_RETROSPECTIVE" and disclosed:
        return True, "same-commit protocol is explicitly disclosed as retrospective"
    if classification == "NO_INDEPENDENT_PREREG" and disclosed and status == "NOT_SUPPORTED":
        return True, "historical negative retained without pretending independent preregistration"
    if classification == "SELF_AUDIT_SAME_COMMIT" and disclosed:
        return True, "historical preregistration audit cannot temporally certify itself"
    return False, "temporal preregistration integrity not established"


def analyze(root: Path = ROOT) -> dict[str, Any]:
    root = root.resolve()
    hypotheses, claims, wp12_disclosed_dirs = _load(root)
    checks: list[TemporalCheck] = []

    for hypothesis in hypotheses:
        hid = str(hypothesis.get("hypothesis_id", ""))
        cid = str(hypothesis.get("claim_id", ""))
        status = str(hypothesis.get("status", ""))
        prereg_paths = _split_paths(hypothesis.get("preregistration"))
        claim = claims.get(cid)
        if claim is None:
            ok, reason = _decision("MISSING_CLAIM", disclosed=False, status=status)
            checks.append(TemporalCheck(hid, cid, status, prereg_paths, None, None, None,
                                        "MISSING_CLAIM", False, ok, reason))
            continue

        binding = claim.get("verdict_binding") or {}
        verdict_path = binding.get("file") if isinstance(binding, dict) else None
        if status == "NOT_TESTED":
            classification = "NOT_TESTED" if not verdict_path else "NOT_TESTED_HAS_VERDICT"
            ok, reason = _decision(classification, disclosed=False, status=status)
            checks.append(TemporalCheck(hid, cid, status, prereg_paths, verdict_path, None, None,
                                        classification, False, ok, reason))
            continue

        if not verdict_path:
            ok, reason = _decision("MISSING_VERDICT_BINDING", disclosed=False, status=status)
            checks.append(TemporalCheck(hid, cid, status, prereg_paths, None, None, None,
                                        "MISSING_VERDICT_BINDING", False, ok, reason))
            continue

        result_commit = _first_add(str(verdict_path), root=root)
        if not result_commit:
            ok, reason = _decision("VERDICT_NOT_IN_GIT", disclosed=False, status=status)
            checks.append(TemporalCheck(hid, cid, status, prereg_paths, str(verdict_path), None, None,
                                        "VERDICT_NOT_IN_GIT", False, ok, reason))
            continue

        # A directory is evidence, not a temporal preregistration document.
        if hid == HISTORICAL_NEGATIVE_WITHOUT_PREREG:
            classification = "NO_INDEPENDENT_PREREG"
            disclosed = True
            ok, reason = _decision(classification, disclosed=disclosed, status=status)
            checks.append(TemporalCheck(hid, cid, status, prereg_paths, str(verdict_path), None,
                                        result_commit, classification, disclosed, ok, reason))
            continue

        prereg_commits: list[str] = []
        missing_prereg_paths: list[str] = []
        for rel in prereg_paths:
            path = root / rel
            if rel == "PENDING" or not path.is_file():
                missing_prereg_paths.append(rel)
                continue
            commit = _first_add(rel, root=root)
            if commit:
                prereg_commits.append(commit)
            else:
                missing_prereg_paths.append(rel)

        if missing_prereg_paths or not prereg_commits:
            classification = "PREREG_NOT_IN_GIT"
            disclosed = False
            ok, reason = _decision(classification, disclosed=disclosed, status=status)
            checks.append(TemporalCheck(hid, cid, status, prereg_paths, str(verdict_path), None,
                                        result_commit, classification, disclosed, ok,
                                        reason + f"; unresolved={missing_prereg_paths}"))
            continue

        prereg_commit = _earliest(prereg_commits, root=root)
        if _is_strict_ancestor(prereg_commit, result_commit, root=root):
            classification = "STRICT_ANCESTOR"
            disclosed = False
        elif prereg_commit == result_commit:
            if hid == SELF_AUDIT_HYPOTHESIS:
                classification = "SELF_AUDIT_SAME_COMMIT"
                disclosed = True
            else:
                classification = "SAME_COMMIT_RETROSPECTIVE"
                disclosed = (
                    _has_explicit_retrospective_marker(prereg_paths, root=root)
                    or _wp12_discloses(prereg_paths, wp12_disclosed_dirs)
                )
        elif _is_strict_ancestor(result_commit, prereg_commit, root=root):
            classification = "RESULT_BEFORE_PREREG"
            disclosed = False
        else:
            classification = "DIVERGED_HISTORY"
            disclosed = False

        ok, reason = _decision(classification, disclosed=disclosed, status=status)
        checks.append(TemporalCheck(hid, cid, status, prereg_paths, str(verdict_path), prereg_commit,
                                    result_commit, classification, disclosed, ok, reason))

    counts: dict[str, int] = {}
    for check in checks:
        counts[check.classification] = counts.get(check.classification, 0) + 1
    failures = [check for check in checks if not check.ok]
    return {
        "gate": "CURRENT_PREREG_TEMPORAL_INTEGRITY",
        "verdict": "PASS" if not failures else "FAIL",
        "hypothesis_count": len(checks),
        "classification_counts": dict(sorted(counts.items())),
        "failure_count": len(failures),
        "checks": [check.to_json() for check in checks],
        "authority": "GOVERNANCE_ONLY_NO_SCIENTIFIC_PROMOTION",
    }


def self_test() -> bool:
    cases = [
        ("STRICT_ANCESTOR", False, "SUPPORTED", True),
        ("SAME_COMMIT_RETROSPECTIVE", True, "SUPPORTED", True),
        ("SAME_COMMIT_RETROSPECTIVE", False, "SUPPORTED", False),
        ("RESULT_BEFORE_PREREG", True, "SUPPORTED", False),
        ("NO_INDEPENDENT_PREREG", True, "NOT_SUPPORTED", True),
        ("NO_INDEPENDENT_PREREG", True, "SUPPORTED", False),
        ("NOT_TESTED", False, "NOT_TESTED", True),
        ("SELF_AUDIT_SAME_COMMIT", True, "SUPPORTED", True),
    ]
    return all(_decision(cls, disclosed=disc, status=status)[0] is expected
               for cls, disc, status, expected in cases)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        if not self_test():
            print("CURRENT-PREREG-GATE SELF-TEST: FAIL")
            return 2
        print("CURRENT-PREREG-GATE SELF-TEST: PASS 8/8 decision mutations")
        return 0
    result = analyze()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        counts = " ".join(f"{k}={v}" for k, v in result["classification_counts"].items())
        print(f"CURRENT-PREREG-GATE: {result['verdict']} hypotheses={result['hypothesis_count']} {counts}")
        if result["failure_count"]:
            for check in result["checks"]:
                if not check["ok"]:
                    print(f"  FAIL {check['hypothesis_id']}: {check['classification']} — {check['reason']}")
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
