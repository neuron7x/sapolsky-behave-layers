from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from cwc.governance.global_product_qualification import (
    GLOBAL_STATISTICAL_COMPOSITION_RULE,
    FamilyP19VerificationInput as V3FamilyP19VerificationInput,
    P19AttestationVerifier,
    build_global_product_qualification_authority as build_v3_global_authority,
)
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes
from cwc.governance.p19_verification_attestation import (
    P19VerificationSignatureReceipt,
    verify_ssh_signed_p19_verification_attestation,
)
from cwc.governance.p19_verifier_policy import (
    CANONICAL_POLICY_PATH,
    load_p19_verifier_trust_policy,
    resolve_allowed_signers,
)

SCHEMA = "DGC_GLOBAL_PRODUCT_QUALIFICATION_AUTHORITY_V4"


class GlobalProductQualificationV4Error(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class FamilyP19VerificationInputV4:
    attestation_path: Path
    verification_report_path: Path
    signature_path: Path


@dataclass(frozen=True, slots=True)
class GlobalProductQualificationAuthorityV4:
    canonical_family_ids: tuple[str, ...]
    family_p19_digests: tuple[tuple[str, str], ...]
    v3_authority_digest: str
    verifier_trust_policy_digest: str
    allowed_signers_sha256: str
    verifier_principals: tuple[str, ...]
    distinct_verifier_count: int
    minimum_distinct_verifiers: int
    same_verifier_across_families_allowed: bool
    repository_commit: str
    repository_tree: str
    statistical_plan_digest: str
    theorem_identity_digest: str
    methodology_anchor_digest: str
    global_statistical_composition_rule: str
    all_family_p19_complete: bool
    all_family_p19_externally_verified: bool
    product_qualified: bool
    production_control_authorized: bool
    authority_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            **asdict(self),
            "global_product_qualification_authorized": self.product_qualified,
            "frozen_verifier_trust_policy_required": True,
            "external_p19_semantic_replay_attestation_required": True,
            "social_independence_machine_proven": False,
            "production_provider_trace_supported": False,
            "shadow_mode_qualified": False,
            "bounded_canary_qualified": False,
        }


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise GlobalProductQualificationV4Error(f"{name} must be lowercase SHA-256")
    return text


