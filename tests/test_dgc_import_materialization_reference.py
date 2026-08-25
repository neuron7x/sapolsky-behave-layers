from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "dgc_import_materialization_reference.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("dgc_import_materialization_reference_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_reference_output_is_confined_to_ignored_eval_bundle(tmp_path: Path, monkeypatch):
    module = _load_module()
    root = tmp_path / "repo"
    runtime = root / "eval_bundle"
    root.mkdir()
    monkeypatch.setattr(module, "ROOT", root)
    monkeypatch.setattr(module, "RUNTIME_EVIDENCE_ROOT", runtime)

    allowed = module._runtime_output(runtime / "dgc" / "materialization.json")
    assert allowed == (runtime / "dgc" / "materialization.json").resolve()
    with pytest.raises(ValueError, match="eval_bundle"):
        module._runtime_output(root / "artifacts" / "materialization.json")
    with pytest.raises(ValueError, match="eval_bundle"):
        module._runtime_output(tmp_path / "outside.json")


def test_reference_output_is_immutable(tmp_path: Path, monkeypatch):
    module = _load_module()
    root = tmp_path / "repo"
    runtime = root / "eval_bundle"
    runtime.mkdir(parents=True)
    target = runtime / "reference.json"
    target.write_text("existing")
    monkeypatch.setattr(module, "ROOT", root)
    monkeypatch.setattr(module, "RUNTIME_EVIDENCE_ROOT", runtime)
    with pytest.raises(FileExistsError, match="immutable"):
        module._runtime_output(target)
