from __future__ import annotations

import json
from pathlib import Path

import pytest

from cwc.governance.external_evidence_reference import (
    ExternalEvidenceError,
    verify_materialization_generation,
)
from cwc.governance.materialization_transaction import AtomicEvidenceGeneration

COMMIT = "a" * 40
TREE = "b" * 40
REGISTRY = "c" * 64
MATERIALIZER = "d" * 64
SOURCE_AUTH_SWE = "1" * 64
SOURCE_AUTH_TB = "2" * 64
MATERIALIZED_AUTH_SWE = "e" * 64
MATERIALIZED_AUTH_TB = "f" * 64


def _make_generation(tmp_path: Path, *, promotion: bool = False, families: tuple[str, ...] = ("SWE_BENCH_VERIFIED", "TERMINAL_BENCH_2_1")) -> Path:
    root = tmp_path / "generation"
    with AtomicEvidenceGeneration(root) as tx:
        assert tx.staging_root is not None
        (tx.staging_root / "SWE_BENCH_VERIFIED").mkdir()
        (tx.staging_root / "SWE_BENCH_VERIFIED" / "payload.bin").write_bytes(b"swe")
        (tx.staging_root / "TERMINAL_BENCH_2_1").mkdir()
        (tx.staging_root / "TERMINAL_BENCH_2_1" / "payload.bin").write_bytes(b"terminal")
        source_authority = {"SWE_BENCH_VERIFIED": SOURCE_AUTH_SWE, "TERMINAL_BENCH_2_1": SOURCE_AUTH_TB}
        materialized_authority = {"SWE_BENCH_VERIFIED": MATERIALIZED_AUTH_SWE, "TERMINAL_BENCH_2_1": MATERIALIZED_AUTH_TB}
        receipt = {
            "schema": "DGC_EXTERNAL_MATERIALIZATION_RECEIPT_V2",
            "families": [
                {
                    "family_id": family,
                    "stage": "MATERIALIZED_VERIFIED",
                    "source_authority_digest": source_authority[family],
                    "authority_digest": materialized_authority[family],
                }
                for family in families
            ],
            "source_registry_sha256": REGISTRY,
            "repository_commit": COMMIT,
            "repository_tree": TREE,
            "materializer_sha256": MATERIALIZER,
            "execution_authorized": False,
            "product_promotion_authorized": promotion,
        }
        provenance = {
            "schema": "DGC_MATERIALIZATION_PROVENANCE_V1",
            "claim": "VERIFIED_MATERIALIZATION_ONLY",
            "repository": {"git_commit": COMMIT, "git_tree": TREE},
            "materials": {
                "external_source_registry_sha256": REGISTRY,
                "materializer_sha256": MATERIALIZER,
                "source_authority_digests": sorted(source_authority[family] for family in families),
            },
            "slsa_conformance_claim": False,
            "execution_authorized": False,
            "product_promotion_authorized": False,
        }
        tx.publish(receipt=receipt, provenance=provenance)
    return root


def test_valid_materialization_generation_mints_portable_subject_reference(tmp_path: Path):
    root = _make_generation(tmp_path)
    reference = verify_materialization_generation(
        root,
        expected_repository_commit=COMMIT,
        expected_repository_tree=TREE,
    )
    assert reference.repository_commit == COMMIT
    assert reference.repository_tree == TREE
    assert reference.payload_manifest_sha256 == json.loads((root / "GENERATION_MANIFEST.json").read_text())["payload_manifest_sha256"]
    assert len(reference.family_source_authority_digests) == 2
    assert len(reference.family_materialized_authority_digests) == 2
    assert reference.family_source_authority_digests != reference.family_materialized_authority_digests
    assert len(reference.digest) == 64


def test_payload_tamper_after_publish_is_rejected(tmp_path: Path):
    root = _make_generation(tmp_path)
    (root / "SWE_BENCH_VERIFIED" / "payload.bin").write_bytes(b"tampered")
    with pytest.raises(ExternalEvidenceError, match="publication file manifest mismatch"):
        verify_materialization_generation(root, expected_repository_commit=COMMIT, expected_repository_tree=TREE)


def test_added_file_after_publish_is_rejected(tmp_path: Path):
    root = _make_generation(tmp_path)
    (root / "injected.bin").write_bytes(b"injected")
    with pytest.raises(ExternalEvidenceError, match="publication file manifest mismatch"):
        verify_materialization_generation(root, expected_repository_commit=COMMIT, expected_repository_tree=TREE)


def test_illegal_product_promotion_bit_is_rejected_even_when_self_consistent(tmp_path: Path):
    root = _make_generation(tmp_path, promotion=True)
    with pytest.raises(ExternalEvidenceError, match="illegally grants downstream authority"):
        verify_materialization_generation(root, expected_repository_commit=COMMIT, expected_repository_tree=TREE)


def test_wrong_repository_identity_is_rejected(tmp_path: Path):
    root = _make_generation(tmp_path)
    with pytest.raises(ExternalEvidenceError, match="repository identity mismatch"):
        verify_materialization_generation(root, expected_repository_commit="1" * 40, expected_repository_tree=TREE)


def test_missing_frozen_family_is_rejected(tmp_path: Path):
    root = _make_generation(tmp_path, families=("SWE_BENCH_VERIFIED",))
    with pytest.raises(ExternalEvidenceError, match="exactly both frozen workload families"):
        verify_materialization_generation(root, expected_repository_commit=COMMIT, expected_repository_tree=TREE)


def test_source_authority_provenance_cannot_be_substituted_with_materialized_authority(tmp_path: Path):
    root = _make_generation(tmp_path)
    # Build a new self-consistent generation with the wrong authority layer in provenance.
    bad = tmp_path / "bad-generation"
    receipt = json.loads((root / "MATERIALIZATION_RECEIPT.json").read_text())
    provenance = json.loads((root / "MATERIALIZATION_PROVENANCE.json").read_text())
    provenance["materials"]["source_authority_digests"] = sorted(
        row["authority_digest"] for row in receipt["families"]
    )
    with AtomicEvidenceGeneration(bad) as tx:
        assert tx.staging_root is not None
        (tx.staging_root / "SWE_BENCH_VERIFIED").mkdir()
        (tx.staging_root / "SWE_BENCH_VERIFIED" / "payload.bin").write_bytes(b"swe")
        (tx.staging_root / "TERMINAL_BENCH_2_1").mkdir()
        (tx.staging_root / "TERMINAL_BENCH_2_1" / "payload.bin").write_bytes(b"terminal")
        # Remove old payload binding; transaction recomputes it.
        receipt.pop("payload_manifest_sha256", None)
        provenance.pop("payload_manifest_sha256", None)
        tx.publish(receipt=receipt, provenance=provenance)
    with pytest.raises(ExternalEvidenceError, match="source authority provenance mismatch"):
        verify_materialization_generation(bad, expected_repository_commit=COMMIT, expected_repository_tree=TREE)


def test_generation_root_symlink_is_rejected(tmp_path: Path):
    root = _make_generation(tmp_path)
    link = tmp_path / "generation-link"
    link.symlink_to(root, target_is_directory=True)
    with pytest.raises(ExternalEvidenceError, match="symlink"):
        verify_materialization_generation(link, expected_repository_commit=COMMIT, expected_repository_tree=TREE)
