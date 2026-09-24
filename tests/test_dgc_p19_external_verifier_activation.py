from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.p19_external_python_runtime import SCHEMA as PYTHON_RUNTIME_SCHEMA
from cwc.governance.p19_external_verification_contract import (
    CANONICAL_REGRESSION_COMMAND,
    REGRESSION_TEST_FILES,
    VERIFIER_ENTRYPOINT,
    VERIFIER_RUNTIME_DEPENDENCIES,
)
from cwc.governance.p19_external_verifier_activation import (
    AUTHORITY_SCHEMA,
    P19ExternalVerifierActivationError,
    build_p19_external_verifier_activation_authority,
    canonical_regression_attestation_bytes,
    make_regression_attestation,
    verify_p19_external_verifier_activation_authority_document,
)
from cwc.governance.p19_external_verifier_regression import (
    build_p19_external_verifier_regression_receipt,
    current_repository_identity,
)
from cwc.governance.p19_verifier_policy import ALLOWED_SIGNERS_FORMAT, SCHEMA as POLICY_SCHEMA


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def _write(root: Path, rel: str, data: bytes) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _python_runtime() -> dict[str, object]:
    payload = {
        "implementation": "cpython",
        "version_major": 3,
        "version_minor": 10,
        "version_micro": 14,
        "releaselevel": "final",
        "serial": 0,
        "cache_tag": "cpython-310",
        "executable_path": "/opt/dgc/python3.10",
        "executable_sha256": "a" * 64,
        "executable_bytes": 123456,
    }
    return {
        "schema": PYTHON_RUNTIME_SCHEMA,
        **payload,
        "runtime_digest": sha256_bytes(canonical_json_bytes(payload)),
    }


def _policy(root: Path) -> tuple[Path, Path]:
    allowed = _write(
        root,
        "artifacts/dgc-product-v1/trust/allowed_signers",
        b"verifier-a ssh-ed25519 QUFB\nverifier-b ssh-ed25519 QkJC\n",
    )
    payload = {
        "policy_generation": "TEST_REGRESSION_VERIFIERS",
        "frozen_pre_outcome": True,
        "activation_authorized": True,
        "allowed_signers_path": allowed.relative_to(root).as_posix(),
        "allowed_signers_sha256": sha256_file(allowed),
        "allowed_signers_format": ALLOWED_SIGNERS_FORMAT,
        "minimum_distinct_verifiers": 2,
        "minimum_distinct_signer_keys": 2,
        "same_verifier_across_families_allowed": False,
        "same_signer_key_across_families_allowed": False,
        "social_independence_machine_proven": False,
    }
    doc = {"schema": POLICY_SCHEMA, **payload, "policy_digest": sha256_bytes(canonical_json_bytes(payload))}
    path = _write(root, "artifacts/dgc-product-v1/P19_VERIFIER_TRUST_POLICY_V2.json", canonical_json_bytes(doc) + b"\n")
    return path, allowed


def _surface(root: Path) -> None:
    _write(root, VERIFIER_ENTRYPOINT, b"print('verifier')\n")
    for rel in VERIFIER_RUNTIME_DEPENDENCIES:
        _write(root, rel, f"# runtime {rel}\n".encode())
    for rel in REGRESSION_TEST_FILES:
        if rel.endswith("test_dgc_p19_external_verifier_activation.py"):
            _write(root, rel, b"# activation regression test\n")
        else:
            _write(root, rel, f"# test {rel}\n".encode())


