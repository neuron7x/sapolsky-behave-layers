from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

import pytest

from scripts import dependency_integrity_gate

ROOT = Path(__file__).resolve().parents[1]


def test_dependency_integrity_gate_passes_canonical_supply_chain() -> None:
    report = dependency_integrity_gate.audit(ROOT)
    assert report.errors == ()
    assert report.metrics["canonical_python"] == "3.11"
    assert report.metrics["canonical_hashless_artifacts"] == 0
    assert report.metrics["noncanonical_hashless_artifacts"] == 0
    assert report.metrics["vulnerability_status"] == "UNKNOWN_EXTERNAL_AUDIT_REQUIRED"


def test_dependency_integrity_has_no_hash_debt() -> None:
    report = dependency_integrity_gate.audit(ROOT)
    assert report.metrics["hashed_artifact_records"] == report.metrics["artifact_records"]
    assert report.warnings == ()


def test_dependency_integrity_self_test_kills_all_faults() -> None:
    attacks = dependency_integrity_gate.run_self_test(ROOT)
    assert len(attacks) == 8
    assert all(attacks.values()), attacks


def test_dependency_self_test_rejects_disabled_origin_guard(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(dependency_integrity_gate, "_safe_https_host", lambda *_: (True, ""))
    monkeypatch.setattr(sys, "argv", ["dependency_integrity_gate", "--self-test"])

    assert dependency_integrity_gate.main() == 1
    output = capsys.readouterr().out
    assert "unapproved_registry_origin: SURVIVED" in output
    assert "unapproved_artifact_origin: SURVIVED" in output
    assert "sbom_lock_equivalence: KILLED" in output
    assert "SELF-TEST: PASS" not in output


def test_dependency_self_test_calibrates_sbom_independently(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dependency_integrity_gate.build_sbom, "validate", lambda *_: [])

    attacks = dependency_integrity_gate.run_self_test(ROOT)

    assert attacks.pop("sbom_lock_equivalence") is False
    assert attacks["noncanonical_artifact_hash_removed"] is True
    assert attacks["dev_runtime_version_drift"] is True
    assert all(attacks.values()), attacks


def test_dependency_self_test_rejects_disabled_hash_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dependency_integrity_gate, "SHA256", re.compile(".*"))

    attacks = dependency_integrity_gate.run_self_test(ROOT)

    assert attacks.pop("canonical_artifact_hash_removed") is False
    assert attacks.pop("noncanonical_artifact_hash_removed") is False
    assert all(attacks.values()), attacks


