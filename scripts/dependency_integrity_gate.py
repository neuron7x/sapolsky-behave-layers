"""Offline dependency-integrity gate for the frozen runtime supply chain.

This gate proves only local invariants that can be checked without a vulnerability
feed: lock/source origin, canonical-Python artifact hashes, direct dependency
presence, exact dev-tool pins, and SBOM/lock equivalence. It deliberately does
NOT claim that dependencies are free of known vulnerabilities; `dependency-audit`
remains the authoritative CVE gate.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import tempfile
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 compatibility
    import tomli as tomllib

from scripts import build_sbom

ROOT = Path(__file__).resolve().parents[1]
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
REQ_NAME = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9_.-]*)")
EXACT_REQ = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.-]*(?:\[[A-Za-z0-9_,.-]+\])?==[^\s;]+(?:\s*;\s*.+)?$"
)
PYTHON_PIN = re.compile(r"^(\d+)\.(\d+)(?:\.\d+)?$")

ALLOWED_REGISTRY_HOSTS = frozenset({"pypi.org", "download.pytorch.org"})
ALLOWED_ARTIFACT_HOSTS = frozenset({"files.pythonhosted.org", "download-r2.pytorch.org"})


@dataclass(frozen=True)
class IntegrityReport:
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    metrics: dict[str, int | str] = field(default_factory=dict)

    @property
    def passed(self) -> bool:
        return not self.errors


def _name(value: str) -> str:
    match = REQ_NAME.match(value)
    return match.group(1).lower().replace("_", "-") if match else ""


def _safe_https_host(url: str, allowed_hosts: frozenset[str]) -> tuple[bool, str]:
    parsed = urllib.parse.urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https":
        return False, f"non-HTTPS URL: {url}"
    if parsed.username or parsed.password:
        return False, f"credentials embedded in URL: {url}"
    if host not in allowed_hosts:
        return False, f"unapproved host {host or '<missing>'}: {url}"
    return True, ""


def _artifact_is_canonical_python(artifact: dict[str, Any], major: int, minor: int) -> bool:
    """Return whether an artifact is relevant to the pinned canonical interpreter.

    sdists are always relevant. Wheels are relevant if they are CPython-specific for
    the canonical version or generic Python 3 wheels. This is intentionally narrower
    than the project's declared Python range: hash debt outside the pinned interpreter
    is surfaced as a warning rather than silently promoted to canonical integrity.
    """
    url = urllib.parse.unquote(str(artifact.get("url", ""))).lower()
    if not url.endswith(".whl"):
        return True
    tag = f"cp{major}{minor}-"
    return tag in url or "-py3-" in url or "-py2.py3-" in url


def _read_toml(path: Path) -> dict[str, Any]:
    return tomllib.loads(path.read_text(encoding="utf-8"))


def audit(root: Path = ROOT) -> IntegrityReport:
    errors: list[str] = []
    warnings: list[str] = []
    metrics: dict[str, int | str] = {
        "vulnerability_status": "UNKNOWN_EXTERNAL_AUDIT_REQUIRED",
    }

    pyproject_path = root / "pyproject.toml"
    lock_path = root / "uv.lock"
    dev_path = root / "cwc-requirements-dev.txt"
    pin_path = root / ".python-version"
    for path in (pyproject_path, lock_path, dev_path, pin_path):
        if not path.is_file():
            errors.append(f"{path.relative_to(root)}: required dependency-control file missing")
    if errors:
        return IntegrityReport(tuple(errors), tuple(warnings), metrics)

    try:
        project = _read_toml(pyproject_path)
        lock = _read_toml(lock_path)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return IntegrityReport((f"dependency TOML parse failure: {exc}",), (), metrics)

    pin_text = pin_path.read_text(encoding="utf-8").strip()
    pin_match = PYTHON_PIN.fullmatch(pin_text)
    if not pin_match:
        errors.append(f".python-version: expected exact major.minor pin, got {pin_text!r}")
        canonical_python = (0, 0)
    else:
        canonical_python = (int(pin_match.group(1)), int(pin_match.group(2)))
        metrics["canonical_python"] = f"{canonical_python[0]}.{canonical_python[1]}"

    packages = lock.get("package")
    if not isinstance(packages, list) or not packages:
        errors.append("uv.lock: no package records")
        packages = []
    metrics["lock_package_records"] = len(packages)

    project_deps = project.get("project", {}).get("dependencies", [])
    if not isinstance(project_deps, list) or not project_deps:
        errors.append("pyproject.toml: project.dependencies missing/empty")
        project_deps = []
    direct_names = {_name(str(dep)) for dep in project_deps}
    if "" in direct_names:
        errors.append("pyproject.toml: unparsable direct dependency")
        direct_names.discard("")
    metrics["direct_runtime_dependencies"] = len(direct_names)

    locked_names = {
        str(pkg.get("name", "")).lower().replace("_", "-")
        for pkg in packages
        if isinstance(pkg, dict)
    }
    for name in sorted(direct_names - locked_names):
        errors.append(f"uv.lock: direct dependency missing: {name}")

    # The only exact runtime pin currently present must resolve to the same base
    # version in every locked platform variant. General range satisfiability remains
    # uv's job; this check prevents a direct exact pin from drifting in the lock.
    for dep in map(str, project_deps):
        if "==" not in dep:
            continue
        lhs, rhs = dep.split("==", 1)
        name = _name(lhs)
        expected = rhs.split(";", 1)[0].strip()
        versions = {
            str(pkg.get("version", ""))
            for pkg in packages
            if str(pkg.get("name", "")).lower().replace("_", "-") == name
        }
        if not versions:
            continue
        bad = sorted(version for version in versions if version.split("+", 1)[0] != expected)
        if bad:
            errors.append(
                f"uv.lock: exact pin {name}=={expected} has mismatched locked variants: {bad}"
            )

    registry_records = 0
    artifact_records = 0
    hashed_artifacts = 0
    canonical_artifacts = 0
    canonical_hashless: list[str] = []
    noncanonical_hashless: list[str] = []

    for pkg in packages:
        if not isinstance(pkg, dict):
            errors.append("uv.lock: non-object package record")
            continue
        name = str(pkg.get("name", "<unnamed>"))
        version = str(pkg.get("version", "<unversioned>"))
        source = pkg.get("source", {})
        if not isinstance(source, dict) or len(source) != 1:
            errors.append(f"uv.lock:{name}=={version}: source must contain exactly one source type")
            continue
        source_type, source_value = next(iter(source.items()))
        if source_type == "registry":
            registry_records += 1
            if not isinstance(source_value, str):
                errors.append(f"uv.lock:{name}=={version}: registry source is not a URL")
            else:
                ok, why = _safe_https_host(source_value, ALLOWED_REGISTRY_HOSTS)
                if not ok:
                    errors.append(f"uv.lock:{name}=={version}: {why}")
        elif source_type == "virtual":
            # Only the root project may be virtual; transitive path/VCS sources are
            # forbidden by omission from this allowlist.
            if name != str(project.get("project", {}).get("name", "")):
                errors.append(f"uv.lock:{name}=={version}: unexpected virtual dependency")
        else:
            errors.append(f"uv.lock:{name}=={version}: forbidden source type {source_type!r}")

        artifacts: list[dict[str, Any]] = []
        sdist = pkg.get("sdist")
        if isinstance(sdist, dict):
            artifacts.append(sdist)
        wheels = pkg.get("wheels", [])
        if isinstance(wheels, list):
            artifacts.extend(item for item in wheels if isinstance(item, dict))
        elif wheels is not None:
            errors.append(f"uv.lock:{name}=={version}: wheels is not a list")

        for artifact in artifacts:
            url = artifact.get("url")
            if not isinstance(url, str) or not url:
                errors.append(f"uv.lock:{name}=={version}: artifact URL missing")
                continue
            artifact_records += 1
            ok, why = _safe_https_host(url, ALLOWED_ARTIFACT_HOSTS)
            if not ok:
                errors.append(f"uv.lock:{name}=={version}: {why}")
            hash_value = artifact.get("hash", "")
            hash_ok = isinstance(hash_value, str) and SHA256.fullmatch(hash_value) is not None
            if hash_ok:
                hashed_artifacts += 1
            is_canonical = (
                canonical_python != (0, 0)
                and _artifact_is_canonical_python(artifact, *canonical_python)
            )
            if is_canonical:
                canonical_artifacts += 1
                if not hash_ok:
                    canonical_hashless.append(f"{name}=={version}:{url}")
            elif not hash_ok:
                noncanonical_hashless.append(f"{name}=={version}:{url}")

    metrics.update(
        {
            "registry_package_records": registry_records,
            "artifact_records": artifact_records,
            "hashed_artifact_records": hashed_artifacts,
            "canonical_artifact_records": canonical_artifacts,
            "canonical_hashless_artifacts": len(canonical_hashless),
            "noncanonical_hashless_artifacts": len(noncanonical_hashless),
        }
    )
    for item in canonical_hashless:
        errors.append(f"canonical artifact missing SHA-256: {item}")
    if noncanonical_hashless:
        warnings.append(
            "declared Python/platform matrix contains unhashed noncanonical artifacts: "
            f"{len(noncanonical_hashless)} (canonical {metrics.get('canonical_python', 'UNKNOWN')} remains hash-complete)"
        )

    dev_lines = [
        line.strip()
        for line in dev_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    metrics["exact_dev_requirements"] = len(dev_lines)
    for line in dev_lines:
        if not EXACT_REQ.fullmatch(line):
            errors.append(f"cwc-requirements-dev.txt: requirement is not exact-pinned: {line}")

    sbom_errors = build_sbom.validate(root)
    errors.extend(f"SBOM: {error}" for error in sbom_errors)
    metrics["sbom_components"] = len(build_sbom.build(root).get("components", [])) if not sbom_errors else 0
    metrics["uv_lock_sha256"] = hashlib.sha256(lock_path.read_bytes()).hexdigest()

    return IntegrityReport(tuple(sorted(set(errors))), tuple(sorted(set(warnings))), metrics)


def validate(root: Path = ROOT) -> list[str]:
    """Compatibility surface for engineering-assurance aggregation."""
    return list(audit(root).errors)


def _copy_controls(src: Path, dst: Path) -> None:
    for rel in (
        "pyproject.toml",
        "uv.lock",
        "cwc-requirements-dev.txt",
        ".python-version",
        "docs/security/SBOM.cdx.json",
    ):
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src / rel, target)


def run_self_test(root: Path = ROOT) -> dict[str, bool]:
    """Inject five supply-chain faults; each must make the gate fail closed."""
    attacks: dict[str, bool] = {}

    def attack(name: str, mutate) -> None:  # type: ignore[no-untyped-def]
        with tempfile.TemporaryDirectory(prefix="cwc-dep-integrity-") as tmp:
            sandbox = Path(tmp)
            _copy_controls(root, sandbox)
            mutate(sandbox)
            attacks[name] = not audit(sandbox).passed

    def bad_registry(sandbox: Path) -> None:
        path = sandbox / "uv.lock"
        text = path.read_text(encoding="utf-8")
        text = text.replace("https://pypi.org/simple", "https://evil.invalid/simple", 1)
        path.write_text(text, encoding="utf-8")

    def bad_artifact_host(sandbox: Path) -> None:
        path = sandbox / "uv.lock"
        text = path.read_text(encoding="utf-8")
        text = text.replace("https://files.pythonhosted.org/", "https://evil.invalid/", 1)
        path.write_text(text, encoding="utf-8")

    def remove_direct_dependency(sandbox: Path) -> None:
        path = sandbox / "uv.lock"
        payload = _read_toml(path)
        target = _name(str(_read_toml(sandbox / "pyproject.toml")["project"]["dependencies"][0]))
        payload["package"] = [
            pkg
            for pkg in payload["package"]
            if str(pkg.get("name", "")).lower().replace("_", "-") != target
        ]
        # tomllib has no writer; remove the first full package table textually.
        original = path.read_text(encoding="utf-8")
        chunks = original.split("[[package]]")
        kept = [chunks[0]]
        for chunk in chunks[1:]:
            if re.search(rf'\nname = "{re.escape(target)}"\n', "\n" + chunk, flags=re.IGNORECASE):
                continue
            kept.append("[[package]]" + chunk)
        path.write_text("".join(kept), encoding="utf-8")

    def loosen_dev_pin(sandbox: Path) -> None:
        path = sandbox / "cwc-requirements-dev.txt"
        text = path.read_text(encoding="utf-8")
        text = text.replace("pytest-cov==7.1.0", "pytest-cov>=7.1.0", 1)
        path.write_text(text, encoding="utf-8")

    def remove_canonical_hash(sandbox: Path) -> None:
        path = sandbox / "uv.lock"
        text = path.read_text(encoding="utf-8")
        pattern = re.compile(
            r'(url = "[^"]*-cp310-cp310-[^"]+\.whl", )hash = "sha256:[0-9a-f]{64}", '
        )
        mutated, count = pattern.subn(r"\1", text, count=1)
        if count != 1:
            raise RuntimeError("self-test could not locate canonical CPython 3.10 wheel hash")
        path.write_text(mutated, encoding="utf-8")

    attack("unapproved_registry_origin", bad_registry)
    attack("unapproved_artifact_origin", bad_artifact_host)
    attack("missing_direct_dependency", remove_direct_dependency)
    attack("unpinned_dev_tool", loosen_dev_pin)
    attack("canonical_artifact_hash_removed", remove_canonical_hash)
    return attacks


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        attacks = run_self_test()
        if args.json:
            print(json.dumps({"attacks": attacks}, sort_keys=True))
        else:
            for name, killed in attacks.items():
                print(f"DEPENDENCY-INTEGRITY-ATTACK {name}: {'KILLED' if killed else 'SURVIVED'}")
        if not attacks or not all(attacks.values()):
            return 1
        print(f"DEPENDENCY-INTEGRITY SELF-TEST: PASS ({len(attacks)}/{len(attacks)} attacks killed)")
        return 0

    report = audit()
    if args.json:
        print(
            json.dumps(
                {
                    "status": "PASS" if report.passed else "FAIL",
                    "errors": report.errors,
                    "warnings": report.warnings,
                    "metrics": report.metrics,
                },
                sort_keys=True,
            )
        )
        return 0 if report.passed else 1
    for warning in report.warnings:
        print(f"DEPENDENCY-INTEGRITY-WARN: {warning}")
    if report.errors:
        for error in report.errors:
            print(f"DEPENDENCY-INTEGRITY-FAIL: {error}")
        return 1
    print(
        "DEPENDENCY-INTEGRITY: PASS "
        f"(packages={report.metrics['lock_package_records']}, "
        f"artifacts={report.metrics['artifact_records']}, "
        f"hashed={report.metrics['hashed_artifact_records']}, "
        f"canonical_hashless={report.metrics['canonical_hashless_artifacts']}, "
        f"noncanonical_hashless={report.metrics['noncanonical_hashless_artifacts']}, "
        "CVE=UNKNOWN_EXTERNAL_AUDIT_REQUIRED)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
