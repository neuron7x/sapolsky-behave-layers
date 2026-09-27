from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "dgc_close_external_materialization.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("dgc_close_external_materialization_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("value", ["g1", "gen-2026-08-23", "trial.v2_A"])
def test_generation_id_accepts_safe_slug(value: str):
    assert _load_module()._generation_id(value) == value


@pytest.mark.parametrize("value", ["../escape", "a/b", "/absolute", "", "has space", "x" * 129])
def test_generation_id_rejects_path_traversal_and_unsafe_values(value: str):
    with pytest.raises(Exception):
        _load_module()._generation_id(value)
