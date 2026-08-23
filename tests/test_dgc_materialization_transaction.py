from __future__ import annotations

import json
from pathlib import Path

import pytest

from cwc.governance.materialization_transaction import AtomicEvidenceGeneration


def test_failed_generation_never_populates_final_root(tmp_path: Path):
    final = tmp_path / "gen-1"
    with pytest.raises(RuntimeError, match="boom"):
        with AtomicEvidenceGeneration(final) as tx:
            assert tx.staging_root is not None
            (tx.staging_root / "partial.bin").write_bytes(b"partial")
            raise RuntimeError("boom")
    assert not final.exists()
    assert not list(tmp_path.glob(".gen-1.staging-*"))


def test_exit_without_publish_is_fail_closed(tmp_path: Path):
    final = tmp_path / "gen-1"
    with AtomicEvidenceGeneration(final) as tx:
        assert tx.staging_root is not None
        (tx.staging_root / "partial.bin").write_bytes(b"partial")
    assert not final.exists()


def test_publish_is_atomic_and_binds_payload_and_control_files(tmp_path: Path):
    final = tmp_path / "gen-1"
    with AtomicEvidenceGeneration(final) as tx:
        assert tx.staging_root is not None
        (tx.staging_root / "family-a").mkdir()
        (tx.staging_root / "family-a" / "x.bin").write_bytes(b"abc")
        published = tx.publish(
            receipt={"schema": "R", "product_promotion_authorized": False},
            provenance={"schema": "P", "repo_commit": "a" * 40},
        )

    assert published.root == final
    assert final.is_dir()
    receipt = json.loads((final / "MATERIALIZATION_RECEIPT.json").read_text())
    provenance = json.loads((final / "MATERIALIZATION_PROVENANCE.json").read_text())
    manifest = json.loads((final / "GENERATION_MANIFEST.json").read_text())
    assert receipt["payload_manifest_sha256"] == published.payload_manifest_sha256
    assert provenance["payload_manifest_sha256"] == published.payload_manifest_sha256
    assert manifest["publication_manifest_sha256"] == published.publication_manifest_sha256
    paths = {row["path"] for row in manifest["files"]}
    assert "family-a/x.bin" in paths
    assert "MATERIALIZATION_RECEIPT.json" in paths
    assert "MATERIALIZATION_PROVENANCE.json" in paths
    assert "GENERATION_MANIFEST.json" not in paths


def test_payload_digest_changes_when_payload_changes(tmp_path: Path):
    digests = []
    for index, content in enumerate((b"a", b"b")):
        final = tmp_path / f"gen-{index}"
        with AtomicEvidenceGeneration(final) as tx:
            assert tx.staging_root is not None
            (tx.staging_root / "payload.bin").write_bytes(content)
            digests.append(
                tx.publish(receipt={"schema": "R"}, provenance={"schema": "P"}).payload_manifest_sha256
            )
    assert digests[0] != digests[1]


def test_existing_final_root_is_never_overwritten(tmp_path: Path):
    final = tmp_path / "gen-1"
    final.mkdir()
    (final / "keep").write_text("original")
    with pytest.raises(FileExistsError):
        with AtomicEvidenceGeneration(final):
            pass
    assert (final / "keep").read_text() == "original"


def test_reserved_control_file_in_staging_is_rejected(tmp_path: Path):
    final = tmp_path / "gen-1"
    with pytest.raises(ValueError, match="reserved control file"):
        with AtomicEvidenceGeneration(final) as tx:
            assert tx.staging_root is not None
            (tx.staging_root / "MATERIALIZATION_RECEIPT.json").write_text("forged")
            tx.publish(receipt={"schema": "R"}, provenance={"schema": "P"})
    assert not final.exists()
