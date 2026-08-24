from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from cwc.governance.global_product_qualification import GLOBAL_STATISTICAL_COMPOSITION_RULE
from cwc.governance.global_product_qualification_v4 import (
    FamilyP19VerificationInputV4,
    build_global_product_qualification_authority_v4,
)
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes
from cwc.governance.p19_verification_attestation import (
    NAMESPACE,
    bind_attestation_to_p19,
    verify_ssh_signed_p19_verification_attestation,
)
from cwc.governance.p19_evidence_root import verify_family_p19_evidence_root_document
from cwc.governance.p19_verifier_policy import CANONICAL_POLICY_PATH, load_p19_verifier_trust_policy, resolve_allowed_signers

SCHEMA = "DGC_GLOBAL_PRODUCT_QUALIFICATION_AUTHORITY_V5"
SIGNATURE_SEMANTICS = "SSH_SIGNATURE_INPUT_SEMANTICS_ENVIRONMENT_INDEPENDENT_V1"


class GlobalProductQualificationV5Error(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class StableFamilyVerificationRecord:
    family_id: str
    p19_digest: str
    verifier_principal: str
    attestation_sha256: str
    verification_report_sha256: str
    signature_sha256: str
    allowed_signers_sha256: str
    namespace: str
    signature_verified: bool
    semantic_replay_attested: bool
    social_independence_machine_proven: bool
    record_digest: str


@dataclass(frozen=True, slots=True)
class GlobalProductQualificationAuthorityV5:
    canonical_family_ids: tuple[str, ...]
    family_p19_digests: tuple[tuple[str, str], ...]
    stable_family_verification_records: tuple[StableFamilyVerificationRecord, ...]
    verifier_trust_policy_digest: str
    allowed_signers_sha256: str
    verifier_principals: tuple[str, ...]
    distinct_verifier_count: int
    minimum_distinct_verifiers: int
    repository_commit: str
    repository_tree: str
    statistical_plan_digest: str
    theorem_identity_digest: str
    methodology_anchor_digest: str
    global_statistical_composition_rule: str
    signature_semantics: str
    signature_tool_execution_provenance_authoritative: bool
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
            "self_contained_p19_verification_transcript_required": True,
            "environment_specific_signature_tool_receipt_is_product_authority": False,
            "social_independence_machine_proven": False,
            "production_provider_trace_supported": False,
            "shadow_mode_qualified": False,
            "bounded_canary_qualified": False,
        }


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise GlobalProductQualificationV5Error(f"{name} must be lowercase SHA-256")
    return text