def test_dependency_self_test_rejects_preexisting_supply_chain_fault(tmp_path: Path) -> None:
    for relative in (
        ".python-version", "pyproject.toml", "uv.lock", "cwc-requirements-dev.txt", "docs/security/SBOM.cdx.json"
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)
    (tmp_path / "cwc-requirements-dev.txt").write_text("pytest-cov>=7.1.0\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="requires passing unmodified dependency controls"):
        dependency_integrity_gate.run_self_test(tmp_path)


def _write_controls_fixture(tmp_path: Path, pin: str = "3.11") -> None:
    tag = "cp" + "".join(pin.split(".")[:2])
    (tmp_path / ".python-version").write_text(pin + "\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "fixture"\ndependencies = ["alpha>=1"]\n', encoding="utf-8"
    )
    (tmp_path / "cwc-requirements-dev.txt").write_text("pytest-cov==7.1.0\nalpha==1.0\n", encoding="utf-8")
    (tmp_path / "uv.lock").write_text(
        'version = 1\n\n[[package]]\nname = "alpha"\nversion = "1.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
        'wheels = [\n'
        f'    {{ url = "https://files.pythonhosted.org/alpha-1.0-{tag}-{tag}-linux.whl", '
        f'hash = "sha256:{"0" * 64}", size = 1 }},\n'
        '    { url = "https://files.pythonhosted.org/alpha-1.0-cp999-cp999-linux.whl", '
        f'hash = "sha256:{"1" * 64}", size = 1 }},\n]\n\n'
        '[[package]]\nname = "fixture"\nversion = "1.0"\nsource = { virtual = "." }\n',
        encoding="utf-8",
    )
    sbom = tmp_path / "docs/security/SBOM.cdx.json"
    sbom.parent.mkdir(parents=True)
    sbom.write_text(
        dependency_integrity_gate.build_sbom.render(dependency_integrity_gate.build_sbom.build(tmp_path)),
        encoding="utf-8",
    )


@pytest.mark.parametrize(
    "requirement",
    [
        "ruff==0.*",
        "ruff==0.16.*",
        "ruff==0.16.2,!=0.16.3",
        "ruff==0.16.2,<1",
        "ruff==0.16.2,==0.16.2",
        "ruff==0.16.2>=0.16.1",
        "ruff===0.16.2",
        'ruff==0.*; python_version < "3.13"',
        "ruff==not-a-version",
    ],
)
def test_dev_requirement_must_pin_one_version(tmp_path: Path, requirement: str) -> None:
    _write_controls_fixture(tmp_path)
    dev = tmp_path / "cwc-requirements-dev.txt"
    dev.write_text(dev.read_text(encoding="utf-8") + requirement + "\n", encoding="utf-8")
    assert dependency_integrity_gate.build_sbom.validate(tmp_path) == []

    report = dependency_integrity_gate.audit(tmp_path)

    assert report.errors == (f"cwc-requirements-dev.txt: requirement is not exact-pinned: {requirement}",)


@pytest.mark.parametrize(
    "requirement",
    [
        "ruff==0.16.2",
        "ruff==1!2.0.0",
        "ruff==2.13.0+cu130",
        "ruff==1.0rc1",
        "ruff==v1.0-2",
        "ruff==1.0.post1.dev2+local.1",
        "ruff==1.0a",
        "ruff==1.0_rev",
        "ruff==1.0DEV",
        "ruff==1.0+linux_x86-64",
        'ruff[format,test]==0.16.2; python_version < "3.13"',
        'ruff==0.16.2 ; python_version in "3.10, 3.11"',
    ],
)
def test_exact_dev_versions_and_markers_remain_valid(tmp_path: Path, requirement: str) -> None:
    _write_controls_fixture(tmp_path)
    dev = tmp_path / "cwc-requirements-dev.txt"
    dev.write_text(dev.read_text(encoding="utf-8") + requirement + "\n", encoding="utf-8")

    assert dependency_integrity_gate.audit(tmp_path).errors == ()


@pytest.mark.parametrize("pin", ["3.10", "3.11", "3.12.1"])
def test_dependency_self_test_uses_pinned_python_wheel(tmp_path: Path, pin: str) -> None:
    _write_controls_fixture(tmp_path, pin)

    attacks = dependency_integrity_gate.run_self_test(tmp_path)

    assert len(attacks) == 8
    assert all(attacks.values()), attacks


@pytest.mark.parametrize("replacement", ["", 'hash = "sha256:invalid", '])
def test_noncanonical_hash_guard_is_independent_of_sbom(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, replacement: str
) -> None:
    _write_controls_fixture(tmp_path)
    lock = tmp_path / "uv.lock"
    lock.write_text(
        lock.read_text(encoding="utf-8").replace(f'hash = "sha256:{"1" * 64}", ', replacement, 1),
        encoding="utf-8",
    )
    monkeypatch.setattr(dependency_integrity_gate.build_sbom, "validate", lambda *_: [])

    report = dependency_integrity_gate.audit(tmp_path)

    assert not report.passed
    assert report.metrics["canonical_hashless_artifacts"] == 0
    assert report.metrics["noncanonical_hashless_artifacts"] == 1
    assert any(error.startswith("noncanonical artifact missing SHA-256:") for error in report.errors)


def test_dev_runtime_version_drift_fails_with_unchanged_lock_and_sbom(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_controls_fixture(tmp_path)
    dev = tmp_path / "cwc-requirements-dev.txt"
    dev.write_text(dev.read_text(encoding="utf-8").replace("alpha==1.0", "alpha==2.0"), encoding="utf-8")
    assert dependency_integrity_gate.build_sbom.validate(tmp_path) == []
    monkeypatch.setattr(dependency_integrity_gate.build_sbom, "validate", lambda *_: [])

    report = dependency_integrity_gate.audit(tmp_path)

    assert report.errors == ("cwc-requirements-dev.txt: runtime pin alpha==2.0 mismatches uv.lock versions: ['1.0']",)


def test_transitive_dev_pin_must_match_locked_version(tmp_path: Path) -> None:
    _write_controls_fixture(tmp_path)
    lock = tmp_path / "uv.lock"
    lock.write_text(
        lock.read_text(encoding="utf-8").replace(
            'name = "alpha"\nversion = "1.0"\n',
            'name = "alpha"\nversion = "1.0"\ndependencies = [{ name = "beta" }]\n',
            1,
        )
        + '\n[[package]]\nname = "beta"\nversion = "1.0"\n'
        + 'source = { registry = "https://pypi.org/simple" }\n'
        + 'sdist = { url = "https://files.pythonhosted.org/beta-1.0.tar.gz", '
        + f'hash = "sha256:{"2" * 64}", size = 1 }}\n',
        encoding="utf-8",
    )
    (tmp_path / "docs/security/SBOM.cdx.json").write_text(
        dependency_integrity_gate.build_sbom.render(dependency_integrity_gate.build_sbom.build(tmp_path)),
        encoding="utf-8",
    )
    dev = tmp_path / "cwc-requirements-dev.txt"
    dev.write_text("pytest-cov==7.1.0\nbeta==1.0\n", encoding="utf-8")
    assert dependency_integrity_gate.audit(tmp_path).errors == ()

    dev.write_text("pytest-cov==7.1.0\nbeta==2.0\n", encoding="utf-8")
    assert dependency_integrity_gate.build_sbom.validate(tmp_path) == []

    assert dependency_integrity_gate.audit(tmp_path).errors == (
        "cwc-requirements-dev.txt: runtime pin beta==2.0 mismatches uv.lock versions: ['1.0']",
    )
    dev.write_text("pytest-cov==7.1.0\nbeta==1.0\n", encoding="utf-8")
    attacks = dependency_integrity_gate.run_self_test(tmp_path)
    assert len(attacks) == 8 and all(attacks.values()), attacks


@pytest.mark.parametrize(
    ("project_name", "locked_name", "dev_name"),
    [
        ("alpha-beta", "alpha-beta", "alpha.beta"),
        ("Alpha_Beta", "alpha.beta", "ALPHA--BETA"),
        ("alpha._-beta", "Alpha__Beta", "alpha-beta"),
        ("ALPHA---BETA", "alpha._.-beta", "Alpha___Beta"),
    ],
)
def test_equivalent_package_names_cannot_bypass_version_guards(
    tmp_path: Path, project_name: str, locked_name: str, dev_name: str
) -> None:
    _write_controls_fixture(tmp_path)
    project = tmp_path / "pyproject.toml"
    project.write_text(
        project.read_text(encoding="utf-8").replace("alpha>=1", f"{project_name}==1.0"),
        encoding="utf-8",
    )
    lock = tmp_path / "uv.lock"
    lock.write_text(
        lock.read_text(encoding="utf-8").replace('name = "alpha"', f'name = "{locked_name}"'),
        encoding="utf-8",
    )
    (tmp_path / "docs/security/SBOM.cdx.json").write_text(
        dependency_integrity_gate.build_sbom.render(dependency_integrity_gate.build_sbom.build(tmp_path)),
        encoding="utf-8",
    )
    dev = tmp_path / "cwc-requirements-dev.txt"
    matching_dev = f"pytest-cov==7.1.0\n{dev_name}==1.0\n"
    dev.write_text(matching_dev, encoding="utf-8")
    assert dependency_integrity_gate.audit(tmp_path).errors == ()

    dev.write_text(matching_dev.replace("==1.0", "==2.0"), encoding="utf-8")
    assert dependency_integrity_gate.audit(tmp_path).errors == (
        "cwc-requirements-dev.txt: runtime pin alpha-beta==2.0 mismatches uv.lock versions: ['1.0']",
    )

    dev.write_text(matching_dev, encoding="utf-8")
    project.write_text(project.read_text(encoding="utf-8").replace("==1.0", "==2.0"), encoding="utf-8")
    assert dependency_integrity_gate.audit(tmp_path).errors == (
        "uv.lock: exact pin alpha-beta==2.0 has mismatched locked variants: ['1.0']",
    )
    project.write_text(project.read_text(encoding="utf-8").replace("==2.0", "==1.0"), encoding="utf-8")
    attacks = dependency_integrity_gate.run_self_test(tmp_path)
    assert len(attacks) == 8 and all(attacks.values()), attacks


def test_locked_name_normalization_does_not_truncate_invalid_suffix(tmp_path: Path) -> None:
    _write_controls_fixture(tmp_path)
    lock = tmp_path / "uv.lock"
    lock.write_text(
        lock.read_text(encoding="utf-8").replace('name = "alpha"', 'name = "alpha/other"'),
        encoding="utf-8",
    )
    (tmp_path / "docs/security/SBOM.cdx.json").write_text(
        dependency_integrity_gate.build_sbom.render(dependency_integrity_gate.build_sbom.build(tmp_path)),
        encoding="utf-8",
    )

    assert "uv.lock: direct dependency missing: alpha" in dependency_integrity_gate.audit(tmp_path).errors


def test_security_admission_keeps_integrity_and_cve_gates_distinct() -> None:
    makefile = (ROOT / "Makefile.cwc").read_text(encoding="utf-8")
    security_line = next(line for line in makefile.splitlines() if line.startswith("pr-security:"))
    assert "dependency-integrity-gate" in security_line
    assert "dependency-audit" in security_line
    assert security_line.index("dependency-integrity-gate") < security_line.index("dependency-audit")


def test_assurance_report_exposes_external_cve_limitation() -> None:
    from scripts import assurance_report

    report = assurance_report.build_report(ROOT)
    checks = {item["name"]: item for item in report["checks"]}
    assert checks["dependency_integrity"]["status"] == "pass"
    assert report["limitations"]["vulnerability_status"] == "UNKNOWN_EXTERNAL_AUDIT_REQUIRED"
    assert report["limitations"]["dependency_integrity_warnings"] == []
