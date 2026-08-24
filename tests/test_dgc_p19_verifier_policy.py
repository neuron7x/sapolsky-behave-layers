from __future__ import annotations

import json
from pathlib import Path

import pytest

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.p19_verifier_policy import (
    SCHEMA,
    P19VerifierPolicyError,
    load_p19_verifier_trust_policy,
    resolve_allowed_signers,
)


def _policy_doc(
    *,
    active: bool,
    allowed_path: str = "trust/allowed_signers",
    allowed_sha: str = "0" * 64,
    minimum: int = 2,
    same_verifier: bool = False,
) -> dict[str, object]:
    payload = {
        "policy_generation": "TEST_POLICY_V1",
        "frozen_pre_outcome": True,
        "activation_authorized": active,
        "allowed_signers_path": allowed_path,
        "allowed_signers_sha256": allowed_sha,
        "minimum_distinct_verifiers": minimum,
        "same_verifier_across_families_allowed": same_verifier,
        "social_independence_machine_proven": False,
    }
    return {
        "schema": SCHEMA,
        **payload,
        "policy_digest": sha256_bytes(canonical_json_bytes(payload)),
    }


def _write_policy(path: Path, doc: dict[str, object]) -> None:
    path.write_bytes(canonical_json_bytes(doc) + b"\n")


def test_unconfigured_policy_loads_but_cannot_activate_trust(tmp_path: Path):
    path = tmp_path / "policy.json"
    doc = _policy_doc(active=False, allowed_path="UNCONFIGURED", allowed_sha="0" * 64)
    _write_policy(path, doc)
    policy = load_p19_verifier_trust_policy(path)
    assert policy.active is False
    with pytest.raises(P19VerifierPolicyError, match="not activated"):
        resolve_allowed_signers(policy, repository_root=tmp_path)


def test_active_policy_resolves_only_exact_frozen_trust_store(tmp_path: Path):
    trust_dir = tmp_path / "trust"
    trust_dir.mkdir()
    allowed = trust_dir / "allowed_signers"
    allowed.write_text(
        "verifier-a ssh-ed25519 AAAATEST-A\nverifier-b ssh-ed25519 AAAATEST-B\n",
        encoding="utf-8",
    )
    policy_path = tmp_path / "policy.json"
    _write_policy(
        policy_path,
        _policy_doc(active=True, allowed_sha=sha256_file(allowed)),
    )
    policy = load_p19_verifier_trust_policy(policy_path)
    assert resolve_allowed_signers(policy, repository_root=tmp_path) == allowed.resolve()

    allowed.write_text("attacker ssh-ed25519 AAAAATTACKER\n", encoding="utf-8")
    with pytest.raises(P19VerifierPolicyError, match="bytes differ"):
        resolve_allowed_signers(policy, repository_root=tmp_path)


def test_policy_rejects_single_verifier_and_cross_family_reuse(tmp_path: Path):
    one = tmp_path / "one.json"
    _write_policy(one, _policy_doc(active=False, minimum=1))
    with pytest.raises(P19VerifierPolicyError, match="at least two distinct"):
        load_p19_verifier_trust_policy(one)

    reused = tmp_path / "reused.json"
    _write_policy(reused, _policy_doc(active=False, same_verifier=True))
    with pytest.raises(P19VerifierPolicyError, match="cannot verify both"):
        load_p19_verifier_trust_policy(reused)


def test_policy_digest_and_canonical_bytes_are_non_substitutable(tmp_path: Path):
    doc = _policy_doc(active=False)
    bad_digest = dict(doc)
    bad_digest["policy_digest"] = "f" * 64
    path = tmp_path / "bad-digest.json"
    _write_policy(path, bad_digest)
    with pytest.raises(P19VerifierPolicyError, match="digest mismatch"):
        load_p19_verifier_trust_policy(path)

    pretty = tmp_path / "pretty.json"
    pretty.write_text(json.dumps(doc, indent=2, sort_keys=True), encoding="utf-8")
    with pytest.raises(P19VerifierPolicyError, match="canonical JSON bytes"):
        load_p19_verifier_trust_policy(pretty)


def test_allowed_signers_path_cannot_escape_repository(tmp_path: Path):
    outside = tmp_path.parent / "outside-signers"
    outside.write_text("verifier ssh-ed25519 AAAATEST\n", encoding="utf-8")
    path = tmp_path / "policy.json"
    _write_policy(
        path,
        _policy_doc(
            active=True,
            allowed_path="../outside-signers",
            allowed_sha=sha256_file(outside),
        ),
    )
    policy = load_p19_verifier_trust_policy(path)
    with pytest.raises(P19VerifierPolicyError, match="repository-relative"):
        resolve_allowed_signers(policy, repository_root=tmp_path)
