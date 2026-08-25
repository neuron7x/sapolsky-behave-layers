from __future__ import annotations

import json
from pathlib import Path

import pytest

import cwc.governance.p19_external_verification_plan as plan_mod
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.p19_external_verification_contract import (
    CHECK_METHOD_IDS,
    REGRESSION_TEST_FILES,
    VERIFIER_ENTRYPOINT,
    VERIFIER_RUNTIME_DEPENDENCIES,
)
from cwc.governance.p19_external_verification_plan import (
    PLAN_GENERATION,
    SCHEMA,
    P19ExternalVerificationPlanError,
    build_activated_p19_external_verification_plan_document,
    build_inactive_p19_external_verification_plan_document,
    load_p19_external_verification_plan,
)
from cwc.governance.p19_external_verifier_regression import current_runtime_digest, current_test_manifest_digest
from cwc.governance.p19_verification_check_receipt import REQUIRED_CHECKS


PAYLOAD_KEYS = (
    "plan_generation", "frozen_pre_outcome", "activation_authorized", "activation_evidence_requirement",
    "verifier_entrypoint_path", "verifier_entrypoint_sha256",
    "verifier_dependency_manifest_digest", "verifier_dependencies", "check_contracts",
    "all_check_implementations_complete", "activation_authority_path", "activation_authority_sha256",
    "activation_authority_digest", "activation_trust_policy_path", "activation_trust_policy_digest",
    "activation_verifier_principals", "activation_signer_key_digests",
    "activation_regression_receipt_path", "activation_regression_receipt_sha256",
    "activation_regression_receipt_digest", "activation_regression_source_commit",
    "activation_regression_source_tree", "activation_regression_test_manifest_digest",
    "product_qualification_authorized",
)


def _runtime_and_tests(root: Path) -> None:
    entry = root / VERIFIER_ENTRYPOINT
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text("print('verifier')\n", encoding="utf-8")
    for rel in VERIFIER_RUNTIME_DEPENDENCIES:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# frozen dependency: {rel}\n", encoding="utf-8")
    for rel in REGRESSION_TEST_FILES:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# frozen regression test: {rel}\n", encoding="utf-8")


def _write(path: Path, doc: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(doc) + b"\n")


def _redigest(doc: dict[str, object]) -> None:
    doc["plan_digest"] = sha256_bytes(canonical_json_bytes({key: doc[key] for key in PAYLOAD_KEYS}))


def _inactive_doc(root: Path) -> dict[str, object]:
    _runtime_and_tests(root)
    return build_inactive_p19_external_verification_plan_document(
        repository_root=root,
        implemented_check_ids=tuple(sorted(REQUIRED_CHECKS)),
    )


def _activation_doc(root: Path, authority_path: Path) -> dict[str, object]:
    return {
        "schema": "DGC_P19_EXTERNAL_VERIFIER_ACTIVATION_AUTHORITY_V1",
        "activation_authorized": True,
        "all_signatures_verified": True,
        "authority_digest": "a" * 64,
        "trust_policy_path": "artifacts/dgc-product-v1/P19_VERIFIER_TRUST_POLICY_V2.json",
        "trust_policy_digest": "b" * 64,
        "verifier_principals": ["verifier-a", "verifier-b"],
        "signer_key_digests": ["c" * 64, "d" * 64],
        "regression_receipt_path": "artifacts/dgc-product-v1/generated/regression/receipt.json",
        "regression_receipt_sha256": "e" * 64,
        "regression_receipt_digest": "f" * 64,
        "source_commit": "1" * 40,
        "source_tree": "2" * 40,
        "runtime_manifest_digest": current_runtime_digest(root),
        "test_manifest_digest": current_test_manifest_digest(root),
        "method_map_digest": "3" * 64,
    }


