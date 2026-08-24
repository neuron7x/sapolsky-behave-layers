from __future__ import annotations

from pathlib import Path

import pytest

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes
from cwc.governance.p19_verification_check_receipt import (
    P19VerificationCheckReceiptError,
    build_check_receipt_document,
    canonical_receipt_bytes,
    load_check_receipt,
)


def _subjects(root: Path) -> tuple[Path, Path, Path]:
    base = root / "artifacts/dgc-product-v1/generated/check"
    base.mkdir(parents=True)
    stdout = base / "stdout.bin"
    stderr = base / "stderr.bin"
    evidence = base / "evidence.json"
    stdout.write_bytes(b"PASS\n")
    stderr.write_bytes(b"")
    evidence.write_bytes(b'{"verified":true}\n')
    return stdout, stderr, evidence


def _document(root: Path) -> dict[str, object]:
    stdout, stderr, evidence = _subjects(root)
    return build_check_receipt_document(
        repository_root=root,
        check_id="REPOSITORY_IDENTITY",
        command_argv=("python", "verify_repository.py"),
        stdout_path=stdout.relative_to(root).as_posix(),
        stderr_path=stderr.relative_to(root).as_posix(),
        evidence_path=evidence.relative_to(root).as_posix(),
        evidence_digest=sha256_bytes(b"semantic-evidence"),
    )


def test_receipt_round_trip_is_repository_root_relative(tmp_path: Path):
    doc = _document(tmp_path)
    path = tmp_path / "artifacts/dgc-product-v1/generated/check/receipt.json"
    path.write_bytes(canonical_receipt_bytes(doc))
    verified = load_check_receipt(
        Path("artifacts/dgc-product-v1/generated/check/receipt.json"),
        repository_root=tmp_path,
    )
    assert verified.check_id == "REPOSITORY_IDENTITY"
    assert verified.status == "PASS"
    assert verified.stderr_bytes == 0
    assert verified.command_sha256 == sha256_bytes(canonical_json_bytes(["python", "verify_repository.py"]))


def test_receipt_symlink_is_rejected(tmp_path: Path):
    doc = _document(tmp_path)
    target = tmp_path / "artifacts/dgc-product-v1/generated/check/real.json"
    target.write_bytes(canonical_receipt_bytes(doc))
    link = tmp_path / "artifacts/dgc-product-v1/generated/check/receipt.json"
    try:
        link.symlink_to(target.name)
    except OSError:
        pytest.skip("symlink unavailable")
    with pytest.raises(P19VerificationCheckReceiptError, match="non-symlink"):
        load_check_receipt(link, repository_root=tmp_path)


def test_receipt_detects_raw_evidence_mutation(tmp_path: Path):
    doc = _document(tmp_path)
    path = tmp_path / "artifacts/dgc-product-v1/generated/check/receipt.json"
    path.write_bytes(canonical_receipt_bytes(doc))
    evidence = tmp_path / str(doc["evidence_path"])
    evidence.write_bytes(b'{"verified":false}\n')
    with pytest.raises(P19VerificationCheckReceiptError, match="bytes differ"):
        load_check_receipt(path, repository_root=tmp_path)


def test_receipt_rejects_noncanonical_subject_path(tmp_path: Path):
    stdout, stderr, evidence = _subjects(tmp_path)
    with pytest.raises(P19VerificationCheckReceiptError, match="canonical repository-relative"):
        build_check_receipt_document(
            repository_root=tmp_path,
            check_id="REPOSITORY_IDENTITY",
            command_argv=("python", "verify_repository.py"),
            stdout_path="artifacts//dgc-product-v1/generated/check/stdout.bin",
            stderr_path=stderr.relative_to(tmp_path).as_posix(),
            evidence_path=evidence.relative_to(tmp_path).as_posix(),
            evidence_digest=sha256_bytes(b"semantic-evidence"),
        )
