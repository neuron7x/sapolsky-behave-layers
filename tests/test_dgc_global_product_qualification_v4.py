from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import cwc.governance.global_product_qualification_v4 as v4
from cwc.governance.global_product_qualification_v4 import (
    FamilyP19VerificationInputV4,
    GlobalProductQualificationV4Error,
    build_global_product_qualification_authority_v4,
    verify_global_product_qualification_authority_v4_document,
)


def _input(tmp_path: Path, stem: str) -> FamilyP19VerificationInputV4:
    return FamilyP19VerificationInputV4(
        attestation_path=tmp_path / f"{stem}.attestation.json",
        verification_report_path=tmp_path / f"{stem}.report.json",
        signature_path=tmp_path / f"{stem}.sig",
    )


def _policy(*, allowed_sha: str = "a" * 64, minimum: int = 2):
    return SimpleNamespace(
        policy_digest="b" * 64,
        allowed_signers_sha256=allowed_sha,
        minimum_distinct_verifiers=minimum,
        same_verifier_across_families_allowed=False,
    )


def _record(family: str, principal: str, *, allowed_sha: str = "a" * 64):
    return SimpleNamespace(family_id=family, verifier_principal=principal, allowed_signers_sha256=allowed_sha)


def _v3(*, principals=("verifier-a", "verifier-b"), allowed_sha: str = "a" * 64):
    records = (
        _record("SWE_BENCH_VERIFIED", principals[0], allowed_sha=allowed_sha),
        _record("TERMINAL_BENCH_2_1", principals[1], allowed_sha=allowed_sha),
    )
    return SimpleNamespace(
        canonical_family_ids=("SWE_BENCH_VERIFIED", "TERMINAL_BENCH_2_1"),
        family_p19_digests=(("SWE_BENCH_VERIFIED", "1" * 64), ("TERMINAL_BENCH_2_1", "2" * 64)),
        family_p19_verification_records=records,
        authority_digest="3" * 64,
        repository_commit="4" * 40,
        repository_tree="5" * 40,
        statistical_plan_digest="6" * 64,
        theorem_identity_digest="7" * 64,
        methodology_anchor_digest="8" * 64,
        global_statistical_composition_rule=v4.GLOBAL_STATISTICAL_COMPOSITION_RULE,
        all_family_p19_complete=True,
        all_family_p19_externally_verified=True,
        product_qualified=True,
    )


def _patch(monkeypatch, *, v3_authority=None, policy=None):
    monkeypatch.setattr(v4, "load_p19_verifier_trust_policy", lambda path: policy or _policy())
    monkeypatch.setattr(v4, "resolve_allowed_signers", lambda policy, repository_root: Path(repository_root) / "frozen.allowed")
    monkeypatch.setattr(v4, "build_v3_global_authority", lambda **kwargs: v3_authority or _v3())


def _build(tmp_path: Path, monkeypatch, *, v3_authority=None, policy=None):
    _patch(monkeypatch, v3_authority=v3_authority, policy=policy)
    return build_global_product_qualification_authority_v4(
        repository_root=tmp_path,
        source_registry_path=tmp_path / "registry.json",
        family_p19_paths=(tmp_path / "swe.json", tmp_path / "terminal.json"),
        family_p19_verification_inputs=(_input(tmp_path, "swe"), _input(tmp_path, "terminal")),
    )


def test_v4_requires_two_distinct_principals_under_one_frozen_trust_policy(tmp_path: Path, monkeypatch):
    authority = _build(tmp_path, monkeypatch)
    assert authority.product_qualified is True
    assert authority.production_control_authorized is False
    assert authority.distinct_verifier_count == 2
    assert authority.minimum_distinct_verifiers == 2
    assert authority.verifier_principals == ("verifier-a", "verifier-b")
    assert authority.allowed_signers_sha256 == "a" * 64

    path = tmp_path / "global-v4.json"
    path.write_text(json.dumps(authority.document, sort_keys=True), encoding="utf-8")
    verified = verify_global_product_qualification_authority_v4_document(path)
    assert verified["global_product_qualification_authorized"] is True
    assert verified["frozen_verifier_trust_policy_required"] is True
    assert verified["self_contained_p19_verification_transcript_required"] is True


def test_same_verifier_for_both_families_cannot_qualify(tmp_path: Path, monkeypatch):
    with pytest.raises(GlobalProductQualificationV4Error, match="distinct verifier"):
        _build(tmp_path, monkeypatch, v3_authority=_v3(principals=("same", "same")))


def test_runtime_verification_cannot_substitute_different_trust_store(tmp_path: Path, monkeypatch):
    with pytest.raises(GlobalProductQualificationV4Error, match="frozen trust store"):
        _build(tmp_path, monkeypatch, v3_authority=_v3(allowed_sha="c" * 64), policy=_policy(allowed_sha="a" * 64))


def test_policy_minimum_above_observed_distinct_count_fails_closed(tmp_path: Path, monkeypatch):
    with pytest.raises(GlobalProductQualificationV4Error, match="minimum number"):
        _build(tmp_path, monkeypatch, policy=_policy(minimum=3))


def test_v4_document_cannot_omit_self_contained_verifier_transcript_requirement(tmp_path: Path, monkeypatch):
    authority = _build(tmp_path, monkeypatch)
    doc = authority.document
    doc["self_contained_p19_verification_transcript_required"] = False
    path = tmp_path / "bad-transcript.json"
    path.write_text(json.dumps(doc, sort_keys=True), encoding="utf-8")
    with pytest.raises(GlobalProductQualificationV4Error, match="self-contained verifier transcript"):
        verify_global_product_qualification_authority_v4_document(path)


def test_v4_document_cannot_leak_production_authority(tmp_path: Path, monkeypatch):
    authority = _build(tmp_path, monkeypatch)
    doc = authority.document
    doc["production_control_authorized"] = True
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(doc, sort_keys=True), encoding="utf-8")
    with pytest.raises(GlobalProductQualificationV4Error, match="cannot authorize production control"):
        verify_global_product_qualification_authority_v4_document(path)


def test_v4_document_rejects_forged_verifier_population_even_with_rehashed_payload(tmp_path: Path, monkeypatch):
    authority = _build(tmp_path, monkeypatch)
    doc = authority.document
    doc["verifier_principals"] = ["same", "same"]
    doc["distinct_verifier_count"] = 1
    keys = (
        "canonical_family_ids", "family_p19_digests", "v3_authority_digest",
        "verifier_trust_policy_digest", "allowed_signers_sha256", "verifier_principals",
        "distinct_verifier_count", "minimum_distinct_verifiers", "same_verifier_across_families_allowed",
        "repository_commit", "repository_tree", "statistical_plan_digest", "theorem_identity_digest",
        "methodology_anchor_digest", "global_statistical_composition_rule", "all_family_p19_complete",
        "all_family_p19_externally_verified", "product_qualified", "production_control_authorized",
    )
    from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes
    doc["authority_digest"] = sha256_bytes(canonical_json_bytes({key: doc[key] for key in keys}))
    path = tmp_path / "forged.json"
    path.write_text(json.dumps(doc, sort_keys=True), encoding="utf-8")
    with pytest.raises(GlobalProductQualificationV4Error, match="distinct verifier threshold"):
        verify_global_product_qualification_authority_v4_document(path)
