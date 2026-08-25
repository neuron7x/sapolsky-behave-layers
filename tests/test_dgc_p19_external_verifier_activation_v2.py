from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from cwc.governance.materialization_transaction import canonical_json_bytes
from cwc.governance.p19_external_verifier_activation_v2 import (
    P19ExternalVerifierActivationV2Error,
    SIGNATURE_SEMANTICS,
    build_p19_external_verifier_activation_authority_v2,
    verify_p19_external_verifier_activation_authority_v2_document,
)
from cwc.governance.p19_verifier_policy import CANONICAL_POLICY_PATH


def _subjects(root: Path) -> tuple[Path, tuple[Path, Path], tuple[Path, Path]]:
    receipt = root / "artifacts/dgc-product-v1/generated/verifier-regression/receipt.json"
    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text("{}\n", encoding="utf-8")
    attestations = (
        root / "artifacts/dgc-product-v1/generated/verifier-regression/a.attestation.json",
        root / "artifacts/dgc-product-v1/generated/verifier-regression/b.attestation.json",
    )
    signatures = (
        root / "artifacts/dgc-product-v1/generated/verifier-regression/a.sig",
        root / "artifacts/dgc-product-v1/generated/verifier-regression/b.sig",
    )
    for index, path in enumerate(attestations):
        path.write_text(f"attestation-{index}\n", encoding="utf-8")
    for index, path in enumerate(signatures):
        path.write_text(f"signature-{index}\n", encoding="utf-8")
    return receipt, attestations, signatures


def _fake_v1(*, local_provenance: str):
    def builder(**kwargs):
        root = Path(kwargs["repository_root"])
        attestations = tuple(Path(value) for value in kwargs["attestation_paths"])
        signatures = tuple(Path(value) for value in kwargs["signature_paths"])
        return SimpleNamespace(
            activation_authorized=True,
            all_signatures_verified=True,
            regression_receipt_path=Path(kwargs["regression_receipt_path"]).relative_to(root).as_posix(),
            regression_receipt_sha256="1" * 64,
            regression_receipt_digest="2" * 64,
            source_commit="3" * 40,
            source_tree="4" * 40,
            runtime_manifest_digest="5" * 64,
            test_manifest_digest="6" * 64,
            method_map_digest="7" * 64,
            trust_policy_path=CANONICAL_POLICY_PATH,
            trust_policy_digest="8" * 64,
            allowed_signers_sha256="9" * 64,
            attestation_paths=tuple(path.relative_to(root).as_posix() for path in attestations),
            signature_paths=tuple(path.relative_to(root).as_posix() for path in signatures),
            verifier_principals=("verifier-a", "verifier-b"),
            signer_key_digests=("a" * 64, "b" * 64),
            signature_receipt_digests=(
                ("c" if local_provenance == "host-a" else "e") * 64,
                ("d" if local_provenance == "host-a" else "f") * 64,
            ),
        )
    return builder


def test_same_cryptographic_inputs_different_local_signature_tool_provenance_same_v2_identity(tmp_path: Path):
    receipt, attestations, signatures = _subjects(tmp_path)
    a = build_p19_external_verifier_activation_authority_v2(
        repository_root=tmp_path,
        regression_receipt_path=receipt,
        attestation_paths=attestations,
        signature_paths=signatures,
        v1_builder=_fake_v1(local_provenance="host-a"),
    )
    b = build_p19_external_verifier_activation_authority_v2(
        repository_root=tmp_path,
        regression_receipt_path=receipt,
        attestation_paths=attestations,
        signature_paths=signatures,
        v1_builder=_fake_v1(local_provenance="host-b"),
    )
    assert a.authority_digest == b.authority_digest
    assert a.document == b.document
    assert a.signature_semantics == SIGNATURE_SEMANTICS
    assert a.signature_tool_execution_provenance_authoritative is False
    assert "signature_receipt_digests" not in a.document


def test_signature_byte_mutation_changes_portable_activation_identity(tmp_path: Path):
    receipt, attestations, signatures = _subjects(tmp_path)
    before = build_p19_external_verifier_activation_authority_v2(
        repository_root=tmp_path,
        regression_receipt_path=receipt,
        attestation_paths=attestations,
        signature_paths=signatures,
        v1_builder=_fake_v1(local_provenance="host-a"),
    )
    signatures[0].write_text("different-signature\n", encoding="utf-8")
    after = build_p19_external_verifier_activation_authority_v2(
        repository_root=tmp_path,
        regression_receipt_path=receipt,
        attestation_paths=attestations,
        signature_paths=signatures,
        v1_builder=_fake_v1(local_provenance="host-a"),
    )
    assert before.authority_digest != after.authority_digest


def test_noncanonical_trust_policy_path_from_v1_validation_is_rejected(tmp_path: Path):
    receipt, attestations, signatures = _subjects(tmp_path)

    def bad_builder(**kwargs):
        value = _fake_v1(local_provenance="host-a")(**kwargs)
        value.trust_policy_path = "artifacts/dgc-product-v1/generated/attacker-policy.json"
        return value

    with pytest.raises(P19ExternalVerifierActivationV2Error, match="canonical trust policy path"):
        build_p19_external_verifier_activation_authority_v2(
            repository_root=tmp_path,
            regression_receipt_path=receipt,
            attestation_paths=attestations,
            signature_paths=signatures,
            v1_builder=bad_builder,
        )


def test_v2_document_replays_to_same_portable_identity(tmp_path: Path):
    receipt, attestations, signatures = _subjects(tmp_path)
    authority = build_p19_external_verifier_activation_authority_v2(
        repository_root=tmp_path,
        regression_receipt_path=receipt,
        attestation_paths=attestations,
        signature_paths=signatures,
        v1_builder=_fake_v1(local_provenance="host-a"),
    )
    path = tmp_path / "artifacts/dgc-product-v1/generated/verifier-regression/activation-v2.json"
    path.write_bytes(canonical_json_bytes(authority.document) + b"\n")
    verified = verify_p19_external_verifier_activation_authority_v2_document(
        path,
        repository_root=tmp_path,
        v1_builder=_fake_v1(local_provenance="host-b"),
    )
    assert verified["authority_digest"] == authority.authority_digest
    assert verified["signature_tool_execution_provenance_authoritative"] is False
