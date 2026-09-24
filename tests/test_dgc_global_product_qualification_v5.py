from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import cwc.governance.global_product_qualification_v5 as v5
from cwc.governance.global_product_qualification_v4 import FamilyP19VerificationInputV4
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes


def _validated():
    return SimpleNamespace(
        canonical_family_ids=("SWE_BENCH_VERIFIED", "TERMINAL_BENCH_2_1"),
        family_p19_digests=(("SWE_BENCH_VERIFIED", "1" * 64), ("TERMINAL_BENCH_2_1", "2" * 64)),
        repository_commit="a" * 40,
        repository_tree="b" * 40,
        statistical_plan_digest="3" * 64,
        theorem_identity_digest="4" * 64,
        methodology_anchor_digest="5" * 64,
        global_statistical_composition_rule="INTERSECTION_UNION_TWO_FAMILY_AND_V1",
    )


def _p19(family: str, digest: str):
    return {
        "family_id": family,
        "p19_digest": digest,
        "repository_commit": "a" * 40,
        "repository_tree": "b" * 40,
        "statistical_plan_digest": "3" * 64,
        "theorem_identity_digest": "4" * 64,
        "methodology_anchor_digest": "5" * 64,
        "stage_evidence_manifest_digest": "6" * 64,
        "subject_root_manifest_digest": "7" * 64,
        "family_evidence_complete": True,
    }


def _attestation(family: str, digest: str, principal: str):
    return {
        "family_id": family,
        "p19_digest": digest,
        "repository_commit": "a" * 40,
        "repository_tree": "b" * 40,
        "statistical_plan_digest": "3" * 64,
        "theorem_identity_digest": "4" * 64,
        "methodology_anchor_digest": "5" * 64,
        "stage_evidence_manifest_digest": "6" * 64,
        "subject_root_manifest_digest": "7" * 64,
        "verifier_principal": principal,
    }


def _receipt(principal: str, *, tool_salt: str):
    return SimpleNamespace(
        attestation_sha256=("8" if principal == "verifier-a" else "9") * 64,
        verification_report_sha256=("a" if principal == "verifier-a" else "b") * 64,
        signature_sha256=("c" if principal == "verifier-a" else "d") * 64,
        allowed_signers_sha256="e" * 64,
        principal=principal,
        namespace=v5.NAMESPACE,
        ssh_keygen_path=f"/tool/{tool_salt}/ssh-keygen",
        ssh_keygen_sha256=("f" if tool_salt == "one" else "0") * 64,
        stdout_sha256=("1" if tool_salt == "one" else "2") * 64,
        stderr_sha256=("3" if tool_salt == "one" else "4") * 64,
        signature_verified=True,
    )


def _build(monkeypatch, tmp_path: Path, *, tool_salt: str):
    policy = SimpleNamespace(
        policy_digest="f" * 64,
        allowed_signers_sha256="e" * 64,
        minimum_distinct_verifiers=2,
    )
    monkeypatch.setattr(v5, "load_p19_verifier_trust_policy", lambda path: policy)
    monkeypatch.setattr(v5, "resolve_allowed_signers", lambda policy, repository_root: tmp_path / "allowed_signers")
    monkeypatch.setattr(v5, "build_global_product_qualification_authority_v4", lambda **kwargs: _validated())
    docs = [
        _p19("SWE_BENCH_VERIFIED", "1" * 64),
        _p19("TERMINAL_BENCH_2_1", "2" * 64),
    ]
    iterator = iter(docs)
    monkeypatch.setattr(v5, "verify_family_p19_evidence_root_document", lambda path: next(iterator))

    calls = {"n": 0}

    def verifier(**kwargs):
        index = calls["n"]
        calls["n"] += 1
        if index == 0:
            return _attestation("SWE_BENCH_VERIFIED", "1" * 64, "verifier-a"), _receipt("verifier-a", tool_salt=tool_salt)
        return _attestation("TERMINAL_BENCH_2_1", "2" * 64, "verifier-b"), _receipt("verifier-b", tool_salt=tool_salt)

    monkeypatch.setattr(v5, "verify_ssh_signed_p19_verification_attestation", verifier)
    inputs = (
        FamilyP19VerificationInputV4(Path("a.json"), Path("a-report.json"), Path("a.sig")),
        FamilyP19VerificationInputV4(Path("b.json"), Path("b-report.json"), Path("b.sig")),
    )
    return v5.build_global_product_qualification_authority_v5(
        repository_root=tmp_path,
        source_registry_path=tmp_path / "registry.json",
        family_p19_paths=(tmp_path / "a-p19.json", tmp_path / "b-p19.json"),
        family_p19_verification_inputs=inputs,
        p19_verifier_policy_path=tmp_path / "policy.json",
    )


