from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from cwc.governance.independent_replication_authority_v3 import (
    AttestationVerifier,
    build_independent_replication_authority_v3,
)
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes
from cwc.governance.product_statistical_plan import (
    CONFSEQ_REFERENCE_COMMIT,
    PRIMARY_ASSUMPTION_BOUNDARY,
    PRIMARY_BOUNDARY_METHOD,
    PRIMARY_CLAIM_TARGET,
    PRIMARY_INFERENCE_METHOD,
    PRIMARY_PREDICTOR_RULE,
    PRIMARY_SEQUENCE_ORDER,
)
from cwc.governance.replication_attestation import verify_ssh_signed_replication_attestation

SCHEMA = "DGC_INDEPENDENT_REPLICATION_AUTHORITY_V4"
SCOPE = "FRESH_SIGNED_REPLICATION_BOUND_TO_V5_EXACT_STITCHING_THEOREM_V1"


class IndependentReplicationAuthorityV4Error(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise IndependentReplicationAuthorityV4Error(f"{name} must be lowercase SHA-256")
    return text


def theorem_identity_digest() -> str:
    return sha256_bytes(canonical_json_bytes({
        "method": PRIMARY_INFERENCE_METHOD,
        "boundary_method": PRIMARY_BOUNDARY_METHOD,
        "claim_target": PRIMARY_CLAIM_TARGET,
        "assumption_boundary": PRIMARY_ASSUMPTION_BOUNDARY,
        "sequence_order_rule": PRIMARY_SEQUENCE_ORDER,
        "predictor_rule": PRIMARY_PREDICTOR_RULE,
        "confseq_reference_commit": CONFSEQ_REFERENCE_COMMIT,
    }))


@dataclass(frozen=True, slots=True)
class IndependentReplicationAuthorityV4:
    replication_scope: str
    v3_raw_replication_authority_digest: str
    replication_package_digest: str
    primary_p9_scientific_authority_digest: str
    primary_anytime_p9_authority_digest: str
    primary_generalization_authority_digest: str
    replica_p9_scientific_authority_digest: str
    replica_anytime_p9_authority_digest: str
    statistical_plan_digest: str
    theorem_identity_digest: str
    methodology_identity_matched: bool
    fresh_execution_verified: bool
    replica_exact_panel_supported: bool
    replica_anytime_average_conditional_mean_supported: bool
    replica_scientific_p9_supported: bool
    signed_independence_attested: bool
    social_independence_machine_proven: bool
    independent_replication_supported: bool
    authority_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            **asdict(self),
            "iid_assumption_required": False,
            "provider_request_independence_required": False,
            "product_promotion_authorized": False,
        }