def build_global_product_qualification_authority_v4(
    *,
    repository_root: Path,
    source_registry_path: Path,
    family_p19_paths: tuple[Path, Path],
    family_p19_verification_inputs: tuple[FamilyP19VerificationInputV4, FamilyP19VerificationInputV4],
    p19_verifier_policy_path: Path = Path(CANONICAL_POLICY_PATH),
    p19_attestation_verifier: P19AttestationVerifier = verify_ssh_signed_p19_verification_attestation,
) -> GlobalProductQualificationAuthorityV4:
    root = Path(repository_root).resolve()
    policy_path = Path(p19_verifier_policy_path)
    if not policy_path.is_absolute():
        policy_path = root / policy_path
    try:
        policy = load_p19_verifier_trust_policy(policy_path)
        allowed_signers = resolve_allowed_signers(policy, repository_root=root)
    except RuntimeError as exc:
        raise GlobalProductQualificationV4Error("frozen P19 verifier trust policy is not execution-ready") from exc

    v3_inputs = tuple(
        V3FamilyP19VerificationInput(
            attestation_path=Path(item.attestation_path),
            verification_report_path=Path(item.verification_report_path),
            signature_path=Path(item.signature_path),
            allowed_signers_path=allowed_signers,
        )
        for item in family_p19_verification_inputs
    )
    try:
        v3 = build_v3_global_authority(
            repository_root=root,
            source_registry_path=Path(source_registry_path),
            family_p19_paths=family_p19_paths,
            family_p19_verification_inputs=v3_inputs,
            p19_attestation_verifier=p19_attestation_verifier,
        )
    except RuntimeError as exc:
        raise GlobalProductQualificationV4Error("V3 evidence aggregation/P19 verification failed") from exc

    records = tuple(v3.family_p19_verification_records)
    principals = tuple(sorted(row.verifier_principal for row in records))
    distinct = len(set(principals))
    if len(records) != 2:
        raise GlobalProductQualificationV4Error("V4 requires exactly two externally verified family P19 roots")
    if distinct < policy.minimum_distinct_verifiers:
        raise GlobalProductQualificationV4Error("V4 requires the frozen minimum number of distinct verifier principals")
    if policy.same_verifier_across_families_allowed:
        raise GlobalProductQualificationV4Error("V4 rejects trust policies allowing one verifier across both families")
    if any(row.allowed_signers_sha256 != policy.allowed_signers_sha256 for row in records):
        raise GlobalProductQualificationV4Error("V4 P19 verification did not use the frozen trust store")
    qualified = bool(
        v3.product_qualified
        and v3.all_family_p19_complete
        and v3.all_family_p19_externally_verified
        and distinct >= policy.minimum_distinct_verifiers
    )
    if not qualified:
        raise GlobalProductQualificationV4Error("V4 qualification conditions are incomplete")

    payload = {
        "canonical_family_ids": list(v3.canonical_family_ids),
        "family_p19_digests": [list(row) for row in v3.family_p19_digests],
        "v3_authority_digest": _sha("v3_authority_digest", v3.authority_digest),
        "verifier_trust_policy_digest": _sha("verifier_trust_policy_digest", policy.policy_digest),
        "allowed_signers_sha256": _sha("allowed_signers_sha256", policy.allowed_signers_sha256),
        "verifier_principals": list(principals),
        "distinct_verifier_count": distinct,
        "minimum_distinct_verifiers": policy.minimum_distinct_verifiers,
        "same_verifier_across_families_allowed": False,
        "repository_commit": v3.repository_commit,
        "repository_tree": v3.repository_tree,
        "statistical_plan_digest": v3.statistical_plan_digest,
        "theorem_identity_digest": v3.theorem_identity_digest,
        "methodology_anchor_digest": v3.methodology_anchor_digest,
        "global_statistical_composition_rule": v3.global_statistical_composition_rule,
        "all_family_p19_complete": True,
        "all_family_p19_externally_verified": True,
        "product_qualified": True,
        "production_control_authorized": False,
    }
    return GlobalProductQualificationAuthorityV4(
        canonical_family_ids=tuple(v3.canonical_family_ids),
        family_p19_digests=tuple(v3.family_p19_digests),
        v3_authority_digest=payload["v3_authority_digest"],
        verifier_trust_policy_digest=payload["verifier_trust_policy_digest"],
        allowed_signers_sha256=payload["allowed_signers_sha256"],
        verifier_principals=principals,
        distinct_verifier_count=distinct,
        minimum_distinct_verifiers=policy.minimum_distinct_verifiers,
        same_verifier_across_families_allowed=False,
        repository_commit=v3.repository_commit,
        repository_tree=v3.repository_tree,
        statistical_plan_digest=v3.statistical_plan_digest,
        theorem_identity_digest=v3.theorem_identity_digest,
        methodology_anchor_digest=v3.methodology_anchor_digest,
        global_statistical_composition_rule=v3.global_statistical_composition_rule,
        all_family_p19_complete=True,
        all_family_p19_externally_verified=True,
        product_qualified=True,
        production_control_authorized=False,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_global_product_qualification_authority_v4_document(path: Path) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise GlobalProductQualificationV4Error("global product V4 authority must be a regular file")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GlobalProductQualificationV4Error("invalid global product V4 JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise GlobalProductQualificationV4Error("unexpected global product V4 schema")
    if doc.get("product_qualified") is not True or doc.get("global_product_qualification_authorized") is not True:
        raise GlobalProductQualificationV4Error("global product V4 qualification is not established")
    if doc.get("frozen_verifier_trust_policy_required") is not True:
        raise GlobalProductQualificationV4Error("global product V4 omitted frozen verifier trust policy")
    if doc.get("external_p19_semantic_replay_attestation_required") is not True:
        raise GlobalProductQualificationV4Error("global product V4 omitted external P19 replay attestation")
    if doc.get("social_independence_machine_proven") is not False:
        raise GlobalProductQualificationV4Error("global product V4 cannot claim machine-proven social independence")
    if doc.get("production_control_authorized") is not False:
        raise GlobalProductQualificationV4Error("global product V4 cannot authorize production control")
    if any(doc.get(field) is not False for field in (
        "production_provider_trace_supported", "shadow_mode_qualified", "bounded_canary_qualified"
    )):
        raise GlobalProductQualificationV4Error("production claims leaked into global product V4")

    keys = (
        "canonical_family_ids", "family_p19_digests", "v3_authority_digest",
        "verifier_trust_policy_digest", "allowed_signers_sha256", "verifier_principals",
        "distinct_verifier_count", "minimum_distinct_verifiers", "same_verifier_across_families_allowed",
        "repository_commit", "repository_tree", "statistical_plan_digest", "theorem_identity_digest",
        "methodology_anchor_digest", "global_statistical_composition_rule", "all_family_p19_complete",
        "all_family_p19_externally_verified", "product_qualified", "production_control_authorized",
    )
    try:
        payload = {key: doc[key] for key in keys}
    except KeyError as exc:
        raise GlobalProductQualificationV4Error("global product V4 payload incomplete") from exc
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("authority_digest", doc.get("authority_digest")):
        raise GlobalProductQualificationV4Error("global product V4 authority digest mismatch")
    for field in (
        "v3_authority_digest", "verifier_trust_policy_digest", "allowed_signers_sha256",
        "statistical_plan_digest", "theorem_identity_digest", "methodology_anchor_digest",
    ):
        _sha(field, doc.get(field))
    ids = doc.get("canonical_family_ids")
    roots = doc.get("family_p19_digests")
    principals = doc.get("verifier_principals")
    if not isinstance(ids, list) or len(ids) != 2 or len(set(map(str, ids))) != 2:
        raise GlobalProductQualificationV4Error("V4 canonical family population malformed")
    if not isinstance(roots, list) or len(roots) != 2:
        raise GlobalProductQualificationV4Error("V4 family P19 population malformed")
    if not isinstance(principals, list) or len(principals) != 2 or any(not str(x).strip() for x in principals):
        raise GlobalProductQualificationV4Error("V4 verifier principal population malformed")
    distinct = len(set(map(str, principals)))
    minimum = int(doc.get("minimum_distinct_verifiers", 0))
    if int(doc.get("distinct_verifier_count", 0)) != distinct or distinct < minimum or minimum < 2:
        raise GlobalProductQualificationV4Error("V4 distinct verifier threshold not satisfied")
    if doc.get("same_verifier_across_families_allowed") is not False:
        raise GlobalProductQualificationV4Error("V4 cannot allow verifier reuse across both families")
    if doc.get("global_statistical_composition_rule") != GLOBAL_STATISTICAL_COMPOSITION_RULE:
        raise GlobalProductQualificationV4Error("V4 statistical composition rule mismatch")
    if doc.get("all_family_p19_complete") is not True or doc.get("all_family_p19_externally_verified") is not True:
        raise GlobalProductQualificationV4Error("V4 family evidence/verification incomplete")
    return doc
