import hashlib
from pathlib import Path

from cwc.governance.evidence_bundle import (
    REQUIRED_PRODUCT_EVIDENCE_FILES,
    verify_evidence_bundle,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_missing_bundle_is_incomplete(tmp_path):
    result = verify_evidence_bundle(tmp_path)
    assert not result.complete
    assert "PREREGISTRATION.md" in result.missing_files
    assert "SHA256SUMS" in result.missing_files


def test_complete_hash_sealed_bundle_passes(tmp_path):
    payload = [x for x in REQUIRED_PRODUCT_EVIDENCE_FILES if x != "SHA256SUMS"]
    for name in payload:
        (tmp_path / name).write_text(f"{name}\n", encoding="utf-8")
    sums = "\n".join(f"{_sha(tmp_path / name)}  {name}" for name in payload) + "\n"
    (tmp_path / "SHA256SUMS").write_text(sums, encoding="utf-8")
    result = verify_evidence_bundle(tmp_path)
    assert result.complete
    assert not result.hash_mismatches
    assert not result.unhashed_files


def test_tampered_bundle_fails(tmp_path):
    payload = [x for x in REQUIRED_PRODUCT_EVIDENCE_FILES if x != "SHA256SUMS"]
    for name in payload:
        (tmp_path / name).write_text(f"{name}\n", encoding="utf-8")
    sums = "\n".join(f"{_sha(tmp_path / name)}  {name}" for name in payload) + "\n"
    (tmp_path / "SHA256SUMS").write_text(sums, encoding="utf-8")
    (tmp_path / "economics.json").write_text("tampered\n", encoding="utf-8")
    result = verify_evidence_bundle(tmp_path)
    assert not result.complete
    assert "economics.json" in result.hash_mismatches