def _active_doc(root: Path, monkeypatch) -> tuple[dict[str, object], Path]:
    _runtime_and_tests(root)
    authority_path = root / "artifacts/dgc-product-v1/generated/regression/activation.json"
    authority_path.parent.mkdir(parents=True, exist_ok=True)
    authority_path.write_bytes(b"activation-authority\n")
    authority = _activation_doc(root, authority_path)
    monkeypatch.setattr(plan_mod, "verify_p19_external_verifier_activation_authority_document", lambda *args, **kwargs: authority)
    return build_activated_p19_external_verification_plan_document(
        repository_root=root,
        activation_authority_path=authority_path.relative_to(root),
    ), authority_path


def test_inactive_builder_content_addresses_exact_implemented_surface(tmp_path: Path):
    document = _inactive_doc(tmp_path)
    assert document["schema"] == SCHEMA
    assert document["plan_generation"] == PLAN_GENERATION
    assert document["activation_authorized"] is False
    assert document["activation_evidence_requirement"] == "DUAL_EXTERNAL_SSH_SIGNED_GIT_BOUND_CANONICAL_REGRESSION_V1"
    assert document["all_check_implementations_complete"] is True
    assert document["product_qualification_authorized"] is False
    assert {row["method_id"] for row in document["check_contracts"]} == set(CHECK_METHOD_IDS.values())
    for field in (
        "activation_authority_path", "activation_authority_sha256", "activation_authority_digest",
        "activation_trust_policy_path", "activation_trust_policy_digest",
        "activation_regression_receipt_path", "activation_regression_receipt_sha256",
        "activation_regression_receipt_digest", "activation_regression_source_commit",
        "activation_regression_source_tree", "activation_regression_test_manifest_digest",
    ):
        assert document[field] is None
    assert document["activation_verifier_principals"] == []
    assert document["activation_signer_key_digests"] == []
    path = tmp_path / "plan.json"
    _write(path, document)
    loaded = load_p19_external_verification_plan(path, repository_root=tmp_path, require_active=False)
    assert loaded.plan_digest == document["plan_digest"]
    assert loaded.activation_authorized is False
    with pytest.raises(P19ExternalVerificationPlanError, match="not activated"):
        load_p19_external_verification_plan(path, repository_root=tmp_path, require_active=True)


def test_inactive_builder_rejects_incomplete_or_duplicate_handler_population(tmp_path: Path):
    _runtime_and_tests(tmp_path)
    missing = tuple(sorted(REQUIRED_CHECKS - {"P19_SEAL_REBUILD"}))
    with pytest.raises(P19ExternalVerificationPlanError, match="exact unique implemented check population"):
        build_inactive_p19_external_verification_plan_document(repository_root=tmp_path, implemented_check_ids=missing)
    duplicate = tuple(sorted(REQUIRED_CHECKS)) + ("REPOSITORY_IDENTITY",)
    with pytest.raises(P19ExternalVerificationPlanError, match="exact unique implemented check population"):
        build_inactive_p19_external_verification_plan_document(repository_root=tmp_path, implemented_check_ids=duplicate)


def test_active_plan_requires_dual_signed_activation_authority(tmp_path: Path, monkeypatch):
    path = tmp_path / "plan.json"
    doc, authority_path = _active_doc(tmp_path, monkeypatch)
    _write(path, doc)
    plan = load_p19_external_verification_plan(path, repository_root=tmp_path)
    assert plan.activation_authorized is True
    assert plan.activation_authority_path == authority_path.relative_to(tmp_path).as_posix()
    assert plan.activation_authority_sha256 == sha256_file(authority_path)
    assert plan.activation_verifier_principals == ("verifier-a", "verifier-b")
    assert len(set(plan.activation_signer_key_digests)) == 2
    assert plan.activation_regression_receipt_digest == "f" * 64


def test_active_builder_without_activation_authority_fails_closed(tmp_path: Path):
    _runtime_and_tests(tmp_path)
    with pytest.raises(TypeError):
        build_activated_p19_external_verification_plan_document(repository_root=tmp_path)  # type: ignore[call-arg]


