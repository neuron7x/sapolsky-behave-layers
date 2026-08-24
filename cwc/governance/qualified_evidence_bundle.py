from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping

from cwc.governance.evidence_packaging_authority import (
    ALLOWED_ADDED_PREFIXES,
    ALLOWED_MUTABLE_EXACT,
    EvidencePackagingAuthority,
    build_evidence_packaging_authority,
)
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.p19_evidence_root import verify_family_p19_evidence_root_document
from cwc.governance.p19_external_verification_plan import load_p19_external_verification_plan
from cwc.governance.p19_verification_attestation import load_p19_verification_report
from cwc.governance.p19_verifier_policy import load_p19_verifier_trust_policy, resolve_allowed_signers
from cwc.governance.product_qualification_pointer import (
    CANONICAL_POINTER_PATH,
    VerifiedProductQualificationPointer,
    load_product_qualification_pointer,
    verify_product_qualification_pointer,
)

SCHEMA = "DGC_QUALIFIED_EVIDENCE_BUNDLE_AUTHORITY_V5"
ROLE_EXECUTION_SOURCE = "EXECUTION_SOURCE_T0"
ROLE_PACKAGING_EVIDENCE = "PACKAGING_EVIDENCE_T1"


class QualifiedEvidenceBundleError(RuntimeError):
    pass


def _git(root: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", "-C", str(root), *args],
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise QualifiedEvidenceBundleError(f"git command failed: {' '.join(args)}") from exc


def _safe_rel(value: object, *, label: str) -> str:
    text = str(value)
    if (
        not text
        or text != text.strip()
        or any(ch in text for ch in ("\x00", "\n", "\r", "\t", "\\"))
        or "//" in text
    ):
        raise QualifiedEvidenceBundleError(f"{label} must be a canonical repository-relative POSIX path")
    rel = PurePosixPath(text)
    if rel.is_absolute() or any(part in ("", ".", "..") for part in rel.parts):
        raise QualifiedEvidenceBundleError(f"{label} must be a canonical repository-relative POSIX path")
    return rel.as_posix()


def _safe_file(root: Path, rel: str, *, allow_empty: bool = False) -> Path:
    path = root / rel
    if path.is_symlink():
        raise QualifiedEvidenceBundleError(f"qualified bundle symlink rejected: {rel}")
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise QualifiedEvidenceBundleError(f"qualified bundle path escapes repository: {rel}") from exc
    if not resolved.is_file():
        raise QualifiedEvidenceBundleError(f"qualified bundle file missing: {rel}")
    if not allow_empty and resolved.stat().st_size <= 0:
        raise QualifiedEvidenceBundleError(f"qualified bundle file empty: {rel}")
    return resolved


def _tree_entry(root: Path, commit: str, rel: str) -> tuple[str, str] | None:
    proc = _git(root, "ls-tree", commit, "--", rel)
    line = proc.stdout.rstrip("\n")
    if not line:
        return None
    if "\t" not in line:
        raise QualifiedEvidenceBundleError(f"malformed Git tree entry: {rel}")
    meta, observed = line.split("\t", 1)
    fields = meta.split()
    if len(fields) != 3 or fields[1] != "blob" or observed != rel:
        raise QualifiedEvidenceBundleError(f"qualified bundle path is not a regular Git blob: {rel}")
    mode, _, oid = fields
    if mode not in {"100644", "100755"}:
        raise QualifiedEvidenceBundleError(f"qualified bundle Git object mode rejected: {rel}")
    if len(oid) != 40 or any(ch not in "0123456789abcdef" for ch in oid.lower()):
        raise QualifiedEvidenceBundleError(f"qualified bundle Git blob OID malformed: {rel}")
    return mode, oid.lower()


def _allowed_packaging_path(rel: str) -> bool:
    return rel in ALLOWED_MUTABLE_EXACT or any(rel.startswith(prefix) for prefix in ALLOWED_ADDED_PREFIXES)


def _pair(doc: Mapping[str, object], field: str) -> tuple[str, str]:
    value = doc.get(field)
    if not isinstance(value, list) or len(value) != 2:
        raise QualifiedEvidenceBundleError(f"qualification pointer {field} must contain exactly two paths")
    return (
        _safe_rel(value[0], label=f"{field}[0]"),
        _safe_rel(value[1], label=f"{field}[1]"),
    )


def _collect_p19_paths(root: Path, p19_rel: str) -> set[str]:
    doc = verify_family_p19_evidence_root_document(_safe_file(root, p19_rel))
    collected = {p19_rel}
    stage_rows = doc.get("stage_evidence")
    if not isinstance(stage_rows, list):
        raise QualifiedEvidenceBundleError("P19 stage evidence population missing")
    for row in stage_rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("evidence"), Mapping):
            raise QualifiedEvidenceBundleError("P19 stage evidence row malformed")
        collected.add(_safe_rel(row["evidence"].get("path"), label="P19 stage evidence path"))
    anchors = doc.get("methodology_anchors")
    if not isinstance(anchors, list):
        raise QualifiedEvidenceBundleError("P19 methodology anchor population missing")
    for row in anchors:
        if not isinstance(row, Mapping):
            raise QualifiedEvidenceBundleError("P19 methodology anchor row malformed")
        collected.add(_safe_rel(row.get("path"), label="P19 methodology anchor path"))
    replay_inputs = doc.get("external_replay_inputs")
    if not isinstance(replay_inputs, list) or not replay_inputs:
        raise QualifiedEvidenceBundleError("P19 portable replay-input population missing")
    for row in replay_inputs:
        if not isinstance(row, Mapping):
            raise QualifiedEvidenceBundleError("P19 replay-input row malformed")
        collected.add(_safe_rel(row.get("path"), label="P19 external replay input path"))
    roots = doc.get("subject_roots")
    if not isinstance(roots, list):
        raise QualifiedEvidenceBundleError("P19 subject-root population missing")
    for row in roots:
        if not isinstance(row, Mapping):
            raise QualifiedEvidenceBundleError("P19 subject-root row malformed")
        root_rel = _safe_rel(row.get("path"), label="P19 subject root")
        files = row.get("files")
        if not isinstance(files, list) or not files:
            raise QualifiedEvidenceBundleError("P19 subject root must disclose non-empty file population")
        for file_row in files:
            if not isinstance(file_row, Mapping):
                raise QualifiedEvidenceBundleError("P19 subject-root file row malformed")
            child = _safe_rel(file_row.get("path"), label="P19 subject-root child")
            collected.add((PurePosixPath(root_rel) / child).as_posix())
    return collected


