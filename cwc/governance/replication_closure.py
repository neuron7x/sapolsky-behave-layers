from __future__ import annotations

from pathlib import Path

from cwc.governance.evidence_closure import ClosureError, EvidenceArtifact, EvidenceClosureLedger, StageExecution, sha256_file
from cwc.governance.independent_replication_authority_v2 import (
    build_independent_replication_authority_v2,
    verify_independent_replication_authority_v2_document,
)
from cwc.governance.materialization_closure import RepositoryIdentityChecker, _assert_repository_identity
from cwc.governance.qualification_closure import _stage_evidence_file


def _repo_file(ledger: EvidenceClosureLedger, value: Path, *, label: str) -> tuple[Path, str]:
    candidate = value if value.is_absolute() else ledger.repository_root / value
    if candidate.is_symlink():
        raise ClosureError(f"{label} symlink rejected")
    resolved = candidate.resolve()
    try:
        rel = resolved.relative_to(ledger.repository_root)
    except ValueError as exc:
        raise ClosureError(f"{label} path escapes repository") from exc
    if not resolved.is_file():
        raise ClosureError(f"{label} must be a regular file")
    return resolved, rel.as_posix()


def close_independent_replication_supported(
    ledger: EvidenceClosureLedger,
    *,
    replication_authority_path: Path,
    primary_dual_p9_authority_path: Path,
    primary_ccf_oracle_audit_authority_path: Path,
    replica_p9_scientific_authority_path: Path,
    replica_dual_p9_authority_path: Path,
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
    attestation_path: Path,
    signature_path: Path,
    allowed_signers_path: Path,
    identity_checker: RepositoryIdentityChecker = _assert_repository_identity,
) -> dict[str, object]:
    identity_checker(ledger)
    if ledger.next_stage() != "INDEPENDENT_REPLICATION_SUPPORTED":
        raise ClosureError("INDEPENDENT_REPLICATION_SUPPORTED is not the next admissible stage")

    declared_path, declared_rel = _repo_file(
        ledger, replication_authority_path, label="independent replication authority"
    )
    try:
        declared = verify_independent_replication_authority_v2_document(declared_path)
    except RuntimeError as exc:
        raise ClosureError("independent replication authority verification failed") from exc
    if declared.get("independent_replication_supported") is not True:
        raise ClosureError("independent replication support is not established")

    primary_p9_path, _, _ = _stage_evidence_file(ledger, stage="P9_SUPPORTED")
    primary_generalization_path, _, _ = _stage_evidence_file(ledger, stage="GENERALIZATION_SUPPORTED")

    try:
        recomputed = build_independent_replication_authority_v2(
            primary_p9_scientific_authority_path=primary_p9_path,
            primary_dual_p9_authority_path=Path(primary_dual_p9_authority_path),
            primary_ccf_oracle_audit_authority_path=Path(primary_ccf_oracle_audit_authority_path),
            primary_generalization_scientific_authority_path=primary_generalization_path,
            replica_p9_scientific_authority_path=Path(replica_p9_scientific_authority_path),
            replica_dual_p9_authority_path=Path(replica_dual_p9_authority_path),
            replica_ccf_oracle_audit_authority_path=Path(replica_ccf_oracle_audit_authority_path),
            replica_execution_authority_path=Path(replica_execution_authority_path),
            replica_execution_bundle_root=Path(replica_execution_bundle_root),
            replica_physical_cost_bundle_root=Path(replica_physical_cost_bundle_root),
            replica_confirmatory_root_authority_path=Path(replica_confirmatory_root_authority_path),
            harness_freeze_path=Path(harness_freeze_path),
            execution_manifest_freeze_path=Path(execution_manifest_freeze_path),
            materialization_reference_path=Path(materialization_reference_path),
            source_registry_path=Path(source_registry_path),
            ccf_spec_authority_path=Path(ccf_spec_authority_path),
            replica_ccf_evidence_bundle_root=Path(replica_ccf_evidence_bundle_root),
            repository_root=ledger.repository_root,
            attestation_path=Path(attestation_path),
            signature_path=Path(signature_path),
            allowed_signers_path=Path(allowed_signers_path),
        )
    except RuntimeError as exc:
        raise ClosureError("independent replication raw-subject/signature replay failed") from exc
    if recomputed.authority_digest != declared.get("authority_digest"):
        raise ClosureError("declared replication authority differs from raw/signature recomputation")
    if not recomputed.independent_replication_supported:
        raise ClosureError("recomputed independent replication does not satisfy the gate")
    if recomputed.social_independence_machine_proven:
        raise ClosureError("replication authority illegally claims machine proof of social independence")

    artifact = EvidenceArtifact(path=declared_rel, sha256=sha256_file(declared_path), minimum_bytes=2)
    return ledger.advance(StageExecution(
        stage="INDEPENDENT_REPLICATION_SUPPORTED",
        commands=(),
        evidence=(artifact,),
    ))