def _stable_record(*, p19: dict[str, object], attestation: dict[str, object], receipt) -> StableFamilyVerificationRecord:
    bind_attestation_to_p19(attestation, p19)
    if not receipt.signature_verified:
        raise GlobalProductQualificationV5Error("P19 signature verification did not PASS")
    payload = {
        "family_id": str(p19["family_id"]),
        "p19_digest": _sha("p19_digest", p19["p19_digest"]),
        "verifier_principal": str(attestation["verifier_principal"]),
        "attestation_sha256": _sha("attestation_sha256", receipt.attestation_sha256),
        "verification_report_sha256": _sha("verification_report_sha256", receipt.verification_report_sha256),
        "signature_sha256": _sha("signature_sha256", receipt.signature_sha256),
        "allowed_signers_sha256": _sha("allowed_signers_sha256", receipt.allowed_signers_sha256),
        "namespace": NAMESPACE,
        "signature_verified": True,
        "semantic_replay_attested": True,
        "social_independence_machine_proven": False,
    }
    return StableFamilyVerificationRecord(
        **payload,
        record_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def build_global_product_qualification_authority_v5(
    *,
    repository_root: Path,
    source_registry_path: Path,
    family_p19_paths: tuple[Path, Path],
    family_p19_verification_inputs: tuple[FamilyP19VerificationInputV4, FamilyP19VerificationInputV4],
    p19_verifier_policy_path: Path = Path(CANONICAL_POLICY_PATH),
) -> GlobalProductQualificationAuthorityV5:
    root = Path(repository_root).resolve()
    policy_path = Path(p19_verifier_policy_path)
    if not policy_path.is_absolute():
        policy_path = root / policy_path
    try:
        policy = load_p19_verifier_trust_policy(policy_path)
        allowed_signers = resolve_allowed_signers(policy, repository_root=root)
        # V4 remains a validation component only. Its environment-specific execution receipt
        # is deliberately excluded from the V5 serialized authority identity.
        validated = build_global_product_qualification_authority_v4(
            repository_root=root,
            source_registry_path=source_registry_path,
            family_p19_paths=family_p19_paths,
            family_p19_verification_inputs=family_p19_verification_inputs,
            p19_verifier_policy_path=policy_path,
        )
    except RuntimeError as exc:
        raise GlobalProductQualificationV5Error("V4 component validation failed") from exc

    p19_docs = [verify_family_p19_evidence_root_document(Path(path)) for path in family_p19_paths]
    records: list[StableFamilyVerificationRecord] = []
    for p19, inputs in zip(p19_docs, family_p19_verification_inputs, strict=True):
        try:
            attestation, receipt = verify_ssh_signed_p19_verification_attestation(
                attestation_path=Path(inputs.attestation_path),
                verification_report_path=Path(inputs.verification_report_path),
                signature_path=Path(inputs.signature_path),
                allowed_signers_path=allowed_signers,
                repository_root=root,
            )
        except RuntimeError as exc:
            raise GlobalProductQualificationV5Error("stable P19 signature semantic replay failed") from exc
        records.append(_stable_record(p19=dict(p19), attestation=attestation, receipt=receipt))

    ordered = tuple(sorted(records, key=lambda row: row.family_id))
    principals = tuple(row.verifier_principal for row in ordered)
    if len(ordered) != 2 or len(set(principals)) < policy.minimum_distinct_verifiers:
        raise GlobalProductQualificationV5Error("V5 verifier separation threshold not satisfied")
    if any(row.allowed_signers_sha256 != policy.allowed_signers_sha256 for row in ordered):
        raise GlobalProductQualificationV5Error("V5 signature semantics did not use frozen trust store")

    payload = {
        "canonical_family_ids": list(validated.canonical_family_ids),
        "family_p19_digests": [list(row) for row in validated.family_p19_digests],
        "stable_family_verification_records": [asdict(row) for row in ordered],
        "verifier_trust_policy_digest": _sha("verifier_trust_policy_digest", policy.policy_digest),
        "allowed_signers_sha256": _sha("allowed_signers_sha256", policy.allowed_signers_sha256),
        "verifier_principals": list(principals),
        "distinct_verifier_count": len(set(principals)),
        "minimum_distinct_verifiers": policy.minimum_distinct_verifiers,
        "repository_commit": validated.repository_commit,
        "repository_tree": validated.repository_tree,
        "statistical_plan_digest": validated.statistical_plan_digest,
        "theorem_identity_digest": validated.theorem_identity_digest,
        "methodology_anchor_digest": validated.methodology_anchor_digest,
        "global_statistical_composition_rule": validated.global_statistical_composition_rule,
        "signature_semantics": SIGNATURE_SEMANTICS,
        "signature_tool_execution_provenance_authoritative": False,
        "all_family_p19_complete": True,
        "all_family_p19_externally_verified": True,
        "product_qualified": True,
        "production_control_authorized": False,
    }
    return GlobalProductQualificationAuthorityV5(
        canonical_family_ids=tuple(validated.canonical_family_ids),
        family_p19_digests=tuple(validated.family_p19_digests),
        stable_family_verification_records=ordered,
        verifier_trust_policy_digest=payload["verifier_trust_policy_digest"],
        allowed_signers_sha256=payload["allowed_signers_sha256"],
        verifier_principals=principals,
        distinct_verifier_count=payload["distinct_verifier_count"],
        minimum_distinct_verifiers=policy.minimum_distinct_verifiers,
        repository_commit=validated.repository_commit,
        repository_tree=validated.repository_tree,
        statistical_plan_digest=validated.statistical_plan_digest,
        theorem_identity_digest=validated.theorem_identity_digest,
        methodology_anchor_digest=validated.methodology_anchor_digest,
        global_statistical_composition_rule=validated.global_statistical_composition_rule,
        signature_semantics=SIGNATURE_SEMANTICS,
        signature_tool_execution_provenance_authoritative=False,
        all_family_p19_complete=True,
        all_family_p19_externally_verified=True,
        product_qualified=True,
        production_control_authorized=False,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_global_product_qualification_authority_v5_document(path: Path) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise GlobalProductQualificationV5Error("global product V5 authority must be a regular file")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GlobalProductQualificationV5Error("invalid global product V5 JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise GlobalProductQualificationV5Error("unexpected global product V5 schema")
    if doc.get("product_qualified") is not True or doc.get("global_product_qualification_authorized") is not True:
        raise GlobalProductQualificationV5Error("global product V5 qualification is not established")
    if doc.get("signature_semantics") != SIGNATURE_SEMANTICS:
        raise GlobalProductQualificationV5Error("global product V5 signature semantics mismatch")
    if doc.get("signature_tool_execution_provenance_authoritative") is not False:
        raise GlobalProductQualificationV5Error("environment-specific signature tool provenance cannot define product truth")
    if doc.get("environment_specific_signature_tool_receipt_is_product_authority") is not False:
        raise GlobalProductQualificationV5Error("environment-specific signature tool receipt leaked into product authority")
    if doc.get("social_independence_machine_proven") is not False or doc.get("production_control_authorized") is not False:
        raise GlobalProductQualificationV5Error("global product V5 claim boundary violated")
    if any(doc.get(field) is not False for field in (
        "production_provider_trace_supported", "shadow_mode_qualified", "bounded_canary_qualified"
    )):
        raise GlobalProductQualificationV5Error("production claims leaked into global product V5")

    keys = (
        "canonical_family_ids", "family_p19_digests", "stable_family_verification_records",
        "verifier_trust_policy_digest", "allowed_signers_sha256", "verifier_principals",
        "distinct_verifier_count", "minimum_distinct_verifiers", "repository_commit", "repository_tree",
        "statistical_plan_digest", "theorem_identity_digest", "methodology_anchor_digest",
        "global_statistical_composition_rule", "signature_semantics",
        "signature_tool_execution_provenance_authoritative", "all_family_p19_complete",
        "all_family_p19_externally_verified", "product_qualified", "production_control_authorized",
    )
    try:
        payload = {key: doc[key] for key in keys}
    except KeyError as exc:
        raise GlobalProductQualificationV5Error("global product V5 payload incomplete") from exc
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("authority_digest", doc.get("authority_digest")):
        raise GlobalProductQualificationV5Error("global product V5 authority digest mismatch")
    ids = doc.get("canonical_family_ids")
    records = doc.get("stable_family_verification_records")
    if not isinstance(ids, list) or len(ids) != 2 or len(set(map(str, ids))) != 2:
        raise GlobalProductQualificationV5Error("V5 canonical family population malformed")
    if not isinstance(records, list) or len(records) != 2:
        raise GlobalProductQualificationV5Error("V5 stable verification population malformed")
    principals: set[str] = set()
    families: set[str] = set()
    for row in records:
        if not isinstance(row, dict):
            raise GlobalProductQualificationV5Error("V5 stable verification row malformed")
        row_payload = {key: row[key] for key in (
            "family_id", "p19_digest", "verifier_principal", "attestation_sha256",
            "verification_report_sha256", "signature_sha256", "allowed_signers_sha256", "namespace",
            "signature_verified", "semantic_replay_attested", "social_independence_machine_proven",
        )}
        if sha256_bytes(canonical_json_bytes(row_payload)) != _sha("stable verification record digest", row.get("record_digest")):
            raise GlobalProductQualificationV5Error("V5 stable verification record digest mismatch")
        if row.get("namespace") != NAMESPACE or row.get("signature_verified") is not True:
            raise GlobalProductQualificationV5Error("V5 stable signature semantics malformed")
        if row.get("semantic_replay_attested") is not True or row.get("social_independence_machine_proven") is not False:
            raise GlobalProductQualificationV5Error("V5 stable verification claim boundary malformed")
        families.add(str(row.get("family_id", "")))
        principals.add(str(row.get("verifier_principal", "")))
    if families != set(map(str, ids)):
        raise GlobalProductQualificationV5Error("V5 verification family set mismatch")
    minimum = int(doc.get("minimum_distinct_verifiers", 0))
    if len(principals) < minimum or minimum < 2 or int(doc.get("distinct_verifier_count", 0)) != len(principals):
        raise GlobalProductQualificationV5Error("V5 verifier threshold not satisfied")
    if doc.get("global_statistical_composition_rule") != GLOBAL_STATISTICAL_COMPOSITION_RULE:
        raise GlobalProductQualificationV5Error("V5 statistical composition rule mismatch")
    return doc