def _collect_verification_transcript_paths(root: Path, report_rel: str) -> tuple[set[str], set[str]]:
    report = load_p19_verification_report(_safe_file(root, report_rel), repository_root=root)
    plan_rel = _safe_rel(report.get("verification_plan_path"), label="P19 verification plan path")
    entry_rel = _safe_rel(report.get("verifier_entrypoint_path"), label="P19 verifier entrypoint path")
    try:
        plan = load_p19_external_verification_plan(root / plan_rel, repository_root=root, require_active=True)
    except RuntimeError as exc:
        raise QualifiedEvidenceBundleError("P19 verifier plan dependency replay failed") from exc
    collected = {report_rel, plan_rel, entry_rel}
    for row in plan.verifier_dependencies:
        collected.add(_safe_rel(row.get("path"), label="P19 verifier dependency path"))
    empty_allowed: set[str] = set()
    checks = report.get("checks")
    if not isinstance(checks, list) or not checks:
        raise QualifiedEvidenceBundleError("P19 verification report transcript population missing")
    for row in checks:
        if not isinstance(row, Mapping):
            raise QualifiedEvidenceBundleError("P19 verification report transcript row malformed")
        for role in ("receipt", "stdout", "stderr", "evidence"):
            rel = _safe_rel(row.get(f"{role}_path"), label=f"P19 verifier {role} path")
            collected.add(rel)
            if role in {"stdout", "stderr"}:
                empty_allowed.add(rel)
    return collected, empty_allowed


@dataclass(frozen=True, slots=True)
class QualifiedBundleFile:
    path: str
    role: str
    sha256: str
    bytes: int
    git_mode: str
    git_blob_oid: str
    record_digest: str


@dataclass(frozen=True, slots=True)
class QualifiedEvidenceBundleAuthority:
    qualified_execution_commit: str
    qualified_execution_tree: str
    packaging_commit: str
    packaging_tree: str
    qualification_pointer_digest: str
    global_v5_authority_digest: str
    packaging_authority_digest: str
    required_files: tuple[QualifiedBundleFile, ...]
    required_file_manifest_digest: str
    execution_source_file_count: int
    packaging_evidence_file_count: int
    raw_p19_verification_transcripts_included: bool
    frozen_verification_plan_and_entrypoint_included: bool
    frozen_verifier_dependency_closure_included: bool
    portable_p19_replay_inputs_included: bool
    portable_global_v5_authority_included: bool
    all_required_subjects_git_bound: bool
    evidence_graph_complete: bool
    authority_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            **asdict(self),
            "product_qualified": True,
            "production_control_authorized": False,
        }


