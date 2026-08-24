from __future__ import annotations

import json
import subprocess
from pathlib import Path, PurePosixPath
from typing import Callable, Mapping

from cwc.governance.ccf_oracle_audit_authority import build_ccf_oracle_audit_authority
from cwc.governance.executed_p9_anytime_authority import build_anytime_p9_authority
from cwc.governance.execution_manifest_freeze import verify_execution_manifest_freeze_document
from cwc.governance.fault_tolerance_authority import build_fault_tolerance_authority, verify_fault_tolerance_authority_document
from cwc.governance.generalization_anytime_authority import (
    build_generalization_anytime_authority,
    build_generalization_axis_anytime_authority,
    verify_generalization_anytime_authority_document,
    verify_generalization_axis_anytime_authority_document,
)
from cwc.governance.generalization_registry import GeneralizationAxis, REQUIRED_AXES
from cwc.governance.generalization_source_guard import verify_generalization_source_binding
from cwc.governance.independent_replication_authority_v4 import (
    build_independent_replication_authority_v4,
    verify_independent_replication_authority_v4_document,
)
from cwc.governance.materialization_transaction import canonical_json_bytes, file_manifest, sha256_bytes, sha256_file
from cwc.governance.p19_evidence_root import (
    METHODOLOGY_ANCHORS,
    REQUIRED_EXTERNAL_REPLAY_INPUTS,
    REQUIRED_SUBJECT_ROOTS,
    _theorem_identity_digest,
    verify_family_p19_evidence_root_document,
)
from cwc.governance.p9_scientific_authority_v3 import (
    build_p9_scientific_authority_v3,
    verify_p9_scientific_authority_v3_document,
)

CHECK_METHOD_IDS = {
    "REPOSITORY_IDENTITY": "DGC_P19_EXTERNAL_REPOSITORY_IDENTITY_V1",
    "THEOREM_AND_PLAN_IDENTITY": "DGC_P19_EXTERNAL_THEOREM_AND_PLAN_IDENTITY_V1",
    "SUBJECT_ROOT_REHASH": "DGC_P19_EXTERNAL_SUBJECT_ROOT_REHASH_V1",
    "P19_SEAL_REBUILD": "DGC_P19_EXTERNAL_SEAL_REBUILD_V1",
    "PRIMARY_P9_RAW_REPLAY": "DGC_P19_EXTERNAL_PRIMARY_P9_RAW_REPLAY_V1",
    "GENERALIZATION_G1_G5_RAW_REPLAY": "DGC_P19_EXTERNAL_GENERALIZATION_G1_G5_RAW_REPLAY_V1",
    "FAULT_TOLERANCE_RAW_REPLAY": "DGC_P19_EXTERNAL_FAULT_TOLERANCE_RAW_REPLAY_V1",
    "INDEPENDENT_REPLICATION_RAW_REPLAY": "DGC_P19_EXTERNAL_INDEPENDENT_REPLICATION_RAW_REPLAY_V1",
}

EVIDENCE_SCHEMA = "DGC_P19_EXTERNAL_CHECK_EVIDENCE_V1"


class P19ExternalReplayError(RuntimeError):
    pass


def _canonical_rel(value: object, *, label: str) -> str:
    text = str(value)
    if (
        not text
        or text != text.strip()
        or any(ch in text for ch in ("\x00", "\n", "\r", "\t", "\\"))
        or "//" in text
    ):
        raise P19ExternalReplayError(f"{label} is not a canonical repository-relative POSIX path")
    rel = PurePosixPath(text)
    if rel.is_absolute() or any(part in ("", ".", "..") for part in rel.parts):
        raise P19ExternalReplayError(f"{label} is not a canonical repository-relative POSIX path")
    return rel.as_posix()


