import hashlib
import os
import random
from pathlib import Path

import pytest

from cwc.governance import evidence_bundle
from cwc.governance.evidence_bundle import (
    REQUIRED_PRODUCT_EVIDENCE_FILES,
    verify_evidence_bundle,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _seal(root: Path) -> tuple[Path, list[str]]:
    root.mkdir(exist_ok=True)
    rows = []
    for name in REQUIRED_PRODUCT_EVIDENCE_FILES[:-1]:
        path = root / name
        path.write_text(f"{name}\n", encoding="utf-8")
        rows.append(f"{_sha(path)}  {name}\n")
    manifest = root / "SHA256SUMS"
    manifest.write_text("".join(rows), encoding="utf-8")
    return manifest, rows


def test_missing_bundle_is_incomplete(tmp_path):
    result = verify_evidence_bundle(tmp_path)
    assert not result.complete
    assert "PREREGISTRATION.md" in result.missing_files
    assert "SHA256SUMS" in result.missing_files


def test_complete_hash_sealed_bundle_passes(tmp_path):
    _seal(tmp_path)
    result = verify_evidence_bundle(tmp_path)
    assert result.complete
    assert not result.hash_mismatches
    assert not result.unhashed_files


def test_tampered_bundle_fails(tmp_path):
    _seal(tmp_path)
    (tmp_path / "economics.json").write_text("tampered\n", encoding="utf-8")
    result = verify_evidence_bundle(tmp_path)
    assert not result.complete
    assert "economics.json" in result.hash_mismatches


def test_v1_canonical_extensions_and_permutations(tmp_path):
    manifest, rows = _seal(tmp_path)
    extra = tmp_path / "nested" / "results.json"
    extra.parent.mkdir()
    extra.write_bytes(b"{}\n")
    rows.append(f"{_sha(extra)} *nested/results.json\n")
    generator = random.Random(31)
    observed = set()
    for _ in range(8):
        generator.shuffle(rows)
        manifest.write_text("".join(rows), encoding="utf-8")
        digest = _sha(manifest)
        result = verify_evidence_bundle(tmp_path, expected_manifest_sha256=digest)
        assert result.complete
        assert result.manifest_sha256 == digest
        assert result.manifest_profile == "cwc-dgc-sha256sums/1"
        observed.add(digest)
    assert len(observed) == 8


@pytest.mark.parametrize(
    "invalid_name",
    [
        "economics.json",  # Repeated identical rows violate unique membership.
        "ECONOMICS.json",
        "economics.json/nested.json",
        "nested/./results.json",
        "nested//results.json",
        "nested\\results.json",
        "results.json.",
        "CON.json",
        "SHA256SUMS",
        "../outside.txt",
        "/outside.txt",
    ],
)
def test_invalid_manifest_membership_stops_before_any_payload_open(tmp_path, monkeypatch, invalid_name):
    manifest, rows = _seal(tmp_path)
    digest = _sha(tmp_path / "economics.json")
    manifest.write_text("".join(rows) + f"{digest}  {invalid_name}\n", encoding="utf-8")
    real_open = os.open
    opened = []

    def record_open(path, flags, *, dir_fd=None):
        opened.append(path)
        return real_open(path, flags, dir_fd=dir_fd)

    with monkeypatch.context() as patch:
        patch.setattr(evidence_bundle.os, "open", record_open)
        result = verify_evidence_bundle(tmp_path)
    assert not result.complete
    assert result.hash_mismatches == ("MALFORMED_SHA256SUMS",)
    assert opened == [tmp_path, "SHA256SUMS"]


def test_duplicate_with_distinct_digests_rejected_in_either_order(tmp_path):
    manifest, rows = _seal(tmp_path)
    conflicting = f"{'0' * 64}  economics.json\n"
    for lines in ([conflicting, *rows], [*rows, conflicting]):
        manifest.write_text("".join(lines), encoding="utf-8")
        assert not verify_evidence_bundle(tmp_path).complete


@pytest.mark.parametrize("invalid", [b"x", b"\xff", b"F" * 64 + b"  example.json\n"])
def test_digest_and_text_syntax_rejected(tmp_path, invalid):
    manifest, rows = _seal(tmp_path)
    manifest.write_bytes("".join(rows).encode("ascii") + invalid)
    assert verify_evidence_bundle(tmp_path).hash_mismatches == ("MALFORMED_SHA256SUMS",)


@pytest.mark.parametrize("replace", ["root", "manifest", "payload", "parent"])
def test_symlinks_do_not_open_their_targets(tmp_path, monkeypatch, replace):
    root = tmp_path / "bundle"
    manifest, rows = _seal(root)
    outside = tmp_path / "sentinel"
    if replace == "root":
        root.rename(outside)
        root.symlink_to(outside, target_is_directory=True)
        forbidden = outside / "SHA256SUMS"
    elif replace == "manifest":
        manifest.rename(outside)
        manifest.symlink_to(outside)
        forbidden = outside
    elif replace == "payload":
        path = root / "economics.json"
        path.rename(outside)
        path.symlink_to(outside)
        forbidden = outside
    else:
        outside.mkdir()
        forbidden = outside / "results.json"
        forbidden.write_bytes(b"{}\n")
        (root / "nested").symlink_to(outside, target_is_directory=True)
        manifest.write_text("".join(rows) + f"{_sha(forbidden)}  nested/results.json\n", encoding="utf-8")

    info = forbidden.stat()
    real_fdopen = os.fdopen

    def guard_fdopen(fd, *args, **kwargs):
        opened = os.fstat(fd)
        assert (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino)
        return real_fdopen(fd, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(evidence_bundle.os, "fdopen", guard_fdopen)
        assert not verify_evidence_bundle(root).complete


def test_hardlink_and_fifo_are_rejected(tmp_path):
    manifest, rows = _seal(tmp_path)
    payload = tmp_path / "economics.json"
    os.link(payload, tmp_path / "alias.json")
    assert not verify_evidence_bundle(tmp_path).complete
    (tmp_path / "alias.json").unlink()
    os.mkfifo(tmp_path / "stream.json")
    manifest.write_text("".join(rows) + f"{'0' * 64}  stream.json\n", encoding="utf-8")
    assert verify_evidence_bundle(tmp_path).hash_mismatches == ("stream.json",)


def test_nofollow_still_holds_after_regular_file_metadata_check(tmp_path, monkeypatch):
    root = tmp_path / "bundle"
    _seal(root)
    payload = root / "economics.json"
    sentinel = tmp_path / "sentinel"
    sentinel.write_bytes(payload.read_bytes())
    sentinel_inode = sentinel.stat().st_ino
    real_open = os.open
    real_fdopen = os.fdopen
    replacements = []

    def substitute_after_stat(path, flags, *, dir_fd=None):
        if path == "economics.json":
            payload.unlink()
            payload.symlink_to(sentinel)
            replacements.append(path)
        return real_open(path, flags, dir_fd=dir_fd)

    def guard_fdopen(fd, *args, **kwargs):
        assert os.fstat(fd).st_ino != sentinel_inode
        return real_fdopen(fd, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(evidence_bundle.os, "open", substitute_after_stat)
        patch.setattr(evidence_bundle.os, "fdopen", guard_fdopen)
        assert verify_evidence_bundle(root).hash_mismatches == ("economics.json",)
    assert replacements == ["economics.json"]


def test_detects_replacement_during_payload_read(tmp_path, monkeypatch):
    _seal(tmp_path)
    current = tmp_path / "economics.json"
    original = current.stat()
    replacement = tmp_path / "replacement.json"
    replacement.write_bytes(current.read_bytes())
    real_hash = evidence_bundle._hash_payload

    def replace_during_hash(handle, limit):
        read = real_hash(handle, limit)
        if os.fstat(handle.fileno()).st_ino == original.st_ino:
            replacement.replace(current)
        return read

    monkeypatch.setattr(evidence_bundle, "_hash_payload", replace_during_hash)
    assert verify_evidence_bundle(tmp_path).hash_mismatches == ("economics.json",)


def test_detects_parent_relocation_during_payload_read(tmp_path, monkeypatch):
    manifest, rows = _seal(tmp_path)
    nested = tmp_path / "nested"
    nested.mkdir()
    payload = nested / "results.json"
    payload.write_bytes(b"{}\n")
    manifest.write_text("".join(rows) + f"{_sha(payload)}  nested/results.json\n", encoding="utf-8")
    target_inode = payload.stat().st_ino
    real_hash = evidence_bundle._hash_payload

    def relocate_during_hash(handle, limit):
        read = real_hash(handle, limit)
        if os.fstat(handle.fileno()).st_ino == target_inode:
            nested.rename(tmp_path / "relocated")
        return read

    monkeypatch.setattr(evidence_bundle, "_hash_payload", relocate_during_hash)
    assert verify_evidence_bundle(tmp_path).hash_mismatches == ("nested/results.json",)


@pytest.mark.parametrize("limit", ["manifest", "count", "payload", "total"])
def test_resource_bounds_include_exact_limit_and_reject_one_less(tmp_path, monkeypatch, limit):
    manifest, rows = _seal(tmp_path)
    sizes = [path.stat().st_size for path in tmp_path.iterdir() if path != manifest]
    key, boundary = {
        "manifest": ("MAX_MANIFEST_BYTES", manifest.stat().st_size),
        "count": ("MAX_PAYLOAD_FILES", len(rows)),
        "payload": ("MAX_PAYLOAD_BYTES", max(sizes)),
        "total": ("MAX_TOTAL_PAYLOAD_BYTES", sum(sizes)),
    }[limit]
    monkeypatch.setattr(evidence_bundle, key, boundary)
    assert verify_evidence_bundle(tmp_path).complete
    monkeypatch.setattr(evidence_bundle, key, boundary - 1)
    assert not verify_evidence_bundle(tmp_path).complete


def test_outer_receipt_digest_precedes_payload_read(tmp_path, monkeypatch):
    manifest, _ = _seal(tmp_path)
    original = _sha(manifest)
    old = manifest.read_bytes()
    manifest.write_bytes(b"\n" + old)

    def reject_read(*args):
        pytest.fail("payload read started before outer manifest binding passed")

    monkeypatch.setattr(evidence_bundle, "_hash_payload", reject_read)
    result = verify_evidence_bundle(tmp_path, expected_manifest_sha256=original)
    assert not result.complete
    assert result.hash_mismatches == ("SHA256SUMS",)
    assert result.manifest_sha256 == _sha(manifest)


def test_required_payload_must_be_listed_and_present(tmp_path):
    manifest, rows = _seal(tmp_path)
    manifest.write_text("".join(row for row in rows if not row.endswith("  economics.json\n")), encoding="utf-8")
    result = verify_evidence_bundle(tmp_path)
    assert not result.complete
    assert result.unhashed_files == ("economics.json",)
    (tmp_path / "economics.json").unlink()
    result = verify_evidence_bundle(tmp_path)
    assert not result.complete
    assert result.missing_files == ("economics.json",)
