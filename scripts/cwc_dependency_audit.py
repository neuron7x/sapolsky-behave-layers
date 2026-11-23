"""Audit explicit dependency closures with an isolated, hash-locked audit tool.

The runtime/dev exports remain frozen to uv.lock. --no-deps disables a second,
unlocked resolution, not auditing: each exported transitive pin is submitted.
The advisory service is pip-audit's existing default (PyPI), with no CVE ignores.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
import tomllib
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def locked_versions(path: Path) -> dict[str, str]:
    """The CI locks deliberately use exact pins and SHA256 wheel allowlists only."""
    versions = {}
    text = path.read_text(encoding="utf-8").replace("\\\n", " ")
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([A-Za-z0-9.!+_-]+)((?:\s+--hash=sha256:[0-9a-f]{64})+)\s*", line)
        if match is None:
            raise ValueError(f"non-exact or unhashed dependency: {path.name}")
        name = re.sub(r"[-_.]+", "-", match[1]).lower()
        if name in versions:
            raise ValueError(f"duplicate dependency: {name}")
        versions[name] = match[2]
    if not versions:
        raise ValueError(f"empty dependency lock: {path}")
    return versions


def validate_controls(root: Path) -> None:
    dev = locked_versions(root / "requirements/cwc-dev.lock")
    locked_versions(root / "requirements/pip-audit.lock")
    runtime = {}
    for package in tomllib.loads((root / "uv.lock").read_text(encoding="utf-8"))["package"]:
        if "version" in package:
            runtime.setdefault(package["name"], set()).add(package["version"])
    for line in (root / "cwc-requirements-dev.txt").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        name, version = line.strip().split("==")
        name = re.sub(r"[-_.]+", "-", name).lower()
        if dev.get(name) != version:
            raise ValueError(f"development input/lock mismatch: {name}")
    for name, version in dev.items():
        if name in runtime and version not in runtime[name]:
            raise ValueError(f"development/runtime lock mismatch: {name}")


def require_target(path: Path) -> None:
    if not path.is_file() or not any(
        line.strip() and not line.lstrip().startswith(("#", "--"))
        for line in path.read_text(encoding="utf-8").splitlines()
    ):
        raise ValueError(f"missing or empty dependency audit target: {path}")


def prepare_targets(root: Path, directory: Path) -> list[Path]:
    for name in ("uv.lock", "pyproject.toml", "requirements/cwc-dev.lock", "requirements/pip-audit.lock"):
        require_target(root / name)
    targets = []
    for label, group in (("runtime", "--no-dev"), ("dev-group", "--only-dev")):
        target = directory / f"{label}.txt"
        subprocess.run([
            "uv", "export", "--quiet", "--frozen", "--extra", "cpu", group,
            "--no-emit-project", "--no-hashes", "--output-file", str(target),
        ], cwd=root, check=True)
        require_target(target)
        # PyPI advisory names omit the CPU wheel's local-version suffix. Keep
        # the established mapping, without changing the frozen installed wheel.
        content = re.sub(r"(?m)^(torch==[0-9.]+)\+cpu(?=\s|$)", r"\1", target.read_text(encoding="utf-8"))
        target.write_text(content, encoding="utf-8")
        targets.append(target)
    targets.append(root / "requirements/cwc-dev.lock")
    return targets


def install_tool(environment: Path, lock: Path) -> Path:
    require_target(lock)
    venv.EnvBuilder(with_pip=False).create(environment)
    python = environment / "bin/python"
    subprocess.run([
        "uv", "pip", "install", "--python", str(python), "--require-hashes",
        "--only-binary", ":all:", "--default-index", "https://pypi.org/simple", "-r", str(lock),
    ], check=True)
    return python


def audit_targets(python: Path, targets: list[Path]) -> None:
    if not targets:
        raise ValueError("dependency audit target roster is empty")
    for target in targets:
        require_target(target)
    subprocess.run([str(python), "-m", "pip_audit", "--version"], check=True)
    for target in targets:
        print(f"AUDIT TARGET: {target.name}", flush=True)
        subprocess.run([
            str(python), "-m", "pip_audit", "--disable-pip", "--no-deps", "--strict",
            "-r", str(target), "--progress-spinner=off",
        ], check=True)


def main() -> int:
    try:
        validate_controls(ROOT)
        subprocess.run(["uv", "--version"], check=True)
        # Unique reservation; no shared /tmp filenames or reusable tool env.
        with tempfile.TemporaryDirectory(prefix="cwc-dependency-audit-") as directory:
            temporary = Path(directory)
            targets = prepare_targets(ROOT, temporary)
            python = install_tool(temporary / "tool", ROOT / "requirements/pip-audit.lock")
            audit_targets(python, targets)
    except subprocess.CalledProcessError as error:
        return error.returncode if error.returncode > 0 else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
