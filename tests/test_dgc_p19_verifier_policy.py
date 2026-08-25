from __future__ import annotations

import json
from pathlib import Path

import pytest

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.p19_verifier_policy import (
    ALLOWED_SIGNERS_FORMAT,
    CANONICAL_POLICY_PATH,
    SCHEMA,
    P19VerifierPolicyError,
    load_p19_verifier_trust_policy,
    parse_allowed_signer_bindings,
    resolve_allowed_signers,
    signer_key_digest_map,
)


def _policy_doc(
    *,
    active: bool,
    allowed_path: str = "trust/allowed_signers",
    allowed_sha: str = "0" * 64,
    minimum_principals: int = 2,
    minimum_keys: int = 2,
    same_verifier: bool = False,
    same_key: bool = False,
) -> dict[str, object]:
    payload = {
        "policy_generation": "TEST_POLICY_V2",
        "frozen_pre_outcome": True,
        "activation_authorized": active,
        "allowed_signers_path": allowed_path,
        "allowed_signers_sha256": allowed_sha,
        "allowed_signers_format": ALLOWED_SIGNERS_FORMAT,
        "minimum_distinct_verifiers": minimum_principals,
        "minimum_distinct_signer_keys": minimum_keys,
        "same_verifier_across_families_allowed": same_verifier,
        "same_signer_key_across_families_allowed": same_key,
        "social_independence_machine_proven": False,
    }
    return {
        "schema": SCHEMA,
        **payload,
        "policy_digest": sha256_bytes(canonical_json_bytes(payload)),
    }


def _write_policy(path: Path, doc: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(doc) + b"\n")


def _write_two_key_store(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "verifier-a ssh-ed25519 AQID\nverifier-b ssh-ed25519 BAUG\n",
        encoding="utf-8",
    )


def _canonical_policy(tmp_path: Path) -> Path:
    return tmp_path / CANONICAL_POLICY_PATH


def test_unconfigured_policy_loads_but_cannot_activate_trust(tmp_path: Path):
    path = tmp_path / "policy.json"
    doc = _policy_doc(active=False, allowed_path="UNCONFIGURED", allowed_sha="0" * 64)
    _write_policy(path, doc)
    policy = load_p19_verifier_trust_policy(path)
    assert policy.active is False
    with pytest.raises(P19VerifierPolicyError, match="not activated"):
        resolve_allowed_signers(policy, repository_root=tmp_path)


def test_active_policy_resolves_only_exact_frozen_two_key_store(tmp_path: Path):
    allowed = tmp_path / "trust/allowed_signers"
    _write_two_key_store(allowed)
    policy_path = _canonical_policy(tmp_path)
    _write_policy(
        policy_path,
        _policy_doc(active=True, allowed_sha=sha256_file(allowed)),
    )
    policy = load_p19_verifier_trust_policy(policy_path)
    assert resolve_allowed_signers(policy, repository_root=tmp_path) == allowed.resolve()
    bindings = parse_allowed_signer_bindings(allowed)
    assert len(bindings) == 2
    mapping = signer_key_digest_map(policy, allowed_signers_path=allowed)
    assert set(mapping) == {"verifier-a", "verifier-b"}
    assert len(set(mapping.values())) == 2

    allowed.write_text("attacker ssh-ed25519 BwgJ\n", encoding="utf-8")
    with pytest.raises(P19VerifierPolicyError, match="bytes differ"):
        resolve_allowed_signers(policy, repository_root=tmp_path)


def test_same_key_material_under_two_principals_is_rejected(tmp_path: Path):
    allowed = tmp_path / "allowed"
    allowed.write_text(
        "verifier-a ssh-ed25519 AQID\nverifier-b ssh-ed25519 AQID\n",
        encoding="utf-8",
    )
    with pytest.raises(P19VerifierPolicyError, match="same signer key material"):
        parse_allowed_signer_bindings(allowed)


def test_policy_rejects_single_verifier_single_key_and_cross_family_reuse(tmp_path: Path):
    one = tmp_path / "one.json"
    _write_policy(one, _policy_doc(active=False, minimum_principals=1))
    with pytest.raises(P19VerifierPolicyError, match="at least two distinct verifier"):
        load_p19_verifier_trust_policy(one)

    one_key = tmp_path / "one-key.json"
    _write_policy(one_key, _policy_doc(active=False, minimum_keys=1))
    with pytest.raises(P19VerifierPolicyError, match="at least two distinct signer keys"):
        load_p19_verifier_trust_policy(one_key)

    reused_principal = tmp_path / "reused-principal.json"
    _write_policy(reused_principal, _policy_doc(active=False, same_verifier=True))
    with pytest.raises(P19VerifierPolicyError, match="principal cannot verify both"):
        load_p19_verifier_trust_policy(reused_principal)

    reused_key = tmp_path / "reused-key.json"
    _write_policy(reused_key, _policy_doc(active=False, same_key=True))
    with pytest.raises(P19VerifierPolicyError, match="key cannot verify both"):
        load_p19_verifier_trust_policy(reused_key)


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
    _write_two_key_store(outside)
    path = _canonical_policy(tmp_path)
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


def test_options_comments_and_multi_principal_lines_are_outside_canonical_format(tmp_path: Path):
    comment = tmp_path / "comment"
    comment.write_text("# no comments\n", encoding="utf-8")
    with pytest.raises(P19VerifierPolicyError, match="comments/options"):
        parse_allowed_signer_bindings(comment)

    multi = tmp_path / "multi"
    multi.write_text("a,b ssh-ed25519 AQID\n", encoding="utf-8")
    with pytest.raises(P19VerifierPolicyError, match="one principal"):
        parse_allowed_signer_bindings(multi)