def _fixture(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    _surface(root)
    policy, _ = _policy(root)
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.org"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "DGC Test"], check=True)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "freeze activation surface"], check=True)
    source_commit, source_tree = current_repository_identity(root)

    stdout = _write(root, "artifacts/dgc-product-v1/generated/regression/stdout.bin", b"all tests passed\n")
    stderr = _write(root, "artifacts/dgc-product-v1/generated/regression/stderr.bin", b"")
    receipt = build_p19_external_verifier_regression_receipt(
        repository_root=root,
        source_commit=source_commit,
        source_tree=source_tree,
        command_argv=CANONICAL_REGRESSION_COMMAND,
        stdout_path=stdout.relative_to(root),
        stderr_path=stderr.relative_to(root),
        exit_code=0,
        python_runtime_identity=_python_runtime(),
    )
    receipt_path = _write(
        root,
        "artifacts/dgc-product-v1/generated/regression/receipt.json",
        canonical_json_bytes(receipt.document) + b"\n",
    )
    receipt_sha = sha256_file(receipt_path)

    attestations: list[Path] = []
    signatures: list[Path] = []
    for principal in ("verifier-a", "verifier-b"):
        att = make_regression_attestation(
            regression_receipt=receipt.document,
            regression_receipt_sha256=receipt_sha,
            verifier_principal=principal,
        )
        attestations.append(_write(
            root,
            f"artifacts/dgc-product-v1/generated/regression/{principal}.json",
            canonical_regression_attestation_bytes(att),
        ))
        signatures.append(_write(
            root,
            f"artifacts/dgc-product-v1/generated/regression/{principal}.sig",
            (principal + "-signature\n").encode(),
        ))
    fake_keygen = _write(root, "tools/ssh-keygen", b"fake ssh-keygen")
    return policy, receipt_path, attestations, signatures, fake_keygen


def _runner(argv, *, input, stdout, stderr, check):
    return subprocess.CompletedProcess(argv, 0, stdout=b"Good signature", stderr=b"")


def test_two_distinct_external_signers_can_build_activation_authority(tmp_path: Path):
    root = tmp_path / "repo"
    policy, receipt, attestations, signatures, fake_keygen = _fixture(root)
    authority = build_p19_external_verifier_activation_authority(
        repository_root=root,
        regression_receipt_path=receipt,
        trust_policy_path=policy,
        attestation_paths=attestations,
        signature_paths=signatures,
        runner=_runner,
        executable=str(fake_keygen),
    )
    assert authority.activation_authorized is True
    assert authority.all_signatures_verified is True
    assert len(set(authority.verifier_principals)) == 2
    assert len(set(authority.signer_key_digests)) == 2


def test_same_principal_cannot_satisfy_two_verifier_activation(tmp_path: Path):
    root = tmp_path / "repo"
    policy, receipt, attestations, signatures, fake_keygen = _fixture(root)
    duplicate = make_regression_attestation(
        regression_receipt=json.loads(receipt.read_text(encoding="utf-8")),
        regression_receipt_sha256=sha256_file(receipt),
        verifier_principal="verifier-a",
    )
    attestations[1].write_bytes(canonical_regression_attestation_bytes(duplicate))
    with pytest.raises(P19ExternalVerifierActivationError, match="principals are not sufficiently distinct"):
        build_p19_external_verifier_activation_authority(
            repository_root=root,
            regression_receipt_path=receipt,
            trust_policy_path=policy,
            attestation_paths=attestations,
            signature_paths=signatures,
            runner=_runner,
            executable=str(fake_keygen),
        )


def test_failed_signature_blocks_activation(tmp_path: Path):
    root = tmp_path / "repo"
    policy, receipt, attestations, signatures, fake_keygen = _fixture(root)

    def bad_runner(argv, *, input, stdout, stderr, check):
        return subprocess.CompletedProcess(argv, 1, stdout=b"", stderr=b"bad signature")

    with pytest.raises(P19ExternalVerifierActivationError, match="SSH signature failed"):
        build_p19_external_verifier_activation_authority(
            repository_root=root,
            regression_receipt_path=receipt,
            trust_policy_path=policy,
            attestation_paths=attestations,
            signature_paths=signatures,
            runner=bad_runner,
            executable=str(fake_keygen),
        )


def test_attestation_bound_to_different_receipt_is_rejected(tmp_path: Path):
    root = tmp_path / "repo"
    policy, receipt, attestations, signatures, fake_keygen = _fixture(root)
    doc = json.loads(attestations[0].read_text(encoding="utf-8"))
    doc["regression_receipt_digest"] = "9" * 64
    attestations[0].write_bytes(canonical_regression_attestation_bytes(doc))
    with pytest.raises(P19ExternalVerifierActivationError, match="attestation/receipt mismatch"):
        build_p19_external_verifier_activation_authority(
            repository_root=root,
            regression_receipt_path=receipt,
            trust_policy_path=policy,
            attestation_paths=attestations,
            signature_paths=signatures,
            runner=_runner,
            executable=str(fake_keygen),
        )


def test_authority_document_is_replayed_from_raw_signatures(tmp_path: Path):
    root = tmp_path / "repo"
    policy, receipt, attestations, signatures, fake_keygen = _fixture(root)
    authority = build_p19_external_verifier_activation_authority(
        repository_root=root,
        regression_receipt_path=receipt,
        trust_policy_path=policy,
        attestation_paths=attestations,
        signature_paths=signatures,
        runner=_runner,
        executable=str(fake_keygen),
    )
    authority_path = _write(
        root,
        "artifacts/dgc-product-v1/generated/regression/activation-authority.json",
        canonical_json_bytes(authority.document) + b"\n",
    )
    loaded = verify_p19_external_verifier_activation_authority_document(
        authority_path,
        repository_root=root,
        runner=_runner,
        executable=str(fake_keygen),
    )
    assert loaded["schema"] == AUTHORITY_SCHEMA
    assert loaded["authority_digest"] == authority.authority_digest


def test_recomputed_outer_digest_cannot_hide_changed_signer_population(tmp_path: Path):
    root = tmp_path / "repo"
    policy, receipt, attestations, signatures, fake_keygen = _fixture(root)
    authority = build_p19_external_verifier_activation_authority(
        repository_root=root,
        regression_receipt_path=receipt,
        trust_policy_path=policy,
        attestation_paths=attestations,
        signature_paths=signatures,
        runner=_runner,
        executable=str(fake_keygen),
    )
    doc = authority.document
    doc["verifier_principals"] = ["verifier-a", "verifier-c"]
    keys = tuple(key for key in doc if key not in {"schema", "authority_digest", "product_qualification_authorized"})
    doc["authority_digest"] = sha256_bytes(canonical_json_bytes({key: doc[key] for key in keys}))
    authority_path = _write(root, "artifacts/dgc-product-v1/generated/regression/forged-authority.json", canonical_json_bytes(doc) + b"\n")
    with pytest.raises(P19ExternalVerifierActivationError, match="differs from raw signature replay"):
        verify_p19_external_verifier_activation_authority_document(
            authority_path,
            repository_root=root,
            runner=_runner,
            executable=str(fake_keygen),
        )