def build_independent_replication_authority_v4(
    *,
    primary_p9_scientific_authority_path: Path,
    primary_anytime_p9_authority_path: Path,
    primary_ccf_oracle_audit_authority_path: Path,
    primary_generalization_authority_path: Path,
    replica_p9_scientific_authority_path: Path,
    replica_anytime_p9_authority_path: Path,
    replica_ccf_oracle_audit_authority_path: Path,
    replica_execution_authority_path: Path,
    replica_execution_bundle_root: Path,
    replica_physical_cost_bundle_root: Path,
    replica_confirmatory_root_authority_path: Path,
    harness_freeze_path: Path,
    execution_manifest_freeze_path: Path,
    materialization_reference_path: Path,
    source_registry_path: Path,
    ccf_spec_authority_path: Path,
    replica_ccf_evidence_bundle_root: Path,
    repository_root: Path,
    attestation_path: Path,
    signature_path: Path,
    allowed_signers_path: Path,
    attestation_verifier: AttestationVerifier = verify_ssh_signed_replication_attestation,
) -> IndependentReplicationAuthorityV4:
    v3 = build_independent_replication_authority_v3(
        primary_p9_scientific_authority_path=primary_p9_scientific_authority_path,
        primary_anytime_p9_authority_path=primary_anytime_p9_authority_path,
        primary_ccf_oracle_audit_authority_path=primary_ccf_oracle_audit_authority_path,
        primary_generalization_authority_path=primary_generalization_authority_path,
        replica_p9_scientific_authority_path=replica_p9_scientific_authority_path,
        replica_anytime_p9_authority_path=replica_anytime_p9_authority_path,
        replica_ccf_oracle_audit_authority_path=replica_ccf_oracle_audit_authority_path,
        replica_execution_authority_path=replica_execution_authority_path,
        replica_execution_bundle_root=replica_execution_bundle_root,
        replica_physical_cost_bundle_root=replica_physical_cost_bundle_root,
        replica_confirmatory_root_authority_path=replica_confirmatory_root_authority_path,
        harness_freeze_path=harness_freeze_path,
        execution_manifest_freeze_path=execution_manifest_freeze_path,
        materialization_reference_path=materialization_reference_path,
        source_registry_path=source_registry_path,
        ccf_spec_authority_path=ccf_spec_authority_path,
        replica_ccf_evidence_bundle_root=replica_ccf_evidence_bundle_root,
        repository_root=repository_root,
        attestation_path=attestation_path,
        signature_path=signature_path,
        allowed_signers_path=allowed_signers_path,
        attestation_verifier=attestation_verifier,
    )
    if not v3.independent_replication_supported:
        raise IndependentReplicationAuthorityV4Error("V3 raw/signature replication evidence is unsupported")
    theorem_digest = theorem_identity_digest()
    payload = {
        "replication_scope": SCOPE,
        "v3_raw_replication_authority_digest": v3.authority_digest,
        "replication_package_digest": v3.replication_package_digest,
        "primary_p9_scientific_authority_digest": v3.primary_p9_scientific_authority_digest,
        "primary_anytime_p9_authority_digest": v3.primary_anytime_p9_authority_digest,
        "primary_generalization_authority_digest": v3.primary_generalization_authority_digest,
        "replica_p9_scientific_authority_digest": v3.replica_p9_scientific_authority_digest,
        "replica_anytime_p9_authority_digest": v3.replica_anytime_p9_authority_digest,
        "statistical_plan_digest": v3.statistical_plan_digest,
        "theorem_identity_digest": theorem_digest,
        "methodology_identity_matched": v3.methodology_identity_matched,
        "fresh_execution_verified": v3.fresh_execution_verified,
        "replica_exact_panel_supported": v3.replica_exact_panel_supported,
        "replica_anytime_average_conditional_mean_supported": v3.replica_anytime_average_conditional_mean_supported,
        "replica_scientific_p9_supported": v3.replica_scientific_p9_supported,
        "signed_independence_attested": v3.signed_independence_attested,
        "social_independence_machine_proven": v3.social_independence_machine_proven,
        "independent_replication_supported": True,
    }
    return IndependentReplicationAuthorityV4(
        **payload,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_independent_replication_authority_v4_document(path: Path) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise IndependentReplicationAuthorityV4Error("independent replication V4 authority must be a regular file")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise IndependentReplicationAuthorityV4Error("invalid independent replication V4 JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise IndependentReplicationAuthorityV4Error("unexpected independent replication V4 schema")
    if doc.get("replication_scope") != SCOPE:
        raise IndependentReplicationAuthorityV4Error("replication V4 scope mismatch")
    if doc.get("iid_assumption_required") is not False or doc.get("provider_request_independence_required") is not False:
        raise IndependentReplicationAuthorityV4Error("replication V4 incorrectly requires iid/provider independence")
    if doc.get("product_promotion_authorized") is not False:
        raise IndependentReplicationAuthorityV4Error("replication V4 cannot directly authorize product promotion")
    keys = (
        "replication_scope", "v3_raw_replication_authority_digest", "replication_package_digest",
        "primary_p9_scientific_authority_digest", "primary_anytime_p9_authority_digest",
        "primary_generalization_authority_digest", "replica_p9_scientific_authority_digest",
        "replica_anytime_p9_authority_digest", "statistical_plan_digest", "theorem_identity_digest",
        "methodology_identity_matched", "fresh_execution_verified", "replica_exact_panel_supported",
        "replica_anytime_average_conditional_mean_supported", "replica_scientific_p9_supported",
        "signed_independence_attested", "social_independence_machine_proven", "independent_replication_supported",
    )
    try:
        payload = {key: doc[key] for key in keys}
    except KeyError as exc:
        raise IndependentReplicationAuthorityV4Error("replication V4 payload incomplete") from exc
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("authority_digest", doc.get("authority_digest")):
        raise IndependentReplicationAuthorityV4Error("replication V4 authority digest mismatch")
    if doc.get("theorem_identity_digest") != theorem_identity_digest():
        raise IndependentReplicationAuthorityV4Error("replication V4 theorem identity is not current V5")
    required = all((
        doc.get("methodology_identity_matched") is True,
        doc.get("fresh_execution_verified") is True,
        doc.get("replica_exact_panel_supported") is True,
        doc.get("replica_anytime_average_conditional_mean_supported") is True,
        doc.get("replica_scientific_p9_supported") is True,
        doc.get("signed_independence_attested") is True,
        doc.get("social_independence_machine_proven") is False,
    ))
    if doc.get("independent_replication_supported") is not required:
        raise IndependentReplicationAuthorityV4Error("replication V4 support is not derived from fresh signed V5 evidence")
    for field in (
        "v3_raw_replication_authority_digest", "replication_package_digest",
        "primary_p9_scientific_authority_digest", "primary_anytime_p9_authority_digest",
        "primary_generalization_authority_digest", "replica_p9_scientific_authority_digest",
        "replica_anytime_p9_authority_digest", "statistical_plan_digest", "theorem_identity_digest",
    ):
        _sha(field, doc.get(field))
    return doc
