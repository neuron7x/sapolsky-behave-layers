from __future__ import annotations

from pathlib import Path
from typing import Mapping

from cwc.governance.evidence_closure import ClosureError, EvidenceArtifact, EvidenceClosureLedger, StageExecution, sha256_file
from cwc.governance.generalization_dual_authority import (
    build_generalization_axis_dual_authority,
    build_generalization_dual_authority,
    verify_generalization_axis_dual_authority_document,
    verify_generalization_dual_authority_document,
)
from cwc.governance.generalization_registry import GeneralizationAxis, REQUIRED_AXES
from cwc.governance.generalization_scientific_authority_v3 import (
    build_generalization_scientific_authority_v3,
    verify_generalization_scientific_authority_v3_document,
)
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
    generalization_scientific_authority_path: Path,
    generalization_dual_authority_path: Path,
    axis_authority_paths: Mapping[GeneralizationAxis, Path],
    axis_bundle_roots: Mapping[GeneralizationAxis, Path],
    identity_checker: RepositoryIdentityChecker = _assert_repository_identity,
) -> dict[str, object]:
    identity_checker(ledger)
    if ledger.next_stage() != "GENERALIZATION_SUPPORTED":
        raise ClosureError("GENERALIZATION_SUPPORTED is not the next admissible stage")
    if set(axis_authority_paths) != set(REQUIRED_AXES) or set(axis_bundle_roots) != set(REQUIRED_AXES):
        raise ClosureError("generalization closure requires exact G1-G5 authority/bundle populations")

    scientific_path, scientific_rel = _repo_file(
        ledger, generalization_scientific_authority_path, label="G1-G5 scientific authority"
    )
    dual_path, _ = _repo_file(
        ledger, generalization_dual_authority_path, label="G1-G5 dual authority"
    )
    try:
        declared_scientific = verify_generalization_scientific_authority_v3_document(scientific_path)
        declared_dual = verify_generalization_dual_authority_document(dual_path)
    except RuntimeError as exc:
        raise ClosureError("G1-G5 scientific/dual authority verification failed") from exc
    if declared_scientific.get("generalization_supported_under_frozen_assumptions") is not True:
        raise ClosureError("G1-G5 scientific support is not established under frozen assumptions")
    if declared_dual.get("exact_g1_g5_supported") is not True:
        raise ClosureError("exact frozen G1-G5 panels are not all supported")
    if declared_dual.get("expected_g1_g5_supported_under_independence_assumption") is not True:
        raise ClosureError("G1-G5 lower-bound inference failed under the frozen independence assumption")

    registry_path, _, _ = _stage_evidence_file(ledger, stage="GENERALIZATION_REGISTRY_FROZEN")
    sizing_path, _, _ = _stage_evidence_file(ledger, stage="TRIAL_SIZED")
    p9_path, _, _ = _stage_evidence_file(ledger, stage="P9_SUPPORTED")

    declared_axis_paths: dict[GeneralizationAxis, Path] = {}
    for axis in REQUIRED_AXES:
        authority_path, _ = _repo_file(
            ledger, axis_authority_paths[axis], label=f"{axis.value} dual authority"
        )
        declared_axis_paths[axis] = authority_path
        try:
            source_binding = verify_generalization_source_binding(
                repository_root=ledger.repository_root,
                registry_path=registry_path,
                axis=axis,
            )
            declared_axis = verify_generalization_axis_dual_authority_document(authority_path)
            recomputed_axis = build_generalization_axis_dual_authority(
                Path(axis_bundle_roots[axis]),
                repository_root=ledger.repository_root,
                registry_path=registry_path,
                trial_sizing_authority_path=sizing_path,
            )
        except RuntimeError as exc:
            raise ClosureError(f"{axis.value} source/raw-subject dual replay failed") from exc
        if source_binding.axis != axis.value:
            raise ClosureError(f"{axis.value} materialized source identity mismatch")
        if declared_axis.get("axis") != axis.value:
            raise ClosureError(f"{axis.value} dual authority path/identity mismatch")
        if recomputed_axis.authority_digest != declared_axis.get("authority_digest"):
            raise ClosureError(f"{axis.value} declared dual authority differs from raw-subject replay")
        if not recomputed_axis.exact_panel_supported:
            raise ClosureError(f"{axis.value} exact frozen-panel gate failed")
        if not recomputed_axis.expected_effect_supported_under_independence_assumption:
            raise ClosureError(f"{axis.value} bounded expected-effect gate failed under frozen assumptions")

    try:
        recomputed_dual = build_generalization_dual_authority(
            registry_path=registry_path,
            p9_scientific_v2_authority_path=p9_path,
            axis_authority_paths=declared_axis_paths,
        )
    except RuntimeError as exc:
        raise ClosureError("G1-G5 dual scientific composition failed") from exc
    if recomputed_dual.authority_digest != declared_dual.get("authority_digest"):
        raise ClosureError("declared G1-G5 dual authority differs from recomputed composition")
    if not recomputed_dual.exact_g1_g5_supported:
        raise ClosureError("recomputed exact G1-G5 composition is not supported")
    if not recomputed_dual.expected_g1_g5_supported_under_independence_assumption:
        raise ClosureError("recomputed G1-G5 lower-bound evidence is not supported")

    try:
        recomputed_scientific = build_generalization_scientific_authority_v3(dual_path)
    except RuntimeError as exc:
        raise ClosureError("G1-G5 scientific V3 composition failed") from exc
    if recomputed_scientific.authority_digest != declared_scientific.get("authority_digest"):
        raise ClosureError("declared G1-G5 scientific authority differs from recomputed composition")
    if not recomputed_scientific.generalization_supported_under_frozen_assumptions:
        raise ClosureError("recomputed G1-G5 scientific support failed")

    artifact = EvidenceArtifact(path=scientific_rel, sha256=sha256_file(scientific_path), minimum_bytes=2)
    return ledger.advance(StageExecution(
        stage="GENERALIZATION_SUPPORTED",
        commands=(),
        evidence=(artifact,),
    ))