def _repo_file(root: Path, rel_value: object, *, label: str, allow_empty: bool = False) -> Path:
    rel = _canonical_rel(rel_value, label=label)
    candidate = root / rel
    if candidate.is_symlink():
        raise P19ExternalReplayError(f"{label} symlink rejected")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise P19ExternalReplayError(f"{label} escapes repository") from exc
    if not resolved.is_file():
        raise P19ExternalReplayError(f"{label} missing")
    if not allow_empty and resolved.stat().st_size <= 0:
        raise P19ExternalReplayError(f"{label} must be non-empty")
    return resolved


def _stage_row(p19: Mapping[str, object], stage: str) -> Mapping[str, object]:
    rows = p19.get("stage_evidence")
    if not isinstance(rows, list):
        raise P19ExternalReplayError("P19 stage evidence missing")
    matches = [row for row in rows if isinstance(row, Mapping) and row.get("stage") == stage]
    if len(matches) != 1 or not isinstance(matches[0].get("evidence"), Mapping):
        raise P19ExternalReplayError(f"P19 requires exactly one stage locator: {stage}")
    return matches[0]


def _stage_path(root: Path, p19: Mapping[str, object], stage: str) -> Path:
    row = _stage_row(p19, stage)
    evidence = row["evidence"]
    assert isinstance(evidence, Mapping)
    path = _repo_file(root, evidence.get("path"), label=f"stage {stage}")
    expected = str(evidence.get("sha256", ""))
    if sha256_file(path) != expected or path.stat().st_size != int(evidence.get("bytes", -1)):
        raise P19ExternalReplayError(f"stage {stage} bytes differ from sealed P19")
    return path


def _subject_row(p19: Mapping[str, object], label: str) -> Mapping[str, object]:
    roots = p19.get("subject_roots")
    if not isinstance(roots, list):
        raise P19ExternalReplayError("P19 subject roots missing")
    matches = [row for row in roots if isinstance(row, Mapping) and row.get("label") == label]
    if len(matches) != 1:
        raise P19ExternalReplayError(f"P19 subject root locator missing/duplicated: {label}")
    return matches[0]


def _subject_root(root: Path, p19: Mapping[str, object], label: str, *, rehash: bool = True) -> Path:
    row = _subject_row(p19, label)
    rel = _canonical_rel(row.get("path"), label=f"subject root {label}")
    candidate = root / rel
    if candidate.is_symlink():
        raise P19ExternalReplayError(f"subject root {label} symlink rejected")
    path = candidate.resolve()
    try:
        path.relative_to(root)
    except ValueError as exc:
        raise P19ExternalReplayError(f"subject root {label} escapes repository") from exc
    if not path.is_dir():
        raise P19ExternalReplayError(f"subject root {label} missing")
    if rehash:
        manifest = file_manifest(path)
        if any(item[1] != "file" for item in manifest):
            raise P19ExternalReplayError(f"subject root {label} contains non-file object")
        files = [
            {"path": p, "type": kind, "mode": mode, "bytes": size, "sha256": digest}
            for p, kind, mode, size, digest in manifest
        ]
        if files != row.get("files"):
            raise P19ExternalReplayError(f"subject root {label} file population changed")
        if len(manifest) != int(row.get("file_count", -1)):
            raise P19ExternalReplayError(f"subject root {label} file count changed")
        if sum(int(item[3]) for item in manifest) != int(row.get("total_bytes", -1)):
            raise P19ExternalReplayError(f"subject root {label} byte count changed")
        if sha256_bytes(canonical_json_bytes(manifest)) != row.get("manifest_sha256"):
            raise P19ExternalReplayError(f"subject root {label} manifest digest changed")
    return path


def _replay_row(p19: Mapping[str, object], label: str) -> Mapping[str, object]:
    rows = p19.get("external_replay_inputs")
    if not isinstance(rows, list):
        raise P19ExternalReplayError("P19 external replay input manifest missing")
    matches = [row for row in rows if isinstance(row, Mapping) and row.get("label") == label]
    if len(matches) != 1:
        raise P19ExternalReplayError(f"P19 external replay input missing/duplicated: {label}")
    return matches[0]