def test_forged_active_flag_without_activation_authority_fails_closed(tmp_path: Path):
    path = tmp_path / "plan.json"
    doc = _inactive_doc(tmp_path)
    doc["activation_authorized"] = True
    _redigest(doc)
    _write(path, doc)
    with pytest.raises(P19ExternalVerificationPlanError):
        load_p19_external_verification_plan(path, repository_root=tmp_path)


def test_inactive_plan_cannot_carry_dormant_activation_evidence(tmp_path: Path):
    path = tmp_path / "plan.json"
    doc = _inactive_doc(tmp_path)
    doc["activation_authority_path"] = "artifacts/dgc-product-v1/generated/forged.json"
    _redigest(doc)
    _write(path, doc)
    with pytest.raises(P19ExternalVerificationPlanError, match="cannot carry activation evidence"):
        load_p19_external_verification_plan(path, repository_root=tmp_path, require_active=False)


def test_plan_generation_substitution_fails_even_with_rehashed_plan(tmp_path: Path):
    path = tmp_path / "plan.json"
    doc = _inactive_doc(tmp_path)
    doc["plan_generation"] = "POST_OUTCOME_RELABELED_PLAN"
    _redigest(doc)
    _write(path, doc)
    with pytest.raises(P19ExternalVerificationPlanError, match="generation mismatch"):
        load_p19_external_verification_plan(path, repository_root=tmp_path, require_active=False)


def test_verifier_runtime_mutation_invalidates_inactive_plan(tmp_path: Path):
    path = tmp_path / "plan.json"
    doc = _inactive_doc(tmp_path)
    _write(path, doc)
    (tmp_path / VERIFIER_ENTRYPOINT).write_text("print('mutated')\n", encoding="utf-8")
    with pytest.raises(P19ExternalVerificationPlanError, match="entrypoint bytes differ"):
        load_p19_external_verification_plan(path, repository_root=tmp_path, require_active=False)


def test_activation_authority_runtime_mismatch_blocks_active_plan(tmp_path: Path, monkeypatch):
    _runtime_and_tests(tmp_path)
    authority_path = tmp_path / "artifacts/dgc-product-v1/generated/regression/activation.json"
    authority_path.parent.mkdir(parents=True, exist_ok=True)
    authority_path.write_bytes(b"activation\n")
    authority = _activation_doc(tmp_path, authority_path)
    authority["runtime_manifest_digest"] = "9" * 64
    monkeypatch.setattr(plan_mod, "verify_p19_external_verifier_activation_authority_document", lambda *args, **kwargs: authority)
    with pytest.raises(P19ExternalVerificationPlanError, match="runtime no longer matches"):
        build_activated_p19_external_verification_plan_document(
            repository_root=tmp_path,
            activation_authority_path=authority_path.relative_to(tmp_path),
        )


def test_method_identity_substitution_fails_even_with_rehashed_plan(tmp_path: Path):
    path = tmp_path / "plan.json"
    doc = _inactive_doc(tmp_path)
    seal = next(row for row in doc["check_contracts"] if row["check_id"] == "P19_SEAL_REBUILD")
    seal["method_id"] = "DGC_P19_EXTERNAL_SEAL_REBUILD_V1"
    _redigest(doc)
    _write(path, doc)
    with pytest.raises(P19ExternalVerificationPlanError, match="method identity mismatch: P19_SEAL_REBUILD"):
        load_p19_external_verification_plan(path, repository_root=tmp_path, require_active=False)


def test_command_template_substitution_fails_even_with_rehashed_plan(tmp_path: Path):
    path = tmp_path / "plan.json"
    doc = _inactive_doc(tmp_path)
    doc["check_contracts"][0]["command_template"] = ["echo", "PASS"]
    _redigest(doc)
    _write(path, doc)
    with pytest.raises(P19ExternalVerificationPlanError, match="command template mismatch"):
        load_p19_external_verification_plan(path, repository_root=tmp_path, require_active=False)
