from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "dgc_materialize_external_sources.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("dgc_materialize_external_sources_tx", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _registry(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "families": [
                    {"family_id": "SWE_BENCH_VERIFIED", "authority_digest": "a" * 64},
                    {"family_id": "TERMINAL_BENCH_2_1", "authority_digest": "b" * 64},
                ]
            }
        )
    )


def test_materializer_failure_never_publishes_partial_generation(tmp_path: Path, monkeypatch):
    module = _load_module()
    registry = tmp_path / "registry.json"
    _registry(registry)
    final = tmp_path / "final"
    monkeypatch.setattr(module, "SOURCE_REGISTRY", registry)
    monkeypatch.setattr(module, "_repo_identity", lambda root: ("c" * 40, "d" * 40))

    def swe(row, root):
        (root / "SWE_BENCH_VERIFIED").mkdir()
        (root / "SWE_BENCH_VERIFIED" / "payload").write_bytes(b"swe")
        return {"family_id": row["family_id"], "stage": "MATERIALIZED_VERIFIED"}

    def terminal(row, root):
        (root / "TERMINAL_BENCH_2_1").mkdir()
        (root / "TERMINAL_BENCH_2_1" / "partial").write_bytes(b"partial")
        raise RuntimeError("terminal materialization failed")

    monkeypatch.setattr(module, "_materialize_swe", swe)
    monkeypatch.setattr(module, "_materialize_terminal", terminal)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--output-root", str(final)])

    with pytest.raises(RuntimeError, match="terminal materialization failed"):
        module.main()
    assert not final.exists()
    assert not list(tmp_path.glob(".final.staging-*"))


def test_success_publishes_only_after_both_families_complete(tmp_path: Path, monkeypatch, capsys):
    module = _load_module()
    registry = tmp_path / "registry.json"
    _registry(registry)
    final = tmp_path / "final"
    monkeypatch.setattr(module, "SOURCE_REGISTRY", registry)
    monkeypatch.setattr(module, "_repo_identity", lambda root: ("c" * 40, "d" * 40))

    def materialize(row, root):
        family = root / row["family_id"]
        family.mkdir()
        (family / "payload").write_text(row["family_id"])
        return {
            "family_id": row["family_id"],
            "stage": "MATERIALIZED_VERIFIED",
            "authority_digest": row["authority_digest"],
        }

    monkeypatch.setattr(module, "_materialize_swe", materialize)
    monkeypatch.setattr(module, "_materialize_terminal", materialize)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--output-root", str(final)])

    assert module.main() == 0
    assert final.is_dir()
    receipt = json.loads((final / "MATERIALIZATION_RECEIPT.json").read_text())
    provenance = json.loads((final / "MATERIALIZATION_PROVENANCE.json").read_text())
    generation = json.loads((final / "GENERATION_MANIFEST.json").read_text())
    assert receipt["schema"] == "DGC_EXTERNAL_MATERIALIZATION_RECEIPT_V2"
    assert receipt["execution_authorized"] is False
    assert provenance["slsa_conformance_claim"] is False
    assert len(generation["files"]) >= 4
    stdout = json.loads(capsys.readouterr().out)
    assert stdout["status"] == "PASS"
    assert stdout["product_promotion_authorized"] is False


def test_existing_generation_is_immutable(tmp_path: Path, monkeypatch):
    module = _load_module()
    registry = tmp_path / "registry.json"
    _registry(registry)
    final = tmp_path / "final"
    final.mkdir()
    (final / "keep").write_text("x")
    monkeypatch.setattr(module, "SOURCE_REGISTRY", registry)
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), "--output-root", str(final)])
    with pytest.raises(ValueError, match="must not exist"):
        module.main()
    assert (final / "keep").read_text() == "x"