def _replay_file(root: Path, p19: Mapping[str, object], label: str) -> Path:
    row = _replay_row(p19, label)
    path = _repo_file(root, row.get("path"), label=f"external replay input {label}")
    if sha256_file(path) != row.get("sha256") or path.stat().st_size != int(row.get("bytes", -1)):
        raise P19ExternalReplayError(f"external replay input {label} changed after P19 seal")
    return path


def _all_external_replay_files(root: Path, p19: Mapping[str, object]) -> tuple[Path, ...]:
    return tuple(_replay_file(root, p19, label) for label in sorted(REQUIRED_EXTERNAL_REPLAY_INPUTS))


def _load_p19(root: Path, p19_path: Path) -> tuple[Path, dict[str, object]]:
    candidate = p19_path if p19_path.is_absolute() else root / p19_path
    if candidate.is_symlink():
        raise P19ExternalReplayError("P19 symlink rejected")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise P19ExternalReplayError("P19 path escapes repository") from exc
    try:
        p19 = verify_family_p19_evidence_root_document(resolved)
    except RuntimeError as exc:
        raise P19ExternalReplayError("P19 structural verification failed") from exc
    return resolved, p19


def _git(root: Path, *args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except OSError as exc:
        raise P19ExternalReplayError("git executable unavailable") from exc
    if proc.returncode != 0:
        raise P19ExternalReplayError(f"git {' '.join(args)} failed")
    return proc.stdout.strip()


def replay_repository_identity(root: Path, p19: Mapping[str, object]) -> dict[str, object]:
    commit = str(p19.get("repository_commit", ""))
    tree = str(p19.get("repository_tree", ""))
    observed_tree = _git(root, "rev-parse", f"{commit}^{{tree}}").lower()
    if observed_tree != tree:
        raise P19ExternalReplayError("P19 execution tree differs from Git object database")
    head = _git(root, "rev-parse", "HEAD").lower()
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "merge-base", "--is-ancestor", commit, head],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise P19ExternalReplayError("git executable unavailable") from exc
    if proc.returncode != 0:
        raise P19ExternalReplayError("current checkout is not a descendant of sealed execution commit")
    return {"execution_commit": commit, "execution_tree": tree, "current_head": head, "ancestor_relation_verified": True}


def replay_theorem_and_plan_identity(root: Path, p19: Mapping[str, object]) -> dict[str, object]:
    if p19.get("theorem_identity_digest") != _theorem_identity_digest():
        raise P19ExternalReplayError("P19 theorem identity differs from current V5 implementation")
    execution_path = _stage_path(root, p19, "EXECUTION_MANIFESTS_FROZEN")
    execution = verify_execution_manifest_freeze_document(execution_path)
    if execution.get("statistical_plan_digest") != p19.get("statistical_plan_digest"):
        raise P19ExternalReplayError("execution statistical plan differs from P19")
    anchors = p19.get("methodology_anchors")
    if not isinstance(anchors, list) or [str(row.get("path")) for row in anchors if isinstance(row, Mapping)] != list(METHODOLOGY_ANCHORS):
        raise P19ExternalReplayError("P19 methodology anchor population/order mismatch")
    rebuilt: list[dict[str, object]] = []
    for row in anchors:
        assert isinstance(row, Mapping)
        path = _repo_file(root, row.get("path"), label="methodology anchor")
        item = {"path": str(row["path"]), "sha256": sha256_file(path), "bytes": path.stat().st_size}
        if item != dict(row):
            raise P19ExternalReplayError("methodology anchor changed after P19 seal")
        rebuilt.append(item)
    if sha256_bytes(canonical_json_bytes(rebuilt)) != p19.get("methodology_anchor_digest"):
        raise P19ExternalReplayError("methodology anchor aggregate digest mismatch")
    return {
        "statistical_plan_digest": str(p19["statistical_plan_digest"]),
        "theorem_identity_digest": str(p19["theorem_identity_digest"]),
        "methodology_anchor_digest": str(p19["methodology_anchor_digest"]),
        "methodology_anchor_count": len(rebuilt),
    }


