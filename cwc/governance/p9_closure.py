from __future__ import annotations

from pathlib import Path

from cwc.governance.ccf_oracle_audit_authority import (
    build_ccf_oracle_audit_authority,
    verify_ccf_oracle_audit_authority_document,
)
from cwc.governance.confirmatory_execution_authority import verify_confirmatory_execution_authority_document
from cwc.governance.evidence_closure import ClosureError, EvidenceArtifact, EvidenceClosureLedger, StageExecution, sha256_file
from cwc.governance.executed_p9_anytime_authority import (
    build_anytime_p9_authority,
    verify_anytime_p9_authority_document,
)
from cwc.governance.materialization_closure import SOURCE_REGISTRY_REL, RepositoryIdentityChecker, _assert_repository_identity
from cwc.governance.p9_scientific_authority_v3 import (
    build_p9_scientific_authority_v3,
    verify_p9_scientific_authority_v3_document,
)
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


def close_p9_supported(
    ledger: EvidenceClosureLedger,
    *,
    p9_scientific_authority_path: Path,
    anytime_p9_authority_path: Path,
    ccf_oracle_audit_authority_path: Path,
    execution_bundle_root: Path,
    physical_cost_bundle_root: Path,
    ccf_evidence_bundle_root: Path,
    identity_checker: RepositoryIdentityChecker = _assert_repository_identity,
) -> dict[str, object]:
    identity_checker(ledger)
    if ledger.next_stage() != "P9_SUPPORTED":
        raise ClosureError("P9_SUPPORTED is not the next admissible stage")

    scientific_path, rel = _repo_file(
        ledger, p9_scientific_authority_path, label="P9 scientific V3 authority"
    )
    anytime_path, _ = _repo_file(
        ledger, anytime_p9_authority_path, label="anytime-valid P9 authority"
    )
    ccf_path, _ = _repo_file(
        ledger, ccf_oracle_audit_authority_path, label="CCF oracle audit authority"
    )
    try:
        declared_scientific = verify_p9_scientific_authority_v3_document(scientific_path)
        declared_anytime = verify_anytime_p9_authority_document(anytime_path)
        declared_ccf = verify_ccf_oracle_audit_authority_document(ccf_path)
    except RuntimeError as exc:
        raise ClosureError("P9 anytime/scientific/CCF authority verification failed") from exc
    if declared_anytime.get("exact_panel_supported") is not True:
        raise ClosureError("P9 exact frozen panel is not supported")
    if declared_anytime.get("anytime_average_conditional_mean_supported") is not True:
        raise ClosureError("P9 anytime-valid average-conditional-mean gate failed")
    if declared_anytime.get("p9_supported_without_iid_assumption") is not True:
        raise ClosureError("P9 scientific support without iid assumption is not established")
    if declared_scientific.get("scientific_p9_supported") is not True:
        raise ClosureError("P9 scientific V3 composition is unsupported")
    if declared_scientific.get("generalization_evaluation_authorized") is not True:
        raise ClosureError("P9 scientific V3 does not authorize generalization evaluation")

    execution_authority_path, _, _ = _stage_evidence_file(ledger, stage="CONFIRMATORY_EXECUTED")
    root_authority_path, _, _ = _stage_evidence_file(ledger, stage="GENERATION_ROOT_FROZEN")
    harness_path, _, _ = _stage_evidence_file(ledger, stage="HARNESS_FROZEN")
    execution_freeze_path, _, _ = _stage_evidence_file(ledger, stage="EXECUTION_MANIFESTS_FROZEN")
    ccf_spec_authority_path, _, _ = _stage_evidence_file(ledger, stage="CCF_SPEC_FROZEN")
    materialization_reference_path, _, _ = _stage_evidence_file(ledger, stage="MATERIALIZED_VERIFIED")
    source_registry_path = ledger.repository_root / SOURCE_REGISTRY_REL
    if source_registry_path.is_symlink() or not source_registry_path.is_file():
        raise ClosureError("canonical source authority registry missing")

    try:
        execution_authority = verify_confirmatory_execution_authority_document(execution_authority_path)
        recomputed_anytime = build_anytime_p9_authority(
            confirmatory_execution_authority_path=execution_authority_path,
            execution_bundle_root=Path(execution_bundle_root),
            physical_cost_bundle_root=Path(physical_cost_bundle_root),
            confirmatory_root_authority_path=root_authority_path,
            harness_freeze_path=harness_path,
            execution_manifest_freeze_path=execution_freeze_path,
            materialization_reference_path=materialization_reference_path,
            source_registry_path=source_registry_path,
        )
        recomputed_ccf = build_ccf_oracle_audit_authority(
            repository_root=ledger.repository_root,
            ccf_spec_authority_path=ccf_spec_authority_path,
            ccf_evidence_bundle_root=Path(ccf_evidence_bundle_root),
            confirmatory_execution_authority_path=execution_authority_path,
            execution_bundle_root=Path(execution_bundle_root),
            physical_cost_bundle_root=Path(physical_cost_bundle_root),
            confirmatory_root_authority_path=root_authority_path,
            harness_freeze_path=harness_path,
        )
    except RuntimeError as exc:
        raise ClosureError("P9 anytime/CCF raw-subject recomputation failed") from exc

    if recomputed_anytime.authority_digest != declared_anytime.get("authority_digest"):
        raise ClosureError("declared anytime-valid P9 differs from raw-subject recomputation")
    if not recomputed_anytime.p9_supported_without_iid_assumption:
        raise ClosureError("recomputed P9 fails exact or anytime-valid scientific gate")
    if recomputed_ccf.authority_digest != declared_ccf.get("authority_digest"):
        raise ClosureError("declared CCF differs from raw-subject recomputation")
    if not recomputed_ccf.headroom_audit_complete:
        raise ClosureError("CCF oracle headroom audit is incomplete")

    try:
        recomputed_scientific = build_p9_scientific_authority_v3(
            anytime_p9_authority_path=anytime_path,
            ccf_oracle_audit_authority_path=ccf_path,
        )
    except RuntimeError as exc:
        raise ClosureError("P9 scientific V3 composition recomputation failed") from exc
    if recomputed_scientific.authority_digest != declared_scientific.get("authority_digest"):
        raise ClosureError("declared P9 scientific V3 differs from recomputed composition")
    if not recomputed_scientific.scientific_p9_supported:
        raise ClosureError("recomputed P9 scientific V3 is unsupported")
    if declared_scientific.get("execution_authority_digest") != execution_authority.get("authority_digest"):
        raise ClosureError("P9 scientific V3 is bound to a different CONFIRMATORY_EXECUTED authority")

    artifact = EvidenceArtifact(path=rel, sha256=sha256_file(scientific_path), minimum_bytes=2)
    return ledger.advance(StageExecution(
        stage="P9_SUPPORTED",
        commands=(),
        evidence=(artifact,),
    ))