def build_qualified_evidence_bundle_authority(
    *,
    repository_root: Path,
    pointer_path: Path = Path(CANONICAL_POINTER_PATH),
) -> tuple[VerifiedProductQualificationPointer, EvidencePackagingAuthority, QualifiedEvidenceBundleAuthority]:
    root = Path(repository_root).resolve()
    pointer_file = pointer_path if pointer_path.is_absolute() else root / pointer_path
    pointer_doc = load_product_qualification_pointer(pointer_file)
    qualification = verify_product_qualification_pointer(repository_root=root, pointer_path=pointer_file)
    packaging = build_evidence_packaging_authority(repository_root=root, qualification=qualification)

    required: set[str] = {
        _safe_rel(pointer_file.resolve().relative_to(root).as_posix(), label="qualification pointer"),
        _safe_rel(qualification.ledger_path, label="qualification ledger"),
        _safe_rel(qualification.global_v5_authority_path, label="global V5 authority"),
        _safe_rel(qualification.source_registry_path, label="source registry"),
        _safe_rel(qualification.p19_verifier_policy_path, label="P19 verifier policy"),
    }
    empty_allowed: set[str] = set()
    p19_paths = _pair(pointer_doc, "family_p19_paths")
    attestation_paths = _pair(pointer_doc, "family_attestation_paths")
    report_paths = _pair(pointer_doc, "family_verification_report_paths")
    signature_paths = _pair(pointer_doc, "family_signature_paths")
    required.update(p19_paths)
    required.update(attestation_paths)
    required.update(signature_paths)

    policy = load_p19_verifier_trust_policy(
        _safe_file(root, _safe_rel(qualification.p19_verifier_policy_path, label="P19 verifier policy"))
    )
    allowed_signers = resolve_allowed_signers(policy, repository_root=root)
    required.add(allowed_signers.relative_to(root).as_posix())
    for p19_rel in p19_paths:
        required.update(_collect_p19_paths(root, p19_rel))
    for report_rel in report_paths:
        paths, zero_ok = _collect_verification_transcript_paths(root, report_rel)
        required.update(paths)
        empty_allowed.update(zero_ok)

    records: list[QualifiedBundleFile] = []
    for rel in sorted(required):
        path = _safe_file(root, rel, allow_empty=rel in empty_allowed)
        exec_entry = _tree_entry(root, qualification.repo_commit, rel)
        pkg_entry = _tree_entry(root, packaging.packaging_commit, rel)
        if pkg_entry is None:
            raise QualifiedEvidenceBundleError(f"required qualification subject is not tracked in T_pkg: {rel}")
        if rel in ALLOWED_MUTABLE_EXACT:
            role = ROLE_PACKAGING_EVIDENCE
        elif exec_entry is not None:
            if exec_entry != pkg_entry:
                raise QualifiedEvidenceBundleError(f"execution-source subject changed in packaging revision: {rel}")
            role = ROLE_EXECUTION_SOURCE
        else:
            if not _allowed_packaging_path(rel):
                raise QualifiedEvidenceBundleError(
                    f"post-outcome required subject is outside evidence-only packaging namespaces: {rel}"
                )
            role = ROLE_PACKAGING_EVIDENCE
        mode, blob_oid = pkg_entry
        payload = {
            "path": rel,
            "role": role,
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
            "git_mode": mode,
            "git_blob_oid": blob_oid,
        }
        records.append(QualifiedBundleFile(**payload, record_digest=sha256_bytes(canonical_json_bytes(payload))))

    ordered = tuple(records)
    manifest_rows = [asdict(row) for row in ordered]
    manifest_digest = sha256_bytes(canonical_json_bytes(manifest_rows))
    source_count = sum(row.role == ROLE_EXECUTION_SOURCE for row in ordered)
    evidence_count = sum(row.role == ROLE_PACKAGING_EVIDENCE for row in ordered)
    if source_count == 0 or evidence_count == 0:
        raise QualifiedEvidenceBundleError("qualified release requires both execution-source and packaging-evidence subjects")

    payload = {
        "qualified_execution_commit": qualification.repo_commit,
        "qualified_execution_tree": qualification.repo_tree,
        "packaging_commit": packaging.packaging_commit,
        "packaging_tree": packaging.packaging_tree,
        "qualification_pointer_digest": qualification.pointer_digest,
        "global_v5_authority_digest": qualification.global_v5_authority_digest,
        "packaging_authority_digest": packaging.authority_digest,
        "required_files": manifest_rows,
        "required_file_manifest_digest": manifest_digest,
        "execution_source_file_count": source_count,
        "packaging_evidence_file_count": evidence_count,
        "raw_p19_verification_transcripts_included": True,
        "frozen_verification_plan_and_entrypoint_included": True,
        "frozen_verifier_dependency_closure_included": True,
        "portable_p19_replay_inputs_included": True,
        "portable_global_v5_authority_included": True,
        "all_required_subjects_git_bound": True,
        "evidence_graph_complete": True,
    }
    authority = QualifiedEvidenceBundleAuthority(
        qualified_execution_commit=qualification.repo_commit,
        qualified_execution_tree=qualification.repo_tree,
        packaging_commit=packaging.packaging_commit,
        packaging_tree=packaging.packaging_tree,
        qualification_pointer_digest=qualification.pointer_digest,
        global_v5_authority_digest=qualification.global_v5_authority_digest,
        packaging_authority_digest=packaging.authority_digest,
        required_files=ordered,
        required_file_manifest_digest=manifest_digest,
        execution_source_file_count=source_count,
        packaging_evidence_file_count=evidence_count,
        raw_p19_verification_transcripts_included=True,
        frozen_verification_plan_and_entrypoint_included=True,
        frozen_verifier_dependency_closure_included=True,
        portable_p19_replay_inputs_included=True,
        portable_global_v5_authority_included=True,
        all_required_subjects_git_bound=True,
        evidence_graph_complete=True,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )
    return qualification, packaging, authority
