from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file

SCHEMA = "DGC_P19_VERIFIER_TRUST_POLICY_V1"
CANONICAL_POLICY_PATH = "artifacts/dgc-product-v1/P19_VERIFIER_TRUST_POLICY_V1.json"


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
class P19VerifierTrustPolicy:
    policy_generation: str
    frozen_pre_outcome: bool
    activation_authorized: bool
    allowed_signers_path: str
    allowed_signers_sha256: str
    minimum_distinct_verifiers: int
    same_verifier_across_families_allowed: bool
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
    minimum = int(doc.get("minimum_distinct_verifiers", 0))
    if minimum < 2:
        raise P19VerifierPolicyError("P19 verifier policy requires at least two distinct verifier principals")
    if doc.get("same_verifier_across_families_allowed") is not False:
        raise P19VerifierPolicyError("same verifier principal cannot verify both canonical families")
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
        "minimum_distinct_verifiers": minimum,
        "same_verifier_across_families_allowed": False,
        "social_independence_machine_proven": False,
    }
    digest = sha256_bytes(canonical_json_bytes(payload))
    if digest != _sha("policy_digest", doc.get("policy_digest")):
        raise P19VerifierPolicyError("P19 verifier trust policy digest mismatch")
    return P19VerifierTrustPolicy(**payload, policy_digest=digest)


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
    return resolved
