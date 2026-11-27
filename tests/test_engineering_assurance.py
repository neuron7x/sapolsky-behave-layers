from __future__ import annotations

import json
from pathlib import Path

import pytest

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


@pytest.fixture
def architecture_fixture(tmp_path: Path) -> Path:
    contract = json.loads((ROOT / architecture_gate.CONTRACT).read_text(encoding="utf-8"))
    for row in contract["boundaries"]:
        package = tmp_path / row["root"]
        package.mkdir(parents=True, exist_ok=True)
        (package / "__init__.py").write_text("", encoding="utf-8")
    path = tmp_path / architecture_gate.CONTRACT
    path.parent.mkdir()
    path.write_text(json.dumps(contract), encoding="utf-8")
    return tmp_path


@pytest.mark.parametrize(("source", "statement"), [
    ("cwc/instrumentation/component.py", "import cwc.plasticity"),
    ("cwc/instrumentation/component.py", "from cwc import plasticity"),
    ("cwc/instrumentation/component.py", "from .. import plasticity"),
    ("cwc/instrumentation/component.py", "from ..plasticity import optimizer"),
    ("cwc/instrumentation/nested/__init__.py", "from ... import plasticity"),
])
def test_architecture_rejects_equivalent_cross_boundary_imports(
    architecture_fixture: Path, source: str, statement: str,
) -> None:
    path = architecture_fixture / source
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(statement + "\n", encoding="utf-8")

    errors = architecture_gate.validate(architecture_fixture)

    assert len(errors) == 1
    assert errors[0].startswith(f"{source}:1: forbidden cross-boundary import cwc.plasticity")


def test_architecture_accepts_local_imports_in_module_and_initializer(architecture_fixture: Path) -> None:
    package = architecture_fixture / "cwc/instrumentation"
    (package / "__init__.py").write_text("from . import sibling\n", encoding="utf-8")
    (package / "sibling.py").write_text("from pathlib import Path\n", encoding="utf-8")
    (package / "component.py").write_text("from ..instrumentation import sibling as local\n", encoding="utf-8")

    assert architecture_gate.validate(architecture_fixture) == []


@pytest.mark.parametrize("roster", [None, [], {"root": "cwc/instrumentation"}])
def test_architecture_requires_nonempty_boundary_roster(
    architecture_fixture: Path, roster: object,
) -> None:
    contract = {"schema_version": 2, "declared_dynamic_imports": []}
    if roster is not None:
        contract["boundaries"] = roster
    (architecture_fixture / architecture_gate.CONTRACT).write_text(json.dumps(contract), encoding="utf-8")

    assert any("nonempty boundary roster required" in error for error in architecture_gate.validate(architecture_fixture))


def test_architecture_detects_undeclared_new_package(architecture_fixture: Path) -> None:
    package = architecture_fixture / "cwc/new_package"
    package.mkdir()
    (package / "component.py").write_text("", encoding="utf-8")

    assert architecture_gate.validate(architecture_fixture) == [
        "engineering/architecture_contract.json: missing boundary cwc/new_package",
    ]


def test_architecture_detects_missing_critical_boundary(architecture_fixture: Path) -> None:
    path = architecture_fixture / architecture_gate.CONTRACT
    contract = json.loads(path.read_text(encoding="utf-8"))
    contract["boundaries"] = [row for row in contract["boundaries"] if row["root"] != "cwc/governance"]
    path.write_text(json.dumps(contract), encoding="utf-8")
    (architecture_fixture / "cwc/governance/__init__.py").unlink()

    assert architecture_gate.validate(architecture_fixture) == [
        "engineering/architecture_contract.json: missing boundary cwc/governance",
    ]


def test_architecture_dynamic_import_inventory_and_permission(architecture_fixture: Path) -> None:
    source = "cwc/instrumentation/component.py"
    path = architecture_fixture / source
    path.write_text(
        'from importlib import import_module as load\nload("cwc.instrumentation.sibling")\n',
        encoding="utf-8",
    )
    assert architecture_gate.validate(architecture_fixture) == [
        f"{source}:2: undeclared dynamic import cwc.instrumentation.sibling",
    ]

    contract_path = architecture_fixture / architecture_gate.CONTRACT
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    contract["declared_dynamic_imports"] = [{"source": source, "module": "cwc.instrumentation.sibling"}]
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    (path.parent / "sibling.py").write_text("", encoding="utf-8")
    assert architecture_gate.validate(architecture_fixture) == []

    contract["declared_dynamic_imports"] = [{"source": source, "module": "cwc.plasticity"}]
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    path.write_text('import importlib as loader\nloader.import_module("cwc.plasticity")\n', encoding="utf-8")
    assert architecture_gate.validate(architecture_fixture) == [
        f"{source}:2: forbidden cross-boundary import cwc.plasticity",
    ]


def test_architecture_rejects_unresolved_imports(architecture_fixture: Path) -> None:
    path = architecture_fixture / "cwc/instrumentation/component.py"
    path.write_text("from ... import sibling\n", encoding="utf-8")
    assert any("cannot resolve source imports" in error for error in architecture_gate.validate(architecture_fixture))
    path.write_text("import importlib\nimportlib.import_module(module_name)\n", encoding="utf-8")
    assert architecture_gate.validate(architecture_fixture) == [
        "cwc/instrumentation/component.py:2: unsupported dynamic import target",
    ]


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