def replay_subject_roots(root: Path, p19: Mapping[str, object]) -> dict[str, object]:
    for label in sorted(REQUIRED_SUBJECT_ROOTS):
        _subject_root(root, p19, label, rehash=True)
    roots = p19.get("subject_roots")
    assert isinstance(roots, list)
    if sha256_bytes(canonical_json_bytes(roots)) != p19.get("subject_root_manifest_digest"):
        raise P19ExternalReplayError("P19 subject-root aggregate digest mismatch")
    return {"subject_root_manifest_digest": str(p19["subject_root_manifest_digest"]), "subject_root_count": len(roots)}


P19_PAYLOAD_KEYS = (
    "family_id", "generation_id", "repository_commit", "repository_tree", "ledger_schema",
    "ledger_snapshot_digest", "ledger_snapshot", "receipt_chain_tip_digest",
    "stage_evidence_manifest_digest", "stage_evidence", "primary_p9_scientific_authority_digest",
    "primary_anytime_p9_authority_digest", "primary_ccf_oracle_audit_authority_digest",
    "generalization_authority_digest", "fault_tolerance_authority_digest",
    "independent_replication_authority_digest", "statistical_plan_digest", "theorem_identity_digest",
    "methodology_anchor_digest", "methodology_anchors", "subject_root_manifest_digest", "subject_roots",
    "external_replay_input_manifest_digest", "external_replay_inputs",
    "family_p9_supported", "family_generalization_supported", "family_fault_tolerance_supported",
    "family_replication_supported", "family_evidence_complete",
)


def replay_p19_seal(root: Path, p19: Mapping[str, object]) -> dict[str, object]:
    replay_theorem_and_plan_identity(root, p19)
    replay_subject_roots(root, p19)
    for stage in p19.get("stage_evidence", []):
        if not isinstance(stage, Mapping):
            raise P19ExternalReplayError("P19 stage evidence malformed")
        _stage_path(root, p19, str(stage.get("stage", "")))
    _all_external_replay_files(root, p19)
    replay_rows = p19.get("external_replay_inputs")
    if not isinstance(replay_rows, list) or sha256_bytes(canonical_json_bytes(replay_rows)) != p19.get("external_replay_input_manifest_digest"):
        raise P19ExternalReplayError("P19 external replay input aggregate digest mismatch")
    try:
        payload = {key: p19[key] for key in P19_PAYLOAD_KEYS}
    except KeyError as exc:
        raise P19ExternalReplayError("P19 seal payload incomplete") from exc
    rebuilt = sha256_bytes(canonical_json_bytes(payload))
    if rebuilt != p19.get("p19_digest"):
        raise P19ExternalReplayError("P19 seal digest differs from full subject replay")
    return {
        "p19_digest": rebuilt,
        "stage_evidence_manifest_digest": str(p19["stage_evidence_manifest_digest"]),
        "subject_root_manifest_digest": str(p19["subject_root_manifest_digest"]),
        "external_replay_input_manifest_digest": str(p19["external_replay_input_manifest_digest"]),
    }


