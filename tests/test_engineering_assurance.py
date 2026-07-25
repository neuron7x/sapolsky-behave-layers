from __future__ import annotations

from pathlib import Path

from scripts import (
    architecture_gate,
    assurance_attack,
    assurance_report,
    build_sbom,
    complexity_gate,
    hermeticity_gate,
)

ROOT = Path(__file__).resolve().parents[1]


def test_architecture_contract_matches_real_import_graph() -> None:
    assert architecture_gate.validate(ROOT) == []


def test_canonical_reproduction_path_is_hermetic() -> None:
    assert hermeticity_gate.validate(ROOT) == []


def test_critical_function_complexity_budgets_hold() -> None:
    assert complexity_gate.validate(ROOT) == []


def test_sbom_exactly_matches_frozen_lock() -> None:
    assert build_sbom.validate(ROOT) == []


def test_assurance_controls_kill_every_injected_fault() -> None:
    results = assurance_attack.run_attacks()
    assert results
    assert all(results.values()), results


def test_assurance_report_is_commit_bound_and_green() -> None:
    report = assurance_report.build_report(ROOT)
    assert report["status"] == "pass"
    assert report["git_commit"]
    assert report["git_tree"]
    assert len(report["uv_lock_sha256"]) == 64
