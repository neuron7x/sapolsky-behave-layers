from __future__ import annotations

import json
from pathlib import Path

import pytest

import cwc.governance.global_product_qualification as gpq
from cwc.governance.global_product_qualification import (
    FamilyP19VerificationInput,
    GlobalProductQualificationError,
    build_global_product_qualification_authority,
    verify_global_product_qualification_authority_document,
)
from cwc.governance.p19_verification_attestation import P19VerificationSignatureReceipt


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
        "stage_evidence_manifest_digest": "6" * 64,
        "subject_root_manifest_digest": "7" * 64,
    }


def _verification_input(tmp_path: Path, stem: str) -> FamilyP19VerificationInput:
    return FamilyP19VerificationInput(
        attestation_path=tmp_path / f"{stem}.attestation.json",
        verification_report_path=tmp_path / f"{stem}.report.json",
        signature_path=tmp_path / f"{stem}.sig",
        allowed_signers_path=tmp_path / f"{stem}.allowed",
    )


def _patch_family_docs(monkeypatch, docs: dict[str, dict[str, object]]):
    monkeypatch.setattr(gpq, "verify_family_p19_evidence_root_document", lambda path: docs[Path(path).name])
    monkeypatch.setattr(gpq, "_rehash_family_p19_subjects", lambda doc, repository_root: None)
    monkeypatch.setattr(gpq, "_verify_family_generalization_error_budget", lambda doc, repository_root: None)


def _fake_verifier_for(docs: dict[str, dict[str, object]], *, wrong_p19_for: str | None = None):
    by_stem = {
        Path(name).stem: doc for name, doc in docs.items()
    }

    def verifier(*, attestation_path, verification_report_path, signature_path, allowed_signers_path):
        stem = Path(attestation_path).name.split(".attestation.json")[0]
        p19 = by_stem[stem]
        p19_digest = "f" * 64 if stem == wrong_p19_for else str(p19["p19_digest"])
        attestation = {
            "family_id": p19["family_id"],
            "p19_digest": p19_digest,
            "repository_commit": p19["repository_commit"],
            "repository_tree": p19["repository_tree"],
            "statistical_plan_digest": p19["statistical_plan_digest"],
            "theorem_identity_digest": p19["theorem_identity_digest"],
            "methodology_anchor_digest": p19["methodology_anchor_digest"],
            "stage_evidence_manifest_digest": p19["stage_evidence_manifest_digest"],
            "subject_root_manifest_digest": p19["subject_root_manifest_digest"],
            "verifier_principal": f"verifier-{stem}",
        }
        receipt = P19VerificationSignatureReceipt(
            attestation_sha256="8" * 64,
            verification_report_sha256="9" * 64,
            signature_sha256="a" * 64,
            allowed_signers_sha256="b" * 64,
            principal=f"verifier-{stem}",
            namespace="dgc-p19-external-verification-v1",
            ssh_keygen_path="/usr/bin/ssh-keygen",
            ssh_keygen_sha256="c" * 64,
            stdout_sha256="d" * 64,
            stderr_sha256="e" * 64,
            signature_verified=True,
        )
        return attestation, receipt

    return verifier


def _inputs(tmp_path: Path):
    return (_verification_input(tmp_path, "swe"), _verification_input(tmp_path, "terminal"))


def test_global_authority_requires_exact_two_canonical_families_under_one_methodology_and_signed_p19_replay(tmp_path: Path, monkeypatch):
    docs = {
        "swe.json": _p19("SWE_BENCH_VERIFIED", "a" * 64),
        "terminal.json": _p19("TERMINAL_BENCH_2_1", "b" * 64),
    }
    _patch_family_docs(monkeypatch, docs)
    authority = build_global_product_qualification_authority(
        repository_root=tmp_path,
        source_registry_path=_registry(tmp_path),
        family_p19_paths=(tmp_path / "swe.json", tmp_path / "terminal.json"),
        family_p19_verification_inputs=_inputs(tmp_path),
        p19_attestation_verifier=_fake_verifier_for(docs),
    )
    assert authority.canonical_family_ids == ("SWE_BENCH_VERIFIED", "TERMINAL_BENCH_2_1")
    assert authority.product_qualified is True
    assert authority.production_control_authorized is False
    assert authority.all_family_p19_externally_verified is True
    assert authority.global_statistical_composition_rule == gpq.GLOBAL_STATISTICAL_COMPOSITION_RULE
    assert authority.generalization_claim_count_per_family == 60
    assert authority.generalization_per_family_fwer == pytest.approx(0.05)
    assert len(authority.family_p19_verification_records) == 2

    path = tmp_path / "global.json"
    path.write_text(json.dumps(authority.document, sort_keys=True))
    verified = verify_global_product_qualification_authority_document(path)
    assert verified["global_product_qualification_authorized"] is True
    assert verified["external_p19_semantic_replay_attestation_required"] is True
    assert verified["production_provider_trace_supported"] is False


def test_self_consistent_green_p19_without_valid_external_replay_attestation_fails_closed(tmp_path: Path, monkeypatch):
    docs = {
        "swe.json": _p19("SWE_BENCH_VERIFIED", "a" * 64),
        "terminal.json": _p19("TERMINAL_BENCH_2_1", "b" * 64),
    }
    _patch_family_docs(monkeypatch, docs)

    def rejected(**kwargs):
        raise RuntimeError("signature/replay unavailable")

    with pytest.raises(GlobalProductQualificationError, match="external P19 semantic-verification attestation failed"):
        build_global_product_qualification_authority(
            repository_root=tmp_path,
            source_registry_path=_registry(tmp_path),
            family_p19_paths=(tmp_path / "swe.json", tmp_path / "terminal.json"),
            family_p19_verification_inputs=_inputs(tmp_path),
            p19_attestation_verifier=rejected,
        )


def test_attestation_bound_to_different_p19_fails_closed(tmp_path: Path, monkeypatch):
    docs = {
        "swe.json": _p19("SWE_BENCH_VERIFIED", "a" * 64),
        "terminal.json": _p19("TERMINAL_BENCH_2_1", "b" * 64),
    }
    _patch_family_docs(monkeypatch, docs)
    with pytest.raises(GlobalProductQualificationError, match="external P19 semantic-verification attestation failed"):
        build_global_product_qualification_authority(
            repository_root=tmp_path,
            source_registry_path=_registry(tmp_path),
            family_p19_paths=(tmp_path / "swe.json", tmp_path / "terminal.json"),
            family_p19_verification_inputs=_inputs(tmp_path),
            p19_attestation_verifier=_fake_verifier_for(docs, wrong_p19_for="terminal"),
        )


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
            family_p19_verification_inputs=_inputs(tmp_path),
            p19_attestation_verifier=_fake_verifier_for(docs),
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
            family_p19_verification_inputs=(
                _verification_input(tmp_path, "one"), _verification_input(tmp_path, "two")
            ),
            p19_attestation_verifier=_fake_verifier_for(docs),
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
            family_p19_verification_inputs=_inputs(tmp_path),
            p19_attestation_verifier=_fake_verifier_for(docs),
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
        family_p19_verification_inputs=_inputs(tmp_path),
        p19_attestation_verifier=_fake_verifier_for(docs),
    )
    doc = authority.document
    doc["production_control_authorized"] = True
    path = tmp_path / "bad-global.json"
    path.write_text(json.dumps(doc, sort_keys=True))
    with pytest.raises(GlobalProductQualificationError, match="cannot authorize production control"):
        verify_global_product_qualification_authority_document(path)
