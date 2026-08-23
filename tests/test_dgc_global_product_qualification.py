from __future__ import annotations

import json
from pathlib import Path

import pytest

import cwc.governance.global_product_qualification as gpq
from cwc.governance.global_product_qualification import (
    GlobalProductQualificationError,
    build_global_product_qualification_authority,
    verify_global_product_qualification_authority_document,
)


def _registry(tmp_path: Path) -> Path:
    path = tmp_path / "registry.json"
    path.write_text(json.dumps({
        "schema": gpq.SOURCE_REGISTRY_SCHEMA,
        "families": [
            {"family_id": "SWE_BENCH_VERIFIED"},
            {"family_id": "TERMINAL_BENCH_2_1"},
        ],
    }, sort_keys=True))
    return path


def _p19(family_id: str, p19_digest: str, *, theorem: str = "4" * 64) -> dict[str, object]:
    return {
        "family_id": family_id,
        "p19_digest": p19_digest,
        "family_evidence_complete": True,
        "repository_commit": "1" * 40,
        "repository_tree": "2" * 40,
        "statistical_plan_digest": "3" * 64,
        "theorem_identity_digest": theorem,
        "methodology_anchor_digest": "5" * 64,
    }


def _patch_family_docs(monkeypatch, docs: dict[str, dict[str, object]]):
    monkeypatch.setattr(gpq, "verify_family_p19_evidence_root_document", lambda path: docs[Path(path).name])
    monkeypatch.setattr(gpq, "_rehash_family_p19_subjects", lambda doc, repository_root: None)


def test_global_authority_requires_exact_two_canonical_families_under_one_v5_methodology(tmp_path: Path, monkeypatch):
    docs = {
        "swe.json": _p19("SWE_BENCH_VERIFIED", "a" * 64),
        "terminal.json": _p19("TERMINAL_BENCH_2_1", "b" * 64),
    }
    _patch_family_docs(monkeypatch, docs)
    authority = build_global_product_qualification_authority(
        repository_root=tmp_path,
        source_registry_path=_registry(tmp_path),
        family_p19_paths=(tmp_path / "swe.json", tmp_path / "terminal.json"),
    )
    assert authority.canonical_family_ids == ("SWE_BENCH_VERIFIED", "TERMINAL_BENCH_2_1")
    assert authority.product_qualified is True
    assert authority.production_control_authorized is False
    assert authority.family_count == 2

    path = tmp_path / "global.json"
    path.write_text(json.dumps(authority.document, sort_keys=True))
    verified = verify_global_product_qualification_authority_document(path)
    assert verified["global_product_qualification_authorized"] is True
    assert verified["production_provider_trace_supported"] is False


def test_theorem_mismatch_between_families_fails_closed(tmp_path: Path, monkeypatch):
    docs = {
        "swe.json": _p19("SWE_BENCH_VERIFIED", "a" * 64, theorem="4" * 64),
        "terminal.json": _p19("TERMINAL_BENCH_2_1", "b" * 64, theorem="6" * 64),
    }
    _patch_family_docs(monkeypatch, docs)
    with pytest.raises(GlobalProductQualificationError, match="statistical/theorem/methodology"):
        build_global_product_qualification_authority(
            repository_root=tmp_path,
            source_registry_path=_registry(tmp_path),
            family_p19_paths=(tmp_path / "swe.json", tmp_path / "terminal.json"),
        )


def test_duplicate_family_cannot_substitute_for_two_family_panel(tmp_path: Path, monkeypatch):
    docs = {
        "one.json": _p19("SWE_BENCH_VERIFIED", "a" * 64),
        "two.json": _p19("SWE_BENCH_VERIFIED", "b" * 64),
    }
    _patch_family_docs(monkeypatch, docs)
    with pytest.raises(GlobalProductQualificationError, match="canonical source registry"):
        build_global_product_qualification_authority(
            repository_root=tmp_path,
            source_registry_path=_registry(tmp_path),
            family_p19_paths=(tmp_path / "one.json", tmp_path / "two.json"),
        )


def test_same_p19_root_cannot_be_counted_twice(tmp_path: Path, monkeypatch):
    docs = {
        "swe.json": _p19("SWE_BENCH_VERIFIED", "a" * 64),
        "terminal.json": _p19("TERMINAL_BENCH_2_1", "a" * 64),
    }
    _patch_family_docs(monkeypatch, docs)
    with pytest.raises(GlobalProductQualificationError, match="distinct family P19 roots"):
        build_global_product_qualification_authority(
            repository_root=tmp_path,
            source_registry_path=_registry(tmp_path),
            family_p19_paths=(tmp_path / "swe.json", tmp_path / "terminal.json"),
        )


def test_product_authority_cannot_leak_production_control_claim(tmp_path: Path, monkeypatch):
    docs = {
        "swe.json": _p19("SWE_BENCH_VERIFIED", "a" * 64),
        "terminal.json": _p19("TERMINAL_BENCH_2_1", "b" * 64),
    }
    _patch_family_docs(monkeypatch, docs)
    authority = build_global_product_qualification_authority(
        repository_root=tmp_path,
        source_registry_path=_registry(tmp_path),
        family_p19_paths=(tmp_path / "swe.json", tmp_path / "terminal.json"),
    )
    doc = authority.document
    doc["production_control_authorized"] = True
    path = tmp_path / "bad-global.json"
    path.write_text(json.dumps(doc, sort_keys=True))
    with pytest.raises(GlobalProductQualificationError, match="cannot authorize production control"):
        verify_global_product_qualification_authority_document(path)
