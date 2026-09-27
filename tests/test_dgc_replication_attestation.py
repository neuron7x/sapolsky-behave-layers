from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from cwc.governance.materialization_transaction import canonical_json_bytes
from cwc.governance.replication_attestation import (
    ATTESTATION_SCHEMA,
    DECLARATION,
    ReplicationAttestationError,
    verify_ssh_signed_replication_attestation,
)


def attestation() -> dict:
    return {
        "schema": ATTESTATION_SCHEMA,
        "replicator_principal": "external-lab",
        "replication_package_digest": "a" * 64,
        "primary_p9_scientific_authority_digest": "b" * 64,
        "primary_generalization_scientific_authority_digest": "c" * 64,
        "replica_p9_scientific_authority_digest": "d" * 64,
        "methodology_unchanged": True,
        "author_control_over_execution": False,
        "raw_results_disclosed": True,
        "declaration": DECLARATION,
    }


def files(tmp_path: Path):
    att = tmp_path / "attestation.json"
    att.write_bytes(canonical_json_bytes(attestation()) + b"\n")
    sig = tmp_path / "attestation.sig"
    sig.write_bytes(b"signature")
    allowed = tmp_path / "allowed_signers"
    allowed.write_text("external-lab ssh-ed25519 AAAATEST\n", encoding="utf-8")
    exe = tmp_path / "ssh-keygen"
    exe.write_bytes(b"fake-verifier-binary")
    return att, sig, allowed, exe


def ok_runner(argv, **kwargs):
    assert "-Y" in argv and "verify" in argv
    assert kwargs["input"].endswith(b"\n")
    return subprocess.CompletedProcess(argv, 0, stdout=b"Good signature\n", stderr=b"")


def bad_runner(argv, **kwargs):
    return subprocess.CompletedProcess(argv, 255, stdout=b"", stderr=b"bad signature")


def test_signature_receipt_binds_verifier_and_inputs(tmp_path: Path):
    att, sig, allowed, exe = files(tmp_path)
    doc, receipt = verify_ssh_signed_replication_attestation(
        attestation_path=att,
        signature_path=sig,
        allowed_signers_path=allowed,
        runner=ok_runner,
        executable=str(exe),
    )
    assert doc["replicator_principal"] == "external-lab"
    assert receipt.signature_verified is True
    assert len(receipt.digest) == 64
    assert receipt.ssh_keygen_sha256 != receipt.signature_sha256


def test_noncanonical_attestation_is_rejected_before_signature(tmp_path: Path):
    att, sig, allowed, exe = files(tmp_path)
    att.write_text(json.dumps(attestation(), indent=2) + "\n", encoding="utf-8")
    with pytest.raises(ReplicationAttestationError, match="canonical JSON"):
        verify_ssh_signed_replication_attestation(
            attestation_path=att,
            signature_path=sig,
            allowed_signers_path=allowed,
            runner=ok_runner,
            executable=str(exe),
        )


def test_failed_signature_is_rejected(tmp_path: Path):
    att, sig, allowed, exe = files(tmp_path)
    with pytest.raises(ReplicationAttestationError, match="signature verification failed"):
        verify_ssh_signed_replication_attestation(
            attestation_path=att,
            signature_path=sig,
            allowed_signers_path=allowed,
            runner=bad_runner,
            executable=str(exe),
        )


def test_independence_declaration_cannot_be_weakened(tmp_path: Path):
    att, sig, allowed, exe = files(tmp_path)
    doc = attestation()
    doc["author_control_over_execution"] = True
    att.write_bytes(canonical_json_bytes(doc) + b"\n")
    with pytest.raises(ReplicationAttestationError, match="execution independence"):
        verify_ssh_signed_replication_attestation(
            attestation_path=att,
            signature_path=sig,
            allowed_signers_path=allowed,
            runner=ok_runner,
            executable=str(exe),
        )