def _mutable_document(authority) -> dict[str, object]:
    return json.loads(json.dumps(authority.document))


def _write_doc(path: Path, doc: dict[str, object]) -> None:
    path.write_bytes(canonical_json_bytes(doc) + b"\n")


def _rehash_authority(doc: dict[str, object]) -> None:
    keys = (
        "canonical_family_ids", "family_p19_digests", "stable_family_verification_records",
        "verifier_trust_policy_digest", "allowed_signers_sha256", "verifier_principals",
        "distinct_verifier_count", "minimum_distinct_verifiers", "repository_commit", "repository_tree",
        "statistical_plan_digest", "theorem_identity_digest", "methodology_anchor_digest",
        "global_statistical_composition_rule", "signature_semantics",
        "signature_tool_execution_provenance_authoritative", "all_family_p19_complete",
        "all_family_p19_externally_verified", "product_qualified", "production_control_authorized",
    )
    doc["authority_digest"] = sha256_bytes(canonical_json_bytes({key: doc[key] for key in keys}))


def test_global_v5_authority_identity_is_independent_of_signature_verifier_binary(monkeypatch, tmp_path: Path):
    first = _build(monkeypatch, tmp_path, tool_salt="one")
    second = _build(monkeypatch, tmp_path, tool_salt="two")
    assert first.authority_digest == second.authority_digest
    assert first.stable_family_verification_records == second.stable_family_verification_records
    assert first.signature_tool_execution_provenance_authoritative is False
    assert first.signature_semantics == v5.SIGNATURE_SEMANTICS


def test_v5_structural_verifier_rejects_cross_population_p19_substitution_even_if_authority_is_rehashed(monkeypatch, tmp_path: Path):
    authority = _build(monkeypatch, tmp_path, tool_salt="one")
    doc = _mutable_document(authority)
    doc["family_p19_digests"][0][1] = "f" * 64
    _rehash_authority(doc)
    path = tmp_path / "forged-p19.json"
    _write_doc(path, doc)
    with pytest.raises(v5.GlobalProductQualificationV5Error, match="different family P19 root"):
        v5.verify_global_product_qualification_authority_v5_document(path)


def test_v5_structural_verifier_rejects_top_level_principal_substitution_even_if_authority_is_rehashed(monkeypatch, tmp_path: Path):
    authority = _build(monkeypatch, tmp_path, tool_salt="one")
    doc = _mutable_document(authority)
    doc["verifier_principals"] = ["verifier-a", "attacker"]
    _rehash_authority(doc)
    path = tmp_path / "forged-principal.json"
    _write_doc(path, doc)
    with pytest.raises(v5.GlobalProductQualificationV5Error, match="top-level verifier principals differ"):
        v5.verify_global_product_qualification_authority_v5_document(path)


def test_v5_structural_verifier_rejects_row_trust_store_substitution_with_valid_row_and_authority_digests(monkeypatch, tmp_path: Path):
    authority = _build(monkeypatch, tmp_path, tool_salt="one")
    doc = _mutable_document(authority)
    row = doc["stable_family_verification_records"][0]
    row["allowed_signers_sha256"] = "0" * 64
    row_keys = (
        "family_id", "p19_digest", "verifier_principal", "attestation_sha256",
        "verification_report_sha256", "signature_sha256", "allowed_signers_sha256", "namespace",
        "signature_verified", "semantic_replay_attested", "social_independence_machine_proven",
    )
    row["record_digest"] = sha256_bytes(canonical_json_bytes({key: row[key] for key in row_keys}))
    _rehash_authority(doc)
    path = tmp_path / "forged-trust-store.json"
    _write_doc(path, doc)
    with pytest.raises(v5.GlobalProductQualificationV5Error, match="different trust store"):
        v5.verify_global_product_qualification_authority_v5_document(path)
