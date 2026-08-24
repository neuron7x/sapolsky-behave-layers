from __future__ import annotations

import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Sequence

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes
from cwc.governance.product_qualification_pointer import VerifiedProductQualificationPointer

SCHEMA = "DGC_EVIDENCE_PACKAGING_AUTHORITY_V1"
DELTA_POLICY = "DGC_APPEND_ONLY_POST_OUTCOME_PACKAGING_POLICY_V1"
REGULAR_BLOB_MODES = frozenset({"100644", "100755"})

# These files are mirrors/terminal packaging metadata, never scientific-method authority.
ALLOWED_MUTABLE_EXACT = frozenset({
    "artifacts/dgc-product-v1/PRODUCT_QUALIFICATION_POINTER_V2.json",
    "artifacts/dgc-product-v1/evidence_status.json",
})

# Newly generated evidence may be committed only under explicitly evidence-only namespaces.
# Pre-outcome preregistration, source, scorer, policy, workflow and theorem files are outside
# these namespaces and therefore cannot change after the qualified execution source revision.
ALLOWED_ADDED_PREFIXES = (
    "artifacts/dgc-product-v1/generated/",
    "artifacts/dgc-product-v1/evidence/",
    "eval_bundle/",
    "release_evidence/",
)


class EvidencePackagingAuthorityError(RuntimeError):
    pass


Runner = Callable[..., subprocess.CompletedProcess[str]]


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise EvidencePackagingAuthorityError(f"{name} must be lowercase SHA-256")
    return text


