from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from cwc.governance.ccf_oracle_audit_authority import (
    build_ccf_oracle_audit_authority,
    verify_ccf_oracle_audit_authority_document,
)
from cwc.governance.executed_p9_anytime_authority import (
    build_anytime_p9_authority,
    verify_anytime_p9_authority_document,
)
from cwc.governance.generalization_anytime_authority import verify_generalization_anytime_authority_document
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes
from cwc.governance.p9_scientific_authority_v3 import (
    build_p9_scientific_authority_v3,
    verify_p9_scientific_authority_v3_document,
)
from cwc.governance.replication_attestation import (
    ReplicationSignatureReceipt,
    verify_ssh_signed_replication_attestation,
)

SCHEMA = "DGC_INDEPENDENT_REPLICATION_AUTHORITY_V3"
SCOPE = "PRIMARY_P9_ANYTIME_VALID_FRESH_EXTERNAL_REPLAY_WITH_G1_G5_CONTEXT_V2"


class IndependentReplicationAuthorityV3Error(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise IndependentReplicationAuthorityV3Error(f"{name} must be lowercase SHA-256")
    return text


AttestationVerifier = Callable[..., tuple[dict[str, object], ReplicationSignatureReceipt]]


@dataclass(frozen=True, slots=True)
class IndependentReplicationAuthorityV3:
    replication_scope: str
    replication_package_digest: str
    primary_p9_scientific_authority_digest: str
    primary_anytime_p9_authority_digest: str
    primary_generalization_authority_digest: str
    replica_p9_scientific_authority_digest: str
    replica_anytime_p9_authority_digest: str
    primary_execution_population_digest: str
    replica_execution_population_digest: str
    primary_execution_bundle_digest: str
    replica_execution_bundle_digest: str
    primary_physical_cost_population_digest: str
    replica_physical_cost_population_digest: str
    primary_ccf_evidence_population_digest: str
    replica_ccf_evidence_population_digest: str
    harness_freeze_digest: str
    confirmatory_task_manifest_digest: str
    statistical_plan_digest: str
    frozen_dgc_policy_digest: str
    methodology_identity_matched: bool
    fresh_execution_verified: bool
    replica_exact_panel_supported: bool
    replica_anytime_average_conditional_mean_supported: bool
    replica_scientific_p9_supported: bool
    replication_signature_receipt_digest: str
    replicator_principal: str
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


def _replication_package_digest(
    *,
    primary_p9: dict[str, object],
    primary_anytime: dict[str, object],
    primary_generalization: dict[str, object],
    primary_ccf: dict[str, object],
) -> str:
    payload = {
        "scope": SCOPE,
        "primary_p9_scientific_authority_digest": _sha("primary P9 authority", primary_p9.get("authority_digest")),
        "primary_anytime_p9_authority_digest": _sha("primary anytime P9 authority", primary_anytime.get("authority_digest")),
        "primary_generalization_authority_digest": _sha(
            "primary generalization authority", primary_generalization.get("authority_digest")
        ),
        "harness_freeze_digest": _sha("harness_freeze_digest", primary_p9.get("harness_freeze_digest")),
        "confirmatory_task_manifest_digest": _sha(
            "confirmatory_task_manifest_digest", primary_p9.get("confirmatory_task_manifest_digest")
        ),
        "statistical_plan_digest": _sha("statistical_plan_digest", primary_anytime.get("statistical_plan_digest")),
        "frozen_dgc_policy_digest": _sha(
            "frozen_dgc_policy_digest", primary_generalization.get("frozen_dgc_policy_digest")
        ),
        "ccf_spec_digest": _sha("ccf_spec_digest", primary_ccf.get("ccf_spec_digest")),
        "p9_claim_scope": str(primary_p9.get("claim_scope", "")),
        "generalization_claim_scope": str(primary_generalization.get("claim_scope", "")),
        "iid_assumption_required": False,
    }
    return sha256_bytes(canonical_json_bytes(payload))


def build_independent_replication_authority_v3(
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
) -> IndependentReplicationAuthorityV3:
    primary_p9 = verify_p9_scientific_authority_v3_document(Path(primary_p9_scientific_authority_path))
    primary_anytime = verify_anytime_p9_authority_document(Path(primary_anytime_p9_authority_path))
    primary_ccf = verify_ccf_oracle_audit_authority_document(Path(primary_ccf_oracle_audit_authority_path))
    primary_generalization = verify_generalization_anytime_authority_document(Path(primary_generalization_authority_path))
    if primary_p9.get("scientific_p9_supported") is not True:
        raise IndependentReplicationAuthorityV3Error("primary P9 scientific V3 is unsupported")
    if primary_generalization.get("generalization_supported_without_iid_assumption") is not True:
        raise IndependentReplicationAuthorityV3Error("primary G1-G5 V5 is unsupported")
    if primary_p9.get("anytime_p9_authority_digest") != primary_anytime.get("authority_digest"):
        raise IndependentReplicationAuthorityV3Error("primary P9/anytime lineage mismatch")
    if primary_p9.get("ccf_oracle_audit_authority_digest") != primary_ccf.get("authority_digest"):
        raise IndependentReplicationAuthorityV3Error("primary P9/CCF lineage mismatch")
    if primary_generalization.get("p9_scientific_v3_authority_digest") != primary_p9.get("authority_digest"):
        raise IndependentReplicationAuthorityV3Error("primary G1-G5/P9 lineage mismatch")

    declared_replica_anytime = verify_anytime_p9_authority_document(Path(replica_anytime_p9_authority_path))
    declared_replica_ccf = verify_ccf_oracle_audit_authority_document(Path(replica_ccf_oracle_audit_authority_path))
    declared_replica_p9 = verify_p9_scientific_authority_v3_document(Path(replica_p9_scientific_authority_path))
    try:
        recomputed_replica_anytime = build_anytime_p9_authority(
            confirmatory_execution_authority_path=Path(replica_execution_authority_path),
            execution_bundle_root=Path(replica_execution_bundle_root),
            physical_cost_bundle_root=Path(replica_physical_cost_bundle_root),
            confirmatory_root_authority_path=Path(replica_confirmatory_root_authority_path),
            harness_freeze_path=Path(harness_freeze_path),
            execution_manifest_freeze_path=Path(execution_manifest_freeze_path),
            materialization_reference_path=Path(materialization_reference_path),
            source_registry_path=Path(source_registry_path),
        )
        recomputed_replica_ccf = build_ccf_oracle_audit_authority(
            repository_root=Path(repository_root),
            ccf_spec_authority_path=Path(ccf_spec_authority_path),
            ccf_evidence_bundle_root=Path(replica_ccf_evidence_bundle_root),
            confirmatory_execution_authority_path=Path(replica_execution_authority_path),
            execution_bundle_root=Path(replica_execution_bundle_root),
            physical_cost_bundle_root=Path(replica_physical_cost_bundle_root),
            confirmatory_root_authority_path=Path(replica_confirmatory_root_authority_path),
            harness_freeze_path=Path(harness_freeze_path),
        )
    except RuntimeError as exc:
        raise IndependentReplicationAuthorityV3Error("replica raw anytime-P9/CCF replay failed") from exc
    if recomputed_replica_anytime.authority_digest != declared_replica_anytime.get("authority_digest"):
        raise IndependentReplicationAuthorityV3Error("replica anytime P9 differs from raw replay")
    if recomputed_replica_ccf.authority_digest != declared_replica_ccf.get("authority_digest"):
        raise IndependentReplicationAuthorityV3Error("replica CCF differs from raw replay")
    recomputed_replica_p9 = build_p9_scientific_authority_v3(
        anytime_p9_authority_path=Path(replica_anytime_p9_authority_path),
        ccf_oracle_audit_authority_path=Path(replica_ccf_oracle_audit_authority_path),
    )
    if recomputed_replica_p9.authority_digest != declared_replica_p9.get("authority_digest"):
        raise IndependentReplicationAuthorityV3Error("replica scientific P9 differs from component replay")
    if not recomputed_replica_p9.scientific_p9_supported:
        raise IndependentReplicationAuthorityV3Error("replica did not reproduce scientific P9")

    methodology_matched = all((
        primary_p9.get("harness_freeze_digest") == declared_replica_p9.get("harness_freeze_digest"),
        primary_p9.get("confirmatory_task_manifest_digest") == declared_replica_p9.get("confirmatory_task_manifest_digest"),
        primary_anytime.get("statistical_plan_digest") == declared_replica_anytime.get("statistical_plan_digest"),
        primary_anytime.get("anytime_method") == declared_replica_anytime.get("anytime_method"),
        primary_anytime.get("anytime_claim_target") == declared_replica_anytime.get("anytime_claim_target"),
        primary_anytime.get("anytime_assumption_boundary") == declared_replica_anytime.get("anytime_assumption_boundary"),
        primary_anytime.get("sequence_order_rule") == declared_replica_anytime.get("sequence_order_rule"),
        primary_ccf.get("ccf_spec_digest") == declared_replica_ccf.get("ccf_spec_digest"),
    ))
    if not methodology_matched:
        raise IndependentReplicationAuthorityV3Error("replica methodology differs from frozen V4 package")

    primary_exec_pop = _sha("primary execution_population_digest", primary_p9.get("execution_population_digest"))
    replica_exec_pop = _sha("replica execution_population_digest", declared_replica_p9.get("execution_population_digest"))
    primary_exec_bundle = _sha("primary execution_bundle_digest", primary_p9.get("execution_bundle_digest"))
    replica_exec_bundle = _sha("replica execution_bundle_digest", declared_replica_p9.get("execution_bundle_digest"))
    primary_cost_pop = _sha("primary physical_cost_population_digest", primary_p9.get("physical_cost_population_digest"))
    replica_cost_pop = _sha("replica physical_cost_population_digest", declared_replica_p9.get("physical_cost_population_digest"))
    primary_ccf_pop = _sha("primary ccf_evidence_population_digest", primary_ccf.get("ccf_evidence_population_digest"))
    replica_ccf_pop = _sha("replica ccf_evidence_population_digest", declared_replica_ccf.get("ccf_evidence_population_digest"))
    fresh = all((
        primary_exec_pop != replica_exec_pop,
        primary_exec_bundle != replica_exec_bundle,
        primary_cost_pop != replica_cost_pop,
        primary_ccf_pop != replica_ccf_pop,
    ))
    if not fresh:
        raise IndependentReplicationAuthorityV3Error("self-replay or reused primary evidence subject rejected")

    package_digest = _replication_package_digest(
        primary_p9=primary_p9,
        primary_anytime=primary_anytime,
        primary_generalization=primary_generalization,
        primary_ccf=primary_ccf,
    )
    try:
        attestation, signature_receipt = attestation_verifier(
            attestation_path=Path(attestation_path),
            signature_path=Path(signature_path),
            allowed_signers_path=Path(allowed_signers_path),
        )
    except RuntimeError as exc:
        raise IndependentReplicationAuthorityV3Error("external replication attestation verification failed") from exc
    if attestation.get("replication_package_digest") != package_digest:
        raise IndependentReplicationAuthorityV3Error("signed attestation references a different replication package")
    if attestation.get("primary_p9_scientific_authority_digest") != primary_p9.get("authority_digest"):
        raise IndependentReplicationAuthorityV3Error("signed attestation references a different primary P9 authority")
    if attestation.get("primary_generalization_scientific_authority_digest") != primary_generalization.get("authority_digest"):
        raise IndependentReplicationAuthorityV3Error("signed attestation references a different primary G1-G5 authority")
    if attestation.get("replica_p9_scientific_authority_digest") != declared_replica_p9.get("authority_digest"):
        raise IndependentReplicationAuthorityV3Error("signed attestation references a different replica P9 authority")
    if not signature_receipt.signature_verified:
        raise IndependentReplicationAuthorityV3Error("replicator signature is not verified")

    payload = {
        "replication_scope": SCOPE,
        "replication_package_digest": package_digest,
        "primary_p9_scientific_authority_digest": _sha("primary P9 authority", primary_p9.get("authority_digest")),
        "primary_anytime_p9_authority_digest": _sha("primary anytime P9 authority", primary_anytime.get("authority_digest")),
        "primary_generalization_authority_digest": _sha("primary G1-G5 authority", primary_generalization.get("authority_digest")),
        "replica_p9_scientific_authority_digest": _sha("replica P9 authority", declared_replica_p9.get("authority_digest")),
        "replica_anytime_p9_authority_digest": _sha("replica anytime P9 authority", declared_replica_anytime.get("authority_digest")),
        "primary_execution_population_digest": primary_exec_pop,
        "replica_execution_population_digest": replica_exec_pop,
        "primary_execution_bundle_digest": primary_exec_bundle,
        "replica_execution_bundle_digest": replica_exec_bundle,
        "primary_physical_cost_population_digest": primary_cost_pop,
        "replica_physical_cost_population_digest": replica_cost_pop,
        "primary_ccf_evidence_population_digest": primary_ccf_pop,
        "replica_ccf_evidence_population_digest": replica_ccf_pop,
        "harness_freeze_digest": _sha("harness_freeze_digest", primary_p9.get("harness_freeze_digest")),
        "confirmatory_task_manifest_digest": _sha("confirmatory_task_manifest_digest", primary_p9.get("confirmatory_task_manifest_digest")),
        "statistical_plan_digest": _sha("statistical_plan_digest", primary_anytime.get("statistical_plan_digest")),
        "frozen_dgc_policy_digest": _sha("frozen_dgc_policy_digest", primary_generalization.get("frozen_dgc_policy_digest")),
        "methodology_identity_matched": methodology_matched,
        "fresh_execution_verified": fresh,
        "replica_exact_panel_supported": declared_replica_anytime.get("exact_panel_supported") is True,
        "replica_anytime_average_conditional_mean_supported": declared_replica_anytime.get("anytime_average_conditional_mean_supported") is True,
        "replica_scientific_p9_supported": declared_replica_p9.get("scientific_p9_supported") is True,
        "replication_signature_receipt_digest": signature_receipt.digest,
        "replicator_principal": str(attestation["replicator_principal"]),
        "signed_independence_attested": True,
        "social_independence_machine_proven": False,
        "independent_replication_supported": True,
    }
    return IndependentReplicationAuthorityV3(
        **payload,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_independent_replication_authority_v3_document(path: Path) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise IndependentReplicationAuthorityV3Error("independent replication V3 authority must be a regular file")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise IndependentReplicationAuthorityV3Error("invalid independent replication V3 JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise IndependentReplicationAuthorityV3Error("unexpected independent replication V3 schema")
    if doc.get("replication_scope") != SCOPE:
        raise IndependentReplicationAuthorityV3Error("independent replication scope mismatch")
    if doc.get("iid_assumption_required") is not False or doc.get("provider_request_independence_required") is not False:
        raise IndependentReplicationAuthorityV3Error("replication V3 incorrectly requires iid/provider independence")
    if doc.get("product_promotion_authorized") is not False:
        raise IndependentReplicationAuthorityV3Error("replication V3 cannot authorize product promotion")
    keys = (
        "replication_scope", "replication_package_digest", "primary_p9_scientific_authority_digest",
        "primary_anytime_p9_authority_digest", "primary_generalization_authority_digest",
        "replica_p9_scientific_authority_digest", "replica_anytime_p9_authority_digest",
        "primary_execution_population_digest", "replica_execution_population_digest",
        "primary_execution_bundle_digest", "replica_execution_bundle_digest",
        "primary_physical_cost_population_digest", "replica_physical_cost_population_digest",
        "primary_ccf_evidence_population_digest", "replica_ccf_evidence_population_digest",
        "harness_freeze_digest", "confirmatory_task_manifest_digest", "statistical_plan_digest",
        "frozen_dgc_policy_digest", "methodology_identity_matched", "fresh_execution_verified",
        "replica_exact_panel_supported", "replica_anytime_average_conditional_mean_supported",
        "replica_scientific_p9_supported", "replication_signature_receipt_digest", "replicator_principal",
        "signed_independence_attested", "social_independence_machine_proven", "independent_replication_supported",
    )
    try:
        payload = {key: doc[key] for key in keys}
    except KeyError as exc:
        raise IndependentReplicationAuthorityV3Error("replication V3 payload incomplete") from exc
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("authority_digest", doc.get("authority_digest")):
        raise IndependentReplicationAuthorityV3Error("replication V3 authority digest mismatch")
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
        raise IndependentReplicationAuthorityV3Error("replication support is not derived from V3 evidence boundary")
    for field in (
        "replication_package_digest", "primary_p9_scientific_authority_digest",
        "primary_anytime_p9_authority_digest", "primary_generalization_authority_digest",
        "replica_p9_scientific_authority_digest", "replica_anytime_p9_authority_digest",
        "primary_execution_population_digest", "replica_execution_population_digest",
        "primary_execution_bundle_digest", "replica_execution_bundle_digest",
        "primary_physical_cost_population_digest", "replica_physical_cost_population_digest",
        "primary_ccf_evidence_population_digest", "replica_ccf_evidence_population_digest",
        "harness_freeze_digest", "confirmatory_task_manifest_digest", "statistical_plan_digest",
        "frozen_dgc_policy_digest", "replication_signature_receipt_digest",
    ):
        _sha(field, doc.get(field))
    return doc