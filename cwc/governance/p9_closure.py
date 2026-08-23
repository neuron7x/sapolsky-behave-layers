from __future__ import annotations

from pathlib import Path

from cwc.governance.ccf_oracle_audit_authority import (
    build_ccf_oracle_audit_authority,
    verify_ccf_oracle_audit_authority_document,
)
from cwc.governance.confirmatory_execution_authority import verify_confirmatory_execution_authority_document
from cwc.governance.evidence_closure import ClosureError, EvidenceArtifact, EvidenceClosureLedger, StageExecution, sha256_file
from cwc.governance.executed_p9_dual_authority import (
    build_dual_p9_authority,
    verify_dual_p9_authority_document,
)
from cwc.governance.materialization_closure import SOURCE_REGISTRY_REL, RepositoryIdentityChecker, _assert_repository_identity
from cwc.governance.p9_scientific_authority_v2 import (
    build_p9_scientific_authority_v2,
    verify_p9_scientific_authority_v2_document,
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
    dual_p9_authority_path: Path,
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
        ledger, p9_scientific_authority_path, label="P9 scientific V2 authority"
    )
    dual_path, _ = _repo_file(ledger, dual_p9_authority_path, label="dual P9 V4 authority")
    ccf_path, _ = _repo_file(
        ledger, ccf_oracle_audit_authority_path, label="CCF oracle audit authority"
    )
    try:
        declared_scientific = verify_p9_scientific_authority_v2_document(scientific_path)
        declared_dual = verify_dual_p9_authority_document(dual_path)
        declared_ccf = verify_ccf_oracle_audit_authority_document(ccf_path)
    except RuntimeError as exc:
        raise ClosureError("P9 V4/scientific V2/CCF authority verification failed") from exc
    if declared_scientific.get("generalization_evaluation_authorized") is not True:
        raise ClosureError("P9 scientific V2 does not authorize generalization evaluation")
    if declared_dual.get("exact_panel_supported") is not True:
        raise ClosureError("P9 exact frozen panel is not supported")

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
        recomputed_dual = build_dual_p9_authority(
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
        raise ClosureError("P9 V4/CCF raw-subject recomputation failed") from exc

    if recomputed_dual.authority_digest != declared_dual.get("authority_digest"):
        raise ClosureError("declared dual P9 differs from raw-subject recomputation")
    if not recomputed_dual.exact_panel_supported:
        raise ClosureError("recomputed exact finite-panel P9 failed")
    if recomputed_ccf.authority_digest != declared_ccf.get("authority_digest"):
        raise ClosureError("declared CCF differs from raw-subject recomputation")
    if not recomputed_ccf.headroom_audit_complete:
        raise ClosureError("CCF oracle headroom audit is incomplete")

    try:
        recomputed_scientific = build_p9_scientific_authority_v2(
            dual_p9_authority_path=dual_path,
            ccf_oracle_audit_authority_path=ccf_path,
        )
    except RuntimeError as exc:
        raise ClosureError("P9 scientific V2 composition recomputation failed") from exc
    if recomputed_scientific.authority_digest != declared_scientific.get("authority_digest"):
        raise ClosureError("declared P9 scientific V2 differs from recomputed composition")
    if not recomputed_scientific.generalization_evaluation_authorized:
        raise ClosureError("recomputed exact P9 + CCF does not authorize generalization evaluation")
    if declared_scientific.get("execution_authority_digest") != execution_authority.get("authority_digest"):
        raise ClosureError("P9 scientific V2 is bound to a different CONFIRMATORY_EXECUTED authority")

    artifact = EvidenceArtifact(path=rel, sha256=sha256_file(scientific_path), minimum_bytes=2)
    return ledger.advance(StageExecution(
        stage="P9_SUPPORTED",
        commands=(),
        evidence=(artifact,),
    ))
