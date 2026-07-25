"""Fail-closed anti-green gate for tests and CI.

This gate does not prove a scientific claim. It rejects known ways a repository
can manufacture a green result without executing the intended falsification.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIN_TEST_FILES = 91
MIN_STATIC_TESTS = 609
SHA_REF = re.compile(r"^[0-9a-f]{40}$")
HARDWARE_REASON = re.compile(r"CUDA|NVML|FA3|flash-attention|driver-probe", re.IGNORECASE)


def _dotted(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _literal_reason(call: ast.Call) -> str:
    values = list(call.args)
    values.extend(k.value for k in call.keywords if k.arg == "reason")
    return " ".join(v.value for v in values if isinstance(v, ast.Constant) and isinstance(v.value, str))


def _test_errors(root: Path) -> list[str]:
    errors: list[str] = []
    paths = sorted((root / "tests").rglob("test_*.py"))
    paths += sorted(
        p for p in (root / "experiments").rglob("test_*.py")
        if ".venv" not in p.parts
    )
    static_tests = 0
    for path in paths:
        rel = path.relative_to(root)
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(rel))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                static_tests += 1
            if isinstance(node, ast.Assert) and isinstance(node.test, ast.Constant) and bool(node.test.value):
                errors.append(f"{rel}:{node.lineno}: vacuous truth assertion")
            if isinstance(node, ast.Call):
                name = _dotted(node.func)
                if name in {"pytest.xfail", "pytest.fail"} and name == "pytest.xfail":
                    errors.append(f"{rel}:{node.lineno}: xfail can convert an unknown defect into green")
                if name == "pytest.skip":
                    reason = _literal_reason(node)
                    if not HARDWARE_REASON.search(reason):
                        errors.append(f"{rel}:{node.lineno}: non-hardware skip is forbidden: {reason!r}")
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                for dec in node.decorator_list:
                    call = dec if isinstance(dec, ast.Call) else None
                    name = _dotted(call.func if call else dec)
                    if name.endswith(".xfail"):
                        errors.append(f"{rel}:{getattr(dec, 'lineno', 0)}: xfail decorator is forbidden")
                    if name.endswith((".skip", ".skipif")):
                        reason = _literal_reason(call) if call else ""
                        if not HARDWARE_REASON.search(reason):
                            errors.append(
                                f"{rel}:{getattr(dec, 'lineno', 0)}: "
                                f"non-hardware skip decorator is forbidden: {reason!r}"
                            )
    if len(paths) < MIN_TEST_FILES:
        errors.append(f"test file floor violated: {len(paths)} < {MIN_TEST_FILES}")
    if static_tests < MIN_STATIC_TESTS:
        errors.append(f"static test floor violated: {static_tests} < {MIN_STATIC_TESTS}")
    return errors


def _workflow_errors(root: Path) -> list[str]:
    errors: list[str] = []
    workflow_dir = root / ".github/workflows"
    required = {
        "cwc-quality.yml",
        "cwc-doc-gates.yml",
        "cwc-full-pr-gate.yml",
        "pr-audit.yml",
        "codeql.yml",
    }
    missing = required - {p.name for p in workflow_dir.glob("*.yml")}
    errors.extend(f"required workflow missing: {name}" for name in sorted(missing))
    for path in sorted(workflow_dir.glob("*.yml")):
        rel = path.relative_to(root)
        text = path.read_text(encoding="utf-8")
        for match in re.finditer(r"(?m)^\\s*-?\\s*uses:\\s*([^@\\s]+)@([^\\s#]+)", text):
            action, ref = match.groups()
            if not SHA_REF.fullmatch(ref):
                errors.append(f"{rel}: mutable action ref {action}@{ref}; pin a 40-char commit")
        for image in ("rhysd/actionlint:", "zricethezav/gitleaks:"):
            for line_no, line in enumerate(text.splitlines(), start=1):
                if image in line and "@sha256:" not in line:
                    errors.append(f"{rel}:{line_no}: mutable Docker image {image}")
        for forbidden in ("continue-on-error: true", "|| true", "--skip-checksum-verify"):
            if forbidden in text:
                errors.append(f"{rel}: fail-open workflow token is forbidden: {forbidden}")
        if "timeout-minutes:" not in text:
            errors.append(f"{rel}: every workflow must bound job runtime")

    gitlab_path = root / ".gitlab-ci.yml"
    if not gitlab_path.is_file():
        errors.append("required workflow missing: .gitlab-ci.yml")
    else:
        text = gitlab_path.read_text(encoding="utf-8")
        for line_no, line in enumerate(text.splitlines(), start=1):
            if re.search(r"^\s*name:\s+\S+", line) and "image" not in line and "@sha256:" not in line:
                errors.append(f".gitlab-ci.yml:{line_no}: mutable container image")
        for forbidden in ("allow_failure: true", "|| true", "--skip-checksum-verify"):
            if forbidden in text:
                errors.append(f".gitlab-ci.yml: fail-open token is forbidden: {forbidden}")
        for job in (
            "truth-gate:",
            "workflow-audit:",
            "secret-audit:",
            "dependency-audit:",
            "engineering-assurance:",
            "quality:",
            "evidence-and-docs:",
            "fractal-verification:",
            "full-verification:",
        ):
            if job not in text:
                errors.append(f".gitlab-ci.yml: mandatory job missing: {job}")
    return errors


def _contract_errors(root: Path) -> list[str]:
    errors: list[str] = []
    makefile = (root / "Makefile.cwc").read_text(encoding="utf-8")
    workflow = (root / ".github/workflows/cwc-full-pr-gate.yml").read_text(encoding="utf-8")
    gitlab = (root / ".gitlab-ci.yml").read_text(encoding="utf-8")
    for token in (
        "verify-full:",
        "pr-full: verify-full pr-security",
        "truth-gate:",
        "engineering-assurance:",
        "pr-security: truth-gate workflow-lint secret-scan dependency-audit engineering-assurance",
    ):
        if token not in makefile:
            errors.append(f"Makefile contract missing: {token}")
    required_assurance = (
        "engineering/architecture_contract.json",
        "engineering/hermeticity_contract.json",
        "engineering/complexity_budgets.json",
        "docs/security/SBOM.cdx.json",
        "scripts/architecture_gate.py",
        "scripts/hermeticity_gate.py",
        "scripts/complexity_gate.py",
        "scripts/build_sbom.py",
        "scripts/assurance_attack.py",
        "scripts/assurance_report.py",
        "scripts/inference_integrity_gate.py",
        "nanochat/inference_contracts.py",
        "nanochat/model_integrity.py",
        "engineering/inference_integrity_contract.json",
        "tests/test_inference_integrity.py",
    )
    for rel in required_assurance:
        if not (root / rel).is_file():
            errors.append(f"engineering assurance component missing: {rel}")
    if "make -f Makefile.cwc pr-full" not in workflow:
        errors.append("full PR workflow does not invoke the canonical pr-full target")
    if "fractal-verification:" not in workflow:
        errors.append("full PR workflow omits the separate Python 3.11 fractal gate")
    if "make -f Makefile.cwc COVERAGE_FAIL_UNDER=91 verify-full" not in gitlab:
        errors.append("GitLab full verification must invoke verify-full with the locked CPU coverage floor")
    if "COVERAGE_FAIL_UNDER ?= 95" not in makefile:
        errors.append("canonical coverage floor must remain 95")
    return errors


def validate(root: Path = ROOT) -> list[str]:
    return _test_errors(root) + _workflow_errors(root) + _contract_errors(root)


def main() -> int:
    errors = validate()
    if errors:
        for error in errors:
            print(f"TRUTH-GATE-FAIL: {error}")
        print(f"TRUTH-GATE: FAIL ({len(errors)} anti-green violations)")
        return 1
    print(
        "TRUTH-GATE: PASS "
        f"(>= {MIN_TEST_FILES} test files, >= {MIN_STATIC_TESTS} static tests, "
        "no unapproved skips/xfails/vacuous asserts, immutable CI refs)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
