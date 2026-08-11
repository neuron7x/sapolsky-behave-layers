from __future__ import annotations

from pathlib import Path

from scripts import dependency_integrity_gate

ROOT = Path(__file__).resolve().parents[1]


def test_dependency_integrity_gate_passes_canonical_supply_chain() -> None:
    report = dependency_integrity_gate.audit(ROOT)
    assert report.errors == ()
    assert report.metrics["canonical_python"] == "3.10"
    assert report.metrics["canonical_hashless_artifacts"] == 0
    assert report.metrics["noncanonical_hashless_artifacts"] == 13
    assert report.metrics["vulnerability_status"] == "UNKNOWN_EXTERNAL_AUDIT_REQUIRED"


def test_dependency_integrity_reports_noncanonical_hash_debt() -> None:
    report = dependency_integrity_gate.audit(ROOT)
    assert any("unhashed noncanonical artifacts: 13" in item for item in report.warnings)


def test_dependency_integrity_self_test_kills_all_faults() -> None:
    attacks = dependency_integrity_gate.run_self_test(ROOT)
    assert len(attacks) == 5
    assert all(attacks.values()), attacks


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
    assert report["limitations"]["dependency_integrity_warnings"]
