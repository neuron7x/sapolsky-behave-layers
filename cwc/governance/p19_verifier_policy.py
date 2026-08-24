from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file

SCHEMA = "DGC_P19_VERIFIER_TRUST_POLICY_V2"
CANONICAL_POLICY_PATH = "artifacts/dgc-product-v1/P19_VERIFIER_TRUST_POLICY_V2.json"
ALLOWED_SIGNERS_FORMAT = "DGC_SIMPLE_ALLOWED_SIGNERS_V1"


class P19VerifierPolicyError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise P19VerifierPolicyError(f"{name} must be lowercase SHA-256")
    return text


def _canonical_bytes(doc: Mapping[str, object]) -> bytes:
    return canonical_json_bytes(dict(doc)) + b"\n"


@dataclass(frozen=True, slots=True)
class AllowedSignerBinding:
    principal: str
    key_type: str
    key_blob: str
    key_digest: str


@dataclass(frozen=True, slots=True)
class P19VerifierTrustPolicy:
    policy_generation: str
    frozen_pre_outcome: bool
    activation_authorized: bool
    allowed_signers_path: str
    allowed_signers_sha256: str
    allowed_signers_format: str
    minimum_distinct_verifiers: int
    minimum_distinct_signer_keys: int
    same_verifier_across_families_allowed: bool
    same_signer_key_across_families_allowed: bool
    social_independence_machine_proven: bool
    policy_digest: str

    @property
    def active(self) -> bool:
        return self.activation_authorized


def load_p19_verifier_trust_policy(path: Path) -> P19VerifierTrustPolicy:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise P19VerifierPolicyError("P19 verifier trust policy must be a regular file")
    try:
        raw = candidate.read_bytes()
        doc = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise P19VerifierPolicyError("invalid P19 verifier trust policy JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise P19VerifierPolicyError("unexpected P19 verifier trust policy schema")
    if raw != _canonical_bytes(doc):
        raise P19VerifierPolicyError("P19 verifier trust policy must use canonical JSON bytes")
    generation = str(doc.get("policy_generation", "")).strip()
    if not generation:
        raise P19VerifierPolicyError("P19 verifier policy_generation required")
    if doc.get("frozen_pre_outcome") is not True:
        raise P19VerifierPolicyError("P19 verifier trust policy must be frozen pre-outcome")
    if doc.get("social_independence_machine_proven") is not False:
        raise P19VerifierPolicyError("P19 verifier policy cannot claim machine-proven social independence")
    minimum_principals = int(doc.get("minimum_distinct_verifiers", 0))
    minimum_keys = int(doc.get("minimum_distinct_signer_keys", 0))
    if minimum_principals < 2:
        raise P19VerifierPolicyError("P19 verifier policy requires at least two distinct verifier principals")
    if minimum_keys < 2:
        raise P19VerifierPolicyError("P19 verifier policy requires at least two distinct signer keys")
    if doc.get("same_verifier_across_families_allowed") is not False:
        raise P19VerifierPolicyError("same verifier principal cannot verify both canonical families")
    if doc.get("same_signer_key_across_families_allowed") is not False:
        raise P19VerifierPolicyError("same signer key cannot verify both canonical families")
    allowed_format = str(doc.get("allowed_signers_format", "")).strip()
    if allowed_format != ALLOWED_SIGNERS_FORMAT:
        raise P19VerifierPolicyError("unsupported P19 allowed-signers format")
    allowed_path = str(doc.get("allowed_signers_path", "")).strip()
    if not allowed_path:
        raise P19VerifierPolicyError("P19 verifier allowed_signers_path required")
    allowed_sha = _sha("allowed_signers_sha256", doc.get("allowed_signers_sha256"))
    payload = {
        "policy_generation": generation,
        "frozen_pre_outcome": True,
        "activation_authorized": doc.get("activation_authorized") is True,
        "allowed_signers_path": allowed_path,
        "allowed_signers_sha256": allowed_sha,
        "allowed_signers_format": ALLOWED_SIGNERS_FORMAT,
        "minimum_distinct_verifiers": minimum_principals,
        "minimum_distinct_signer_keys": minimum_keys,
        "same_verifier_across_families_allowed": False,
        "same_signer_key_across_families_allowed": False,
        "social_independence_machine_proven": False,
    }
    digest = sha256_bytes(canonical_json_bytes(payload))
    if digest != _sha("policy_digest", doc.get("policy_digest")):
        raise P19VerifierPolicyError("P19 verifier trust policy digest mismatch")
    return P19VerifierTrustPolicy(**payload, policy_digest=digest)


def parse_allowed_signer_bindings(path: Path) -> tuple[AllowedSignerBinding, ...]:
    candidate = Path(path)
    try:
        lines = candidate.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError) as exc:
        raise P19VerifierPolicyError("cannot read P19 verifier allowed-signers file") from exc
    bindings: list[AllowedSignerBinding] = []
    principals: set[str] = set()
    key_digests: set[str] = set()
    for line_number, raw in enumerate(lines, start=1):
        text = raw.strip()
        if not text:
            continue
        if text.startswith("#"):
            raise P19VerifierPolicyError("comments/options are forbidden in DGC simple allowed-signers format")
        parts = text.split()
        if len(parts) != 3:
            raise P19VerifierPolicyError(
                f"allowed-signers line {line_number} must be exactly: principal keytype base64"
            )
        principal, key_type, key_blob = parts
        if not principal or "," in principal or any(ch.isspace() for ch in principal):
            raise P19VerifierPolicyError("each allowed-signers line must bind exactly one principal")
        if principal in principals:
            raise P19VerifierPolicyError("duplicate verifier principal in allowed-signers file")
        if not key_type or not key_blob:
            raise P19VerifierPolicyError("allowed-signers key type/blob required")
        try:
            decoded = base64.b64decode(key_blob.encode("ascii"), validate=True)
        except (UnicodeEncodeError, binascii.Error) as exc:
            raise P19VerifierPolicyError("allowed-signers key blob must be canonical base64") from exc
        if not decoded:
            raise P19VerifierPolicyError("allowed-signers key blob cannot decode to empty bytes")
        key_digest = sha256_bytes(canonical_json_bytes([key_type, key_blob]))
        if key_digest in key_digests:
            raise P19VerifierPolicyError("same signer key material cannot be reused across verifier principals")
        principals.add(principal)
        key_digests.add(key_digest)
        bindings.append(AllowedSignerBinding(
            principal=principal,
            key_type=key_type,
            key_blob=key_blob,
            key_digest=key_digest,
        ))
    if not bindings:
        raise P19VerifierPolicyError("allowed-signers file contains no verifier bindings")
    return tuple(sorted(bindings, key=lambda row: row.principal))


