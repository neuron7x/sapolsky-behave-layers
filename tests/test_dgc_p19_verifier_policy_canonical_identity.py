from __future__ import annotations

from pathlib import Path

import pytest

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.p19_verifier_policy import (
    ALLOWED_SIGNERS_FORMAT,
    CANONICAL_POLICY_PATH,
    SCHEMA,
    P19VerifierPolicyError,
    load_p19_verifier_trust_policy,
    resolve_allowed_signers,
)


def _write_policy(root: Path, *, policy_rel: str, allowed_rel: str, principals: tuple[str, str]) -> Path:
    allowed = root / allowed_rel
    allowed.parent.mkdir(parents=True, exist_ok=True)
    allowed.write_text(
        f"{principals[0]} ssh-ed25519 QUFB\n{principals[1]} ssh-ed25519 QkJC\n",
        encoding="utf-8",
    )
    payload = {
        "policy_generation": f"TEST_{principals[0]}_{principals[1]}",
        "frozen_pre_outcome": True,
        "activation_authorized": True,
        "allowed_signers_path": allowed_rel,
        "allowed_signers_sha256": sha256_file(allowed),
        "allowed_signers_format": ALLOWED_SIGNERS_FORMAT,
        "minimum_distinct_verifiers": 2,
        "minimum_distinct_signer_keys": 2,
        "same_verifier_across_families_allowed": False,
        "same_signer_key_across_families_allowed": False,
        "social_independence_machine_proven": False,
    }
    doc = {
        "schema": SCHEMA,
        **payload,
        "policy_digest": sha256_bytes(canonical_json_bytes(payload)),
    }
    path = root / policy_rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(doc) + b"\n")
    return path


def test_exact_canonical_policy_identity_resolves_allowed_signers(tmp_path: Path):
    canonical = _write_policy(
        tmp_path,
        policy_rel=CANONICAL_POLICY_PATH,
        allowed_rel="artifacts/dgc-product-v1/trust/canonical_allowed_signers",
        principals=("verifier-a", "verifier-b"),
    )
    policy = load_p19_verifier_trust_policy(canonical)
    allowed = resolve_allowed_signers(policy, repository_root=tmp_path)
    assert allowed.relative_to(tmp_path).as_posix() == policy.allowed_signers_path


def test_valid_but_noncanonical_policy_identity_cannot_substitute_activation_trust_root(tmp_path: Path):
    _write_policy(
        tmp_path,
        policy_rel=CANONICAL_POLICY_PATH,
        allowed_rel="artifacts/dgc-product-v1/trust/canonical_allowed_signers",
        principals=("verifier-a", "verifier-b"),
    )
    attacker = _write_policy(
        tmp_path,
        policy_rel="artifacts/dgc-product-v1/generated/attacker_policy.json",
        allowed_rel="artifacts/dgc-product-v1/generated/attacker_allowed_signers",
        principals=("attacker-a", "attacker-b"),
    )
    attacker_policy = load_p19_verifier_trust_policy(attacker)
    with pytest.raises(P19VerifierPolicyError, match="differs from canonical frozen policy identity"):
        resolve_allowed_signers(attacker_policy, repository_root=tmp_path)
