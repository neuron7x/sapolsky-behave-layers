from __future__ import annotations

import json
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
from cwc.governance.p19_verifier_policy import load_p19_verifier_trust_policy, resolve_allowed_signers
from cwc.governance.product_qualification_pointer import (
    CANONICAL_POINTER_PATH,
    VerifiedProductQualificationPointer,
    load_product_qualification_pointer,
    verify_product_qualification_pointer,
)

SCHEMA = "DGC_QUALIFIED_EVIDENCE_BUNDLE_AUTHORITY_V1"
ROLE_EXECUTION_SOURCE = "EXECUTION_SOURCE_T0"
ROLE_PACKAGING_EVIDENCE = "PACKAGING_EVIDENCE_T1"
REGULAR_GIT_MODES = frozenset({"100644", "100755"})


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
    raw = str(value)
    if not raw or raw != raw.strip():
        raise QualifiedEvidenceBundleError(f"{label} must not contain surrounding whitespace")
    if any(ch in raw for ch in ("\x00", "\n", "\r", "\t", "\\")):
        raise QualifiedEvidenceBundleError(f"{label} contains forbidden control/ambiguous character")
    rel = PurePosixPath(raw)
    canonical = rel.as_posix()
    if (
        rel.is_absolute()
        or ".." in rel.parts
        or "." in rel.parts
        or canonical != raw
        or raw.startswith("/")
        or raw.endswith("/")
        or "//" in raw
    ):
        raise QualifiedEvidenceBundleError(f"{label} must be a canonical repository-relative POSIX path")
    return canonical


def _safe_file(root: Path, rel: str) -> Path:
    rel = _safe_rel(rel, label="qualified bundle path")
    path = root / rel
    if path.is_symlink():
        raise QualifiedEvidenceBundleError(f"qualified bundle symlink rejected: {rel}")
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise QualifiedEvidenceBundleError(f"qualified bundle path escapes repository: {rel}") from exc
    if not resolved.is_file() or resolved.stat().st_size <= 0:
        raise QualifiedEvidenceBundleError(f"qualified bundle file missing/empty: {rel}")
    return resolved


def _tree_entry(root: Path, commit: str, rel: str) -> tuple[str, str] | None:
    rel = _safe_rel(rel, label="Git tree lookup path")
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
    if mode not in REGULAR_GIT_MODES:
        raise QualifiedEvidenceBundleError(f"qualified bundle requires regular Git file mode: {mode} {rel}")
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
    p19_rel = _safe_rel(p19_rel, label="family P19 path")
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
            combined = (PurePosixPath(root_rel) / child).as_posix()
            collected.add(_safe_rel(combined, label="P19 subject-root resolved child"))
    return collected


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
    global_v4_authority_digest: str
    packaging_authority_digest: str
    required_files: tuple[QualifiedBundleFile, ...]
    required_file_manifest_digest: str
    execution_source_file_count: int
    packaging_evidence_file_count: int
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
) -> tuple[
    VerifiedProductQualificationPointer,
    EvidencePackagingAuthority,
    QualifiedEvidenceBundleAuthority,
]:
    root = Path(repository_root).resolve()
    pointer_file = pointer_path if pointer_path.is_absolute() else root / pointer_path
    pointer_doc = load_product_qualification_pointer(pointer_file)
    qualification = verify_product_qualification_pointer(
        repository_root=root,
        pointer_path=pointer_file,
    )
    packaging = build_evidence_packaging_authority(
        repository_root=root,
        qualification=qualification,
    )

    try:
        pointer_rel = pointer_file.resolve().relative_to(root).as_posix()
    except ValueError as exc:
        raise QualifiedEvidenceBundleError("qualification pointer escapes repository") from exc

    required: set[str] = {
        _safe_rel(pointer_rel, label="qualification pointer"),
        _safe_rel(qualification.ledger_path, label="qualification ledger"),
        _safe_rel(qualification.global_v4_authority_path, label="global V4 authority"),
        _safe_rel(qualification.source_registry_path, label="source registry"),
        _safe_rel(qualification.p19_verifier_policy_path, label="P19 verifier policy"),
    }
    p19_paths = _pair(pointer_doc, "family_p19_paths")
    attestation_paths = _pair(pointer_doc, "family_attestation_paths")
    report_paths = _pair(pointer_doc, "family_verification_report_paths")
    signature_paths = _pair(pointer_doc, "family_signature_paths")
    required.update(p19_paths)
    required.update(attestation_paths)
    required.update(report_paths)
    required.update(signature_paths)

    policy = load_p19_verifier_trust_policy(
        _safe_file(root, _safe_rel(qualification.p19_verifier_policy_path, label="P19 verifier policy"))
    )
    allowed_signers = resolve_allowed_signers(policy, repository_root=root)
    try:
        allowed_rel = allowed_signers.relative_to(root).as_posix()
    except ValueError as exc:
        raise QualifiedEvidenceBundleError("allowed-signers trust store escapes repository") from exc
    required.add(_safe_rel(allowed_rel, label="allowed-signers trust store"))

    for p19_rel in p19_paths:
        required.update(_collect_p19_paths(root, p19_rel))

    records: list[QualifiedBundleFile] = []
    for rel in sorted(required):
        path = _safe_file(root, rel)
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
        records.append(QualifiedBundleFile(
            **payload,
            record_digest=sha256_bytes(canonical_json_bytes(payload)),
        ))

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
        "global_v4_authority_digest": qualification.global_v4_authority_digest,
        "packaging_authority_digest": packaging.authority_digest,
        "required_files": manifest_rows,
        "required_file_manifest_digest": manifest_digest,
        "execution_source_file_count": source_count,
        "packaging_evidence_file_count": evidence_count,
        "all_required_subjects_git_bound": True,
        "evidence_graph_complete": True,
    }
    authority = QualifiedEvidenceBundleAuthority(
        qualified_execution_commit=qualification.repo_commit,
        qualified_execution_tree=qualification.repo_tree,
        packaging_commit=packaging.packaging_commit,
        packaging_tree=packaging.packaging_tree,
        qualification_pointer_digest=qualification.pointer_digest,
        global_v4_authority_digest=qualification.global_v4_authority_digest,
        packaging_authority_digest=packaging.authority_digest,
        required_files=ordered,
        required_file_manifest_digest=manifest_digest,
        execution_source_file_count=source_count,
        packaging_evidence_file_count=evidence_count,
        all_required_subjects_git_bound=True,
        evidence_graph_complete=True,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )
    return qualification, packaging, authority