def replay_primary_p9(root: Path, p19: Mapping[str, object]) -> dict[str, object]:
    declared_scientific_path = _stage_path(root, p19, "P9_SUPPORTED")
    declared_scientific = verify_p9_scientific_authority_v3_document(declared_scientific_path)
    anytime_path = _replay_file(root, p19, "PRIMARY_ANYTIME_P9_AUTHORITY")
    ccf_path = _replay_file(root, p19, "PRIMARY_CCF_ORACLE_AUDIT_AUTHORITY")
    execution_path = _stage_path(root, p19, "CONFIRMATORY_EXECUTED")
    confirmatory_root = _replay_file(root, p19, "CONFIRMATORY_ROOT_AUTHORITY")
    harness = _stage_path(root, p19, "HARNESS_FROZEN")
    execution_freeze = _stage_path(root, p19, "EXECUTION_MANIFESTS_FROZEN")
    materialization = _replay_file(root, p19, "MATERIALIZATION_REFERENCE")
    source_registry = _replay_file(root, p19, "SOURCE_REGISTRY")
    ccf_spec = _stage_path(root, p19, "CCF_SPEC_FROZEN")
    execution_root = _subject_root(root, p19, "PRIMARY_EXECUTION")
    physical_root = _subject_root(root, p19, "PRIMARY_PHYSICAL_COST")
    ccf_root = _subject_root(root, p19, "PRIMARY_CCF")

    try:
        anytime = build_anytime_p9_authority(
            confirmatory_execution_authority_path=execution_path,
            execution_bundle_root=execution_root,
            physical_cost_bundle_root=physical_root,
            confirmatory_root_authority_path=confirmatory_root,
            harness_freeze_path=harness,
            execution_manifest_freeze_path=execution_freeze,
            materialization_reference_path=materialization,
            source_registry_path=source_registry,
        )
        ccf = build_ccf_oracle_audit_authority(
            repository_root=root,
            ccf_spec_authority_path=ccf_spec,
            ccf_evidence_bundle_root=ccf_root,
            confirmatory_execution_authority_path=execution_path,
            execution_bundle_root=execution_root,
            physical_cost_bundle_root=physical_root,
            confirmatory_root_authority_path=confirmatory_root,
            harness_freeze_path=harness,
        )
        scientific = build_p9_scientific_authority_v3(
            anytime_p9_authority_path=anytime_path,
            ccf_oracle_audit_authority_path=ccf_path,
        )
    except RuntimeError as exc:
        raise P19ExternalReplayError("primary P9 raw replay failed") from exc

    expected = (
        (anytime.authority_digest, p19.get("primary_anytime_p9_authority_digest"), "anytime P9"),
        (ccf.authority_digest, p19.get("primary_ccf_oracle_audit_authority_digest"), "CCF"),
        (scientific.authority_digest, p19.get("primary_p9_scientific_authority_digest"), "scientific P9"),
    )
    for observed, sealed, label in expected:
        if observed != sealed:
            raise P19ExternalReplayError(f"recomputed {label} differs from P19")
    if scientific.authority_digest != declared_scientific.get("authority_digest"):
        raise P19ExternalReplayError("P19 stage P9 authority differs from scientific recomputation")
    if not anytime.p9_supported_without_iid_assumption or not ccf.headroom_audit_complete or not scientific.scientific_p9_supported:
        raise P19ExternalReplayError("recomputed primary P9 gate is unsupported")
    return {
        "anytime_p9_authority_digest": anytime.authority_digest,
        "ccf_oracle_audit_authority_digest": ccf.authority_digest,
        "scientific_p9_authority_digest": scientific.authority_digest,
    }


def replay_generalization(root: Path, p19: Mapping[str, object]) -> dict[str, object]:
    registry = _stage_path(root, p19, "GENERALIZATION_REGISTRY_FROZEN")
    sizing = _stage_path(root, p19, "TRIAL_SIZED")
    p9 = _stage_path(root, p19, "P9_SUPPORTED")
    declared_final_path = _stage_path(root, p19, "GENERALIZATION_SUPPORTED")
    declared_final = verify_generalization_anytime_authority_document(declared_final_path)
    axis_paths: dict[GeneralizationAxis, Path] = {}
    axis_digests: dict[str, str] = {}
    for axis in REQUIRED_AXES:
        label = f"{axis.value.split('_', 1)[0]}_AXIS_ANYTIME_AUTHORITY"
        authority_path = _replay_file(root, p19, label)
        bundle_root = _subject_root(root, p19, f"{axis.value.split('_', 1)[0]}_EXECUTION")
        try:
            binding = verify_generalization_source_binding(repository_root=root, registry_path=registry, axis=axis)
            declared_axis = verify_generalization_axis_anytime_authority_document(authority_path)
            rebuilt = build_generalization_axis_anytime_authority(
                bundle_root,
                repository_root=root,
                registry_path=registry,
                trial_sizing_authority_path=sizing,
            )
        except RuntimeError as exc:
            raise P19ExternalReplayError(f"{axis.value} raw/source replay failed") from exc
        if binding.axis != axis.value or declared_axis.get("axis") != axis.value:
            raise P19ExternalReplayError(f"{axis.value} identity mismatch")
        if rebuilt.authority_digest != declared_axis.get("authority_digest"):
            raise P19ExternalReplayError(f"{axis.value} authority differs from raw replay")
        if not rebuilt.axis_supported_without_iid_assumption:
            raise P19ExternalReplayError(f"{axis.value} replay is unsupported")
        axis_paths[axis] = authority_path
        axis_digests[axis.value] = rebuilt.authority_digest
    try:
        final = build_generalization_anytime_authority(
            registry_path=registry,
            p9_scientific_v3_authority_path=p9,
            axis_authority_paths=axis_paths,
        )
    except RuntimeError as exc:
        raise P19ExternalReplayError("G1-G5 composition replay failed") from exc
    if final.authority_digest != p19.get("generalization_authority_digest"):
        raise P19ExternalReplayError("recomputed G1-G5 authority differs from P19")
    if final.authority_digest != declared_final.get("authority_digest") or not final.generalization_supported_without_iid_assumption:
        raise P19ExternalReplayError("recomputed G1-G5 final gate is unsupported/inconsistent")
    return {"generalization_authority_digest": final.authority_digest, "axis_authority_digests": axis_digests}


