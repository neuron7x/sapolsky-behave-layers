from __future__ import annotations

import hashlib
import json
import os
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
    assert manifest["schema"] == "DGC_EVIDENCE_GENERATION_MANIFEST_V2"
    assert receipt["payload_manifest_sha256"] == published.payload_manifest_sha256
    assert provenance["payload_manifest_sha256"] == published.payload_manifest_sha256
    assert manifest["publication_manifest_sha256"] == published.publication_manifest_sha256
    paths = {row["path"] for row in manifest["files"]}
    assert "family-a/x.bin" in paths
    assert "MATERIALIZATION_RECEIPT.json" in paths
    assert "MATERIALIZATION_PROVENANCE.json" in paths
    assert "GENERATION_MANIFEST.json" not in paths


def test_symlink_is_manifested_as_link_without_dereferencing_target(tmp_path: Path):
    outside = tmp_path / "outside-secret.bin"
    outside.write_bytes(b"external-secret-v1")
    final = tmp_path / "gen-1"
    with AtomicEvidenceGeneration(final) as tx:
        assert tx.staging_root is not None
        os.symlink(outside, tx.staging_root / "escape-link")
        published = tx.publish(receipt={"schema": "R"}, provenance={"schema": "P"})

    manifest = json.loads((final / "GENERATION_MANIFEST.json").read_text())
    row = next(row for row in manifest["files"] if row["path"] == "escape-link")
    target_bytes = os.fsencode(str(outside))
    assert row["type"] == "symlink"
    assert row["bytes"] == len(target_bytes)
    assert row["sha256"] == hashlib.sha256(target_bytes).hexdigest()
    assert row["sha256"] != hashlib.sha256(outside.read_bytes()).hexdigest()
    assert published.file_count == len(manifest["files"])


def test_symlink_target_content_change_does_not_change_generation_payload_digest(tmp_path: Path):
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"v1")
    digests = []
    for index in range(2):
        final = tmp_path / f"gen-link-{index}"
        with AtomicEvidenceGeneration(final) as tx:
            assert tx.staging_root is not None
            os.symlink(outside, tx.staging_root / "link")
            digests.append(
                tx.publish(receipt={"schema": "R"}, provenance={"schema": "P"}).payload_manifest_sha256
            )
        outside.write_bytes(b"v2")
    assert digests[0] == digests[1]


def test_fifo_is_rejected_as_unrepresentable_evidence(tmp_path: Path):
    if not hasattr(os, "mkfifo"):
        pytest.skip("mkfifo unavailable")
    final = tmp_path / "gen-fifo"
    with pytest.raises(ValueError, match="unsupported evidence filesystem object"):
        with AtomicEvidenceGeneration(final) as tx:
            assert tx.staging_root is not None
            os.mkfifo(tx.staging_root / "pipe")
            tx.publish(receipt={"schema": "R"}, provenance={"schema": "P"})
    assert not final.exists()


def test_payload_digest_changes_when_payload_changes(tmp_path: Path):
    digests = []
    for index, content in enumerate((b"a", b"b")):
        final = tmp_path / f"gen-{index}"
        with AtomicEvidenceGeneration(final) as tx:
            assert tx.staging_root is not None
            (tx.staging_root / "payload.bin").write_bytes(content)
            digests.append(tx.publish(receipt={"schema": "R"}, provenance={"schema": "P"}).payload_manifest_sha256)
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