def resolve_allowed_signers(policy: P19VerifierTrustPolicy, *, repository_root: Path) -> Path:
    if not policy.activation_authorized:
        raise P19VerifierPolicyError("P19 external verifier trust policy is not activated")
    rel = Path(policy.allowed_signers_path)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise P19VerifierPolicyError("P19 verifier allowed-signers path must be repository-relative")
    root = Path(repository_root).resolve()
    candidate = root / rel
    if candidate.is_symlink():
        raise P19VerifierPolicyError("P19 verifier allowed-signers symlink rejected")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise P19VerifierPolicyError("P19 verifier allowed-signers path escapes repository") from exc
    if not resolved.is_file() or resolved.stat().st_size <= 0:
        raise P19VerifierPolicyError("P19 verifier allowed-signers file is missing/empty")
    if sha256_file(resolved) != policy.allowed_signers_sha256:
        raise P19VerifierPolicyError("P19 verifier allowed-signers bytes differ from frozen policy")
    bindings = parse_allowed_signer_bindings(resolved)
    if len({row.principal for row in bindings}) < policy.minimum_distinct_verifiers:
        raise P19VerifierPolicyError("frozen allowed-signers file has too few distinct verifier principals")
    if len({row.key_digest for row in bindings}) < policy.minimum_distinct_signer_keys:
        raise P19VerifierPolicyError("frozen allowed-signers file has too few distinct signer keys")
    return resolved


def signer_key_digest_map(policy: P19VerifierTrustPolicy, *, allowed_signers_path: Path) -> dict[str, str]:
    bindings = parse_allowed_signer_bindings(Path(allowed_signers_path))
    result = {row.principal: row.key_digest for row in bindings}
    if len(result) < policy.minimum_distinct_verifiers:
        raise P19VerifierPolicyError("allowed-signers principal population below frozen minimum")
    if len(set(result.values())) < policy.minimum_distinct_signer_keys:
        raise P19VerifierPolicyError("allowed-signers key population below frozen minimum")
    return result