def _oid(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 40 or any(ch not in "0123456789abcdef" for ch in text):
        raise EvidencePackagingAuthorityError(f"{name} must be lowercase 40-hex Git object id")
    return text


def _git(
    root: Path,
    args: Sequence[str],
    *,
    runner: Runner = subprocess.run,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        return runner(
            ["git", "-C", str(root), *args],
            check=check,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise EvidencePackagingAuthorityError(f"git command failed: {' '.join(args)}") from exc


def _canonical_delta_path(path: str) -> str:
    if not path or path != path.strip():
        raise EvidencePackagingAuthorityError("packaging delta path must not contain surrounding whitespace")
    if any(ch in path for ch in ("\x00", "\n", "\r", "\t", "\\")):
        raise EvidencePackagingAuthorityError("packaging delta path contains forbidden control/ambiguous character")
    if path.startswith("/") or "//" in path or path.endswith("/"):
        raise EvidencePackagingAuthorityError("packaging delta path is not canonical repository-relative form")
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise EvidencePackagingAuthorityError("packaging delta path contains non-canonical component")
    return path


def _allowed_add(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in ALLOWED_ADDED_PREFIXES)


def _parse_name_status_z(raw: str) -> tuple[tuple[str, str], ...]:
    # --no-renames makes the stream regular: STATUS\0PATH\0 pairs.
    parts = raw.split("\0")
    if parts and parts[-1] == "":
        parts.pop()
    if len(parts) % 2:
        raise EvidencePackagingAuthorityError("malformed git name-status stream")
    rows: list[tuple[str, str]] = []
    for index in range(0, len(parts), 2):
        status = parts[index].strip()
        path = _canonical_delta_path(parts[index + 1])
        if not status:
            raise EvidencePackagingAuthorityError("malformed packaging delta row")
        rows.append((status, path))
    return tuple(rows)


def _tree_entry(root: Path, commit: str, path: str, *, runner: Runner) -> tuple[str, str]:
    path = _canonical_delta_path(path)
    proc = _git(root, ("ls-tree", commit, "--", path), runner=runner)
    line = proc.stdout.rstrip("\n")
    if not line or "\t" not in line:
        raise EvidencePackagingAuthorityError(f"Git tree entry missing for packaging path: {path}")
    meta, observed_path = line.split("\t", 1)
    fields = meta.split()
    if len(fields) != 3 or fields[1] != "blob" or observed_path != path:
        raise EvidencePackagingAuthorityError(f"unsupported/non-blob packaging tree entry: {path}")
    mode, _, oid = fields
    if mode not in REGULAR_BLOB_MODES:
        raise EvidencePackagingAuthorityError(
            f"post-outcome packaging requires regular Git files; symlink/special mode rejected: {mode} {path}"
        )
    _oid("blob oid", oid)
    return mode, oid


@dataclass(frozen=True, slots=True)
class PackagingDeltaRow:
    status: str
    path: str
    execution_mode: str | None
    execution_blob_oid: str | None
    packaging_mode: str
    packaging_blob_oid: str
    row_digest: str


@dataclass(frozen=True, slots=True)
class EvidencePackagingAuthority:
    qualified_generation_id: str
    qualified_execution_commit: str
    qualified_execution_tree: str
    qualification_pointer_digest: str
    global_v4_authority_digest: str
    terminal_ledger_tip_receipt_digest: str
    packaging_commit: str
    packaging_tree: str
    delta_policy: str
    allowed_mutable_exact: tuple[str, ...]
    allowed_added_prefixes: tuple[str, ...]
    delta_rows: tuple[PackagingDeltaRow, ...]
    delta_manifest_digest: str
    protected_execution_source_unchanged: bool
    execution_revision_is_ancestor: bool
    tracked_packaging_tree_clean: bool
    slsa_conformance_claim: bool
    authority_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            **asdict(self),
            "execution_source_identity_distinct_from_packaging_identity": True,
            "product_qualified": True,
            "production_control_authorized": False,
        }


def build_evidence_packaging_authority(
    *,
    repository_root: Path,
    qualification: VerifiedProductQualificationPointer,
    packaging_commit: str | None = None,
    runner: Runner = subprocess.run,
) -> EvidencePackagingAuthority:
    root = Path(repository_root).resolve()
    if not root.is_dir():
        raise EvidencePackagingAuthorityError("repository root missing")

    execution_commit = _oid("qualified execution commit", qualification.repo_commit)
    execution_tree = _oid("qualified execution tree", qualification.repo_tree)

    resolved_execution_tree = _git(
        root, ("rev-parse", f"{execution_commit}^{{tree}}"), runner=runner
    ).stdout.strip().lower()
    if _oid("resolved execution tree", resolved_execution_tree) != execution_tree:
        raise EvidencePackagingAuthorityError("qualified execution commit/tree identity mismatch")

    current_commit = (
        _oid("packaging commit", packaging_commit)
        if packaging_commit is not None
        else _oid("packaging commit", _git(root, ("rev-parse", "HEAD"), runner=runner).stdout.strip())
    )
    packaging_tree = _oid(
        "packaging tree", _git(root, ("rev-parse", f"{current_commit}^{{tree}}"), runner=runner).stdout.strip()
    )

    dirty = _git(root, ("status", "--porcelain=v1", "--untracked-files=no"), runner=runner).stdout.strip()
    if dirty:
        raise EvidencePackagingAuthorityError("tracked packaging working tree must be clean")

    ancestor = _git(
        root,
        ("merge-base", "--is-ancestor", execution_commit, current_commit),
        runner=runner,
        check=False,
    )
    if ancestor.returncode != 0:
        raise EvidencePackagingAuthorityError("qualified execution revision is not an ancestor of packaging revision")

    diff = _git(
        root,
        ("diff", "--name-status", "-z", "--no-renames", execution_commit, current_commit, "--"),
        runner=runner,
    )
    raw_rows = _parse_name_status_z(diff.stdout)
    verified: list[PackagingDeltaRow] = []
    for status, path in raw_rows:
        if status == "A":
            if not _allowed_add(path):
                raise EvidencePackagingAuthorityError(
                    f"post-outcome packaging added path outside evidence-only namespaces: {path}"
                )
            execution_mode = None
            execution_blob = None
        elif status == "M":
            if path not in ALLOWED_MUTABLE_EXACT:
                raise EvidencePackagingAuthorityError(
                    f"post-outcome packaging modified protected execution-source path: {path}"
                )
            execution_mode, execution_blob = _tree_entry(root, execution_commit, path, runner=runner)
        else:
            # Deletions, type changes, unresolved states and every other status are forbidden.
            raise EvidencePackagingAuthorityError(
                f"post-outcome packaging delta status is not append-only/approved-mutable: {status} {path}"
            )

        packaging_mode, packaging_blob = _tree_entry(root, current_commit, path, runner=runner)
        if execution_mode is not None and execution_mode != packaging_mode:
            raise EvidencePackagingAuthorityError(f"approved mutable path changed Git mode: {path}")
        payload = {
            "status": status,
            "path": path,
            "execution_mode": execution_mode,
            "execution_blob_oid": execution_blob,
            "packaging_mode": packaging_mode,
            "packaging_blob_oid": packaging_blob,
        }
        verified.append(PackagingDeltaRow(
            **payload,
            row_digest=sha256_bytes(canonical_json_bytes(payload)),
        ))

    ordered = tuple(sorted(verified, key=lambda row: row.path))
    delta_payload = [
        {
            "status": row.status,
            "path": row.path,
            "execution_mode": row.execution_mode,
            "execution_blob_oid": row.execution_blob_oid,
            "packaging_mode": row.packaging_mode,
            "packaging_blob_oid": row.packaging_blob_oid,
            "row_digest": row.row_digest,
        }
        for row in ordered
    ]
    delta_digest = sha256_bytes(canonical_json_bytes(delta_payload))
    payload = {
        "qualified_generation_id": qualification.generation_id,
        "qualified_execution_commit": execution_commit,
        "qualified_execution_tree": execution_tree,
        "qualification_pointer_digest": _sha("qualification pointer digest", qualification.pointer_digest),
        "global_v4_authority_digest": _sha("global V4 authority digest", qualification.global_v4_authority_digest),
        "terminal_ledger_tip_receipt_digest": _sha(
            "terminal ledger tip receipt digest", qualification.ledger_tip_receipt_digest
        ),
        "packaging_commit": current_commit,
        "packaging_tree": packaging_tree,
        "delta_policy": DELTA_POLICY,
        "allowed_mutable_exact": sorted(ALLOWED_MUTABLE_EXACT),
        "allowed_added_prefixes": list(ALLOWED_ADDED_PREFIXES),
        "delta_rows": delta_payload,
        "delta_manifest_digest": delta_digest,
        "protected_execution_source_unchanged": True,
        "execution_revision_is_ancestor": True,
        "tracked_packaging_tree_clean": True,
        "slsa_conformance_claim": False,
    }
    return EvidencePackagingAuthority(
        qualified_generation_id=qualification.generation_id,
        qualified_execution_commit=execution_commit,
        qualified_execution_tree=execution_tree,
        qualification_pointer_digest=payload["qualification_pointer_digest"],
        global_v4_authority_digest=payload["global_v4_authority_digest"],
        terminal_ledger_tip_receipt_digest=payload["terminal_ledger_tip_receipt_digest"],
        packaging_commit=current_commit,
        packaging_tree=packaging_tree,
        delta_policy=DELTA_POLICY,
        allowed_mutable_exact=tuple(sorted(ALLOWED_MUTABLE_EXACT)),
        allowed_added_prefixes=tuple(ALLOWED_ADDED_PREFIXES),
        delta_rows=ordered,
        delta_manifest_digest=delta_digest,
        protected_execution_source_unchanged=True,
        execution_revision_is_ancestor=True,
        tracked_packaging_tree_clean=True,
        slsa_conformance_claim=False,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )
