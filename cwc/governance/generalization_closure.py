from __future__ import annotations

from pathlib import Path
from typing import Mapping

from cwc.governance.evidence_closure import ClosureError, EvidenceArtifact, EvidenceClosureLedger, StageExecution, sha256_file
from cwc.governance.generalization_anytime_authority import (
    build_generalization_anytime_authority,
    build_generalization_axis_anytime_authority,
    verify_generalization_anytime_authority_document,
    verify_generalization_axis_anytime_authority_document,
)
from cwc.governance.generalization_registry import GeneralizationAxis, REQUIRED_AXES
from cwc.governance.generalization_source_guard import verify_generalization_source_binding
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


def close_generalization_supported(
    ledger: EvidenceClosureLedger,
    *,
    generalization_anytime_authority_path: Path,
    axis_authority_paths: Mapping[GeneralizationAxis, Path],
    axis_bundle_roots: Mapping[GeneralizationAxis, Path],
    identity_checker: RepositoryIdentityChecker = _assert_repository_identity,
) -> dict[str, object]:
    identity_checker(ledger)
    if ledger.next_stage() != "GENERALIZATION_SUPPORTED":
        raise ClosureError("GENERALIZATION_SUPPORTED is not the next admissible stage")
    if set(axis_authority_paths) != set(REQUIRED_AXES) or set(axis_bundle_roots) != set(REQUIRED_AXES):
        raise ClosureError("generalization closure requires exact G1-G5 authority/bundle populations")

    final_path, final_rel = _repo_file(
        ledger, generalization_anytime_authority_path, label="G1-G5 anytime-valid authority"
    )
    try:
        declared_final = verify_generalization_anytime_authority_document(final_path)
    except RuntimeError as exc:
        raise ClosureError("G1-G5 anytime-valid authority verification failed") from exc
    if declared_final.get("generalization_supported_without_iid_assumption") is not True:
        raise ClosureError("G1-G5 support without iid assumption is not established")

    registry_path, _, _ = _stage_evidence_file(ledger, stage="GENERALIZATION_REGISTRY_FROZEN")
    sizing_path, _, _ = _stage_evidence_file(ledger, stage="TRIAL_SIZED")
    p9_path, _, _ = _stage_evidence_file(ledger, stage="P9_SUPPORTED")

    declared_axis_paths: dict[GeneralizationAxis, Path] = {}
    for axis in REQUIRED_AXES:
        authority_path, _ = _repo_file(
            ledger, axis_authority_paths[axis], label=f"{axis.value} anytime authority"
        )
        declared_axis_paths[axis] = authority_path
        try:
            source_binding = verify_generalization_source_binding(
                repository_root=ledger.repository_root,
                registry_path=registry_path,
                axis=axis,
            )
            declared_axis = verify_generalization_axis_anytime_authority_document(authority_path)
            recomputed_axis = build_generalization_axis_anytime_authority(
                Path(axis_bundle_roots[axis]),
                repository_root=ledger.repository_root,
                registry_path=registry_path,
                trial_sizing_authority_path=sizing_path,
            )
        except RuntimeError as exc:
            raise ClosureError(f"{axis.value} source/raw-subject anytime replay failed") from exc
        if source_binding.axis != axis.value:
            raise ClosureError(f"{axis.value} materialized source identity mismatch")
        if declared_axis.get("axis") != axis.value:
            raise ClosureError(f"{axis.value} anytime authority path/identity mismatch")
        if recomputed_axis.authority_digest != declared_axis.get("authority_digest"):
            raise ClosureError(f"{axis.value} declared anytime authority differs from raw-subject replay")
        if not recomputed_axis.exact_panel_supported:
            raise ClosureError(f"{axis.value} exact frozen-panel gate failed")
        if not recomputed_axis.anytime_average_conditional_mean_supported:
            raise ClosureError(f"{axis.value} anytime-valid average-conditional-mean gate failed")
        if not recomputed_axis.axis_supported_without_iid_assumption:
            raise ClosureError(f"{axis.value} scientific gate failed without iid assumption")

    try:
        recomputed_final = build_generalization_anytime_authority(
            registry_path=registry_path,
            p9_scientific_v3_authority_path=p9_path,
            axis_authority_paths=declared_axis_paths,
        )
    except RuntimeError as exc:
        raise ClosureError("G1-G5 anytime-valid scientific composition failed") from exc
    if recomputed_final.authority_digest != declared_final.get("authority_digest"):
        raise ClosureError("declared G1-G5 anytime authority differs from recomputed composition")
    if not recomputed_final.generalization_supported_without_iid_assumption:
        raise ClosureError("recomputed G1-G5 anytime-valid support failed")

    artifact = EvidenceArtifact(path=final_rel, sha256=sha256_file(final_path), minimum_bytes=2)
    return ledger.advance(StageExecution(
        stage="GENERALIZATION_SUPPORTED",
        commands=(),
        evidence=(artifact,),
    ))