def replay_fault_tolerance(root: Path, p19: Mapping[str, object]) -> dict[str, object]:
    declared_path = _stage_path(root, p19, "FAULT_TOLERANCE_SUPPORTED")
    declared = verify_fault_tolerance_authority_document(declared_path)
    try:
        rebuilt = build_fault_tolerance_authority(
            _subject_root(root, p19, "FAULT_TOLERANCE"),
            repository_root=root,
            fault_spec_authority_path=_stage_path(root, p19, "FAULT_INJECTION_SPEC_FROZEN"),
            execution_manifest_freeze_path=_stage_path(root, p19, "EXECUTION_MANIFESTS_FROZEN"),
            harness_freeze_path=_stage_path(root, p19, "HARNESS_FROZEN"),
        )
    except RuntimeError as exc:
        raise P19ExternalReplayError("fault-tolerance raw replay failed") from exc
    if rebuilt.authority_digest != p19.get("fault_tolerance_authority_digest"):
        raise P19ExternalReplayError("recomputed fault authority differs from P19")
    if rebuilt.authority_digest != declared.get("authority_digest") or not rebuilt.all_required_cases_supported:
        raise P19ExternalReplayError("recomputed fault gate is unsupported/inconsistent")
    return {"fault_tolerance_authority_digest": rebuilt.authority_digest}


def replay_independent_replication(root: Path, p19: Mapping[str, object]) -> dict[str, object]:
    declared_path = _stage_path(root, p19, "INDEPENDENT_REPLICATION_SUPPORTED")
    declared = verify_independent_replication_authority_v4_document(declared_path)
    try:
        rebuilt = build_independent_replication_authority_v4(
            primary_p9_scientific_authority_path=_stage_path(root, p19, "P9_SUPPORTED"),
            primary_anytime_p9_authority_path=_replay_file(root, p19, "PRIMARY_ANYTIME_P9_AUTHORITY"),
            primary_ccf_oracle_audit_authority_path=_replay_file(root, p19, "PRIMARY_CCF_ORACLE_AUDIT_AUTHORITY"),
            primary_generalization_authority_path=_stage_path(root, p19, "GENERALIZATION_SUPPORTED"),
            replica_p9_scientific_authority_path=_replay_file(root, p19, "REPLICA_P9_SCIENTIFIC_AUTHORITY"),
            replica_anytime_p9_authority_path=_replay_file(root, p19, "REPLICA_ANYTIME_P9_AUTHORITY"),
            replica_ccf_oracle_audit_authority_path=_replay_file(root, p19, "REPLICA_CCF_ORACLE_AUDIT_AUTHORITY"),
            replica_execution_authority_path=_replay_file(root, p19, "REPLICA_EXECUTION_AUTHORITY"),
            replica_execution_bundle_root=_subject_root(root, p19, "REPLICA_EXECUTION"),
            replica_physical_cost_bundle_root=_subject_root(root, p19, "REPLICA_PHYSICAL_COST"),
            replica_confirmatory_root_authority_path=_replay_file(root, p19, "REPLICA_CONFIRMATORY_ROOT_AUTHORITY"),
            harness_freeze_path=_stage_path(root, p19, "HARNESS_FROZEN"),
            execution_manifest_freeze_path=_stage_path(root, p19, "EXECUTION_MANIFESTS_FROZEN"),
            materialization_reference_path=_replay_file(root, p19, "MATERIALIZATION_REFERENCE"),
            source_registry_path=_replay_file(root, p19, "SOURCE_REGISTRY"),
            ccf_spec_authority_path=_stage_path(root, p19, "CCF_SPEC_FROZEN"),
            replica_ccf_evidence_bundle_root=_subject_root(root, p19, "REPLICA_CCF"),
            repository_root=root,
            attestation_path=_replay_file(root, p19, "REPLICATION_ATTESTATION"),
            signature_path=_replay_file(root, p19, "REPLICATION_SIGNATURE"),
            allowed_signers_path=_replay_file(root, p19, "REPLICATION_ALLOWED_SIGNERS"),
        )
    except RuntimeError as exc:
        raise P19ExternalReplayError("independent replication raw/signature replay failed") from exc
    if rebuilt.authority_digest != p19.get("independent_replication_authority_digest"):
        raise P19ExternalReplayError("recomputed replication authority differs from P19")
    if rebuilt.authority_digest != declared.get("authority_digest") or not rebuilt.independent_replication_supported:
        raise P19ExternalReplayError("recomputed replication gate is unsupported/inconsistent")
    if rebuilt.social_independence_machine_proven:
        raise P19ExternalReplayError("replication illegally claims machine-proven social independence")
    return {
        "independent_replication_authority_digest": rebuilt.authority_digest,
        "replication_package_digest": rebuilt.replication_package_digest,
        "social_independence_machine_proven": False,
    }


CHECK_HANDLERS: dict[str, Callable[[Path, Mapping[str, object]], dict[str, object]]] = {
    "REPOSITORY_IDENTITY": replay_repository_identity,
    "THEOREM_AND_PLAN_IDENTITY": replay_theorem_and_plan_identity,
    "SUBJECT_ROOT_REHASH": replay_subject_roots,
    "P19_SEAL_REBUILD": replay_p19_seal,
    "PRIMARY_P9_RAW_REPLAY": replay_primary_p9,
    "GENERALIZATION_G1_G5_RAW_REPLAY": replay_generalization,
    "FAULT_TOLERANCE_RAW_REPLAY": replay_fault_tolerance,
    "INDEPENDENT_REPLICATION_RAW_REPLAY": replay_independent_replication,
}


def run_external_p19_check(*, repository_root: Path, p19_path: Path, check_id: str) -> dict[str, object]:
    root = Path(repository_root).resolve()
    if check_id not in CHECK_HANDLERS or check_id not in CHECK_METHOD_IDS:
        raise P19ExternalReplayError("unknown external P19 check")
    p19_file, p19 = _load_p19(root, Path(p19_path))
    details = CHECK_HANDLERS[check_id](root, p19)
    payload = {
        "check_id": check_id,
        "method_id": CHECK_METHOD_IDS[check_id],
        "family_id": str(p19.get("family_id", "")),
        "p19_path": p19_file.relative_to(root).as_posix(),
        "p19_sha256": sha256_file(p19_file),
        "p19_digest": str(p19.get("p19_digest", "")),
        "repository_commit": str(p19.get("repository_commit", "")),
        "repository_tree": str(p19.get("repository_tree", "")),
        "result": "PASS",
        "details": details,
        "product_qualification_authorized": False,
    }
    return {"schema": EVIDENCE_SCHEMA, **payload, "evidence_digest": sha256_bytes(canonical_json_bytes(payload))}
