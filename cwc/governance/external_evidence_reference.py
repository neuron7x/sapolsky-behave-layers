from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.materialization_transaction import (
    AtomicEvidenceGeneration,
    canonical_json_bytes,
    file_manifest,
    sha256_bytes,
    sha256_file,
)

REFERENCE_SCHEMA = "DGC_EXTERNAL_EVIDENCE_REFERENCE_V1"
GENERATION_MANIFEST_SCHEMA = "DGC_EVIDENCE_GENERATION_MANIFEST_V2"
MATERIALIZATION_RECEIPT_SCHEMA = "DGC_EXTERNAL_MATERIALIZATION_RECEIPT_V2"
MATERIALIZATION_PROVENANCE_SCHEMA = "DGC_MATERIALIZATION_PROVENANCE_V1"
_REQUIRED_FAMILIES = frozenset({"SWE_BENCH_VERIFIED", "TERMINAL_BENCH_2_1"})


class ExternalEvidenceError(RuntimeError):
    """Raised when an external evidence generation cannot be imported safely."""


def _sha(name: str, value: object) -> str:
    text = str(value).lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise ExternalEvidenceError(f"{name} must be lowercase SHA-256")
    return text


def _git_oid(name: str, value: object) -> str:
    text = str(value).lower()
    if len(text) != 40 or any(ch not in "0123456789abcdef" for ch in text):
        raise ExternalEvidenceError(f"{name} must be lowercase 40-char Git object id")
    return text


def _read_json(path: Path, *, expected_schema: str) -> dict[str, object]:
    if not path.is_file() or path.is_symlink():
        raise ExternalEvidenceError(f"missing regular control file: {path.name}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExternalEvidenceError(f"invalid JSON control file: {path.name}") from exc
    if not isinstance(value, dict) or value.get("schema") != expected_schema:
        raise ExternalEvidenceError(f"unexpected schema for {path.name}")
    return value


def _manifest_rows(rows: object) -> tuple[tuple[str, str, int, int, str], ...]:
    if not isinstance(rows, list):
        raise ExternalEvidenceError("generation manifest files must be a list")
    normalized: list[tuple[str, str, int, int, str]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ExternalEvidenceError("generation manifest file row must be an object")
        path = str(row.get("path", ""))
        object_type = str(row.get("type", ""))
        try:
            mode = int(row.get("mode"))
            size = int(row.get("bytes"))
        except (TypeError, ValueError) as exc:
            raise ExternalEvidenceError("generation manifest mode/bytes must be integers") from exc
        digest = _sha("generation file sha256", row.get("sha256"))
        if not path or Path(path).is_absolute() or ".." in Path(path).parts:
            raise ExternalEvidenceError("generation manifest path must be relative")
        if path in seen:
            raise ExternalEvidenceError(f"duplicate generation manifest path: {path}")
        if object_type not in {"file", "symlink"}:
            raise ExternalEvidenceError(f"unsupported generation object type: {object_type}")
        if mode < 0 or mode > 0o7777 or size < 0:
            raise ExternalEvidenceError("generation manifest mode/bytes out of range")
        seen.add(path)
        normalized.append((path, object_type, mode, size, digest))
    return tuple(sorted(normalized))


@dataclass(frozen=True, slots=True)
class ExternalEvidenceReference:
    subject_type: str
    publication_manifest_sha256: str
    payload_manifest_sha256: str
    materialization_receipt_sha256: str
    materialization_provenance_sha256: str
    source_registry_sha256: str
    repository_commit: str
    repository_tree: str
    family_source_authority_digests: tuple[tuple[str, str], ...]
    family_materialized_authority_digests: tuple[tuple[str, str], ...]
    file_count: int

    def __post_init__(self) -> None:
        if self.subject_type != "DGC_EXTERNAL_MATERIALIZATION_GENERATION_V2":
            raise ExternalEvidenceError("unsupported external evidence subject type")
        for name in (
            "publication_manifest_sha256",
            "payload_manifest_sha256",
            "materialization_receipt_sha256",
            "materialization_provenance_sha256",
            "source_registry_sha256",
        ):
            object.__setattr__(self, name, _sha(name, getattr(self, name)))
        object.__setattr__(self, "repository_commit", _git_oid("repository_commit", self.repository_commit))
        object.__setattr__(self, "repository_tree", _git_oid("repository_tree", self.repository_tree))
        if self.file_count < 1:
            raise ExternalEvidenceError("file_count must be >= 1")
        for field_name in ("family_source_authority_digests", "family_materialized_authority_digests"):
            rows = getattr(self, field_name)
            if {family for family, _ in rows} != _REQUIRED_FAMILIES or len(rows) != len(_REQUIRED_FAMILIES):
                raise ExternalEvidenceError("reference must bind exactly the two frozen workload families")
            for family, digest in rows:
                if not family:
                    raise ExternalEvidenceError("family id required")
                _sha(f"{field_name} digest for {family}", digest)

    @property
    def payload(self) -> dict[str, object]:
        return {
            "schema": REFERENCE_SCHEMA,
            **asdict(self),
        }

    @property
    def digest(self) -> str:
        return sha256_bytes(canonical_json_bytes(self.payload))


def verify_materialization_generation(
    generation_root: Path,
    *,
    expected_repository_commit: str,
    expected_repository_tree: str,
) -> ExternalEvidenceReference:
    supplied_root = Path(generation_root)
    if supplied_root.is_symlink():
        raise ExternalEvidenceError("generation_root symlink is not accepted")
    root = supplied_root.resolve()
    if not root.is_dir():
        raise ExternalEvidenceError("generation_root must be a real directory")

    manifest_path = root / AtomicEvidenceGeneration.MANIFEST_NAME
    receipt_path = root / AtomicEvidenceGeneration.RECEIPT_NAME
    provenance_path = root / AtomicEvidenceGeneration.PROVENANCE_NAME
    manifest = _read_json(manifest_path, expected_schema=GENERATION_MANIFEST_SCHEMA)
    receipt = _read_json(receipt_path, expected_schema=MATERIALIZATION_RECEIPT_SCHEMA)
    provenance = _read_json(provenance_path, expected_schema=MATERIALIZATION_PROVENANCE_SCHEMA)

    observed_publication_rows = file_manifest(
        root,
        excluded_names=frozenset({AtomicEvidenceGeneration.MANIFEST_NAME}),
    )
    declared_publication_rows = _manifest_rows(manifest.get("files"))
    if observed_publication_rows != declared_publication_rows:
        raise ExternalEvidenceError("generation publication file manifest mismatch")
    observed_publication_digest = sha256_bytes(canonical_json_bytes(observed_publication_rows))
    declared_publication_digest = _sha(
        "publication_manifest_sha256", manifest.get("publication_manifest_sha256")
    )
    if observed_publication_digest != declared_publication_digest:
        raise ExternalEvidenceError("generation publication digest mismatch")

    observed_payload_rows = file_manifest(root, excluded_names=AtomicEvidenceGeneration._CONTROL_FILES)
    observed_payload_digest = sha256_bytes(canonical_json_bytes(observed_payload_rows))
    declared_payload_digest = _sha("payload_manifest_sha256", manifest.get("payload_manifest_sha256"))
    if observed_payload_digest != declared_payload_digest:
        raise ExternalEvidenceError("generation payload digest mismatch")
    for name, control in (("receipt", receipt), ("provenance", provenance)):
        if _sha(f"{name}.payload_manifest_sha256", control.get("payload_manifest_sha256")) != observed_payload_digest:
            raise ExternalEvidenceError(f"{name} payload binding mismatch")

    expected_commit = _git_oid("expected_repository_commit", expected_repository_commit)
    expected_tree = _git_oid("expected_repository_tree", expected_repository_tree)
    receipt_commit = _git_oid("receipt.repository_commit", receipt.get("repository_commit"))
    receipt_tree = _git_oid("receipt.repository_tree", receipt.get("repository_tree"))
    repository = provenance.get("repository")
    if not isinstance(repository, Mapping):
        raise ExternalEvidenceError("materialization provenance repository binding missing")
    provenance_commit = _git_oid("provenance.repository.git_commit", repository.get("git_commit"))
    provenance_tree = _git_oid("provenance.repository.git_tree", repository.get("git_tree"))
    if {receipt_commit, provenance_commit} != {expected_commit} or {receipt_tree, provenance_tree} != {expected_tree}:
        raise ExternalEvidenceError("materialization repository identity mismatch")

    if receipt.get("execution_authorized") is not False or receipt.get("product_promotion_authorized") is not False:
        raise ExternalEvidenceError("materialization receipt illegally grants downstream authority")
    if provenance.get("execution_authorized") is not False or provenance.get("product_promotion_authorized") is not False:
        raise ExternalEvidenceError("materialization provenance illegally grants downstream authority")
    if provenance.get("claim") != "VERIFIED_MATERIALIZATION_ONLY":
        raise ExternalEvidenceError("materialization provenance claim boundary mismatch")
    if provenance.get("slsa_conformance_claim") is not False:
        raise ExternalEvidenceError("unverified SLSA conformance claim rejected")

    source_registry_sha = _sha("source_registry_sha256", receipt.get("source_registry_sha256"))
    materials = provenance.get("materials")
    if not isinstance(materials, Mapping):
        raise ExternalEvidenceError("materialization provenance materials missing")
    if _sha("provenance source registry", materials.get("external_source_registry_sha256")) != source_registry_sha:
        raise ExternalEvidenceError("source registry provenance mismatch")
    materializer_sha = _sha("receipt.materializer_sha256", receipt.get("materializer_sha256"))
    if _sha("provenance.materializer_sha256", materials.get("materializer_sha256")) != materializer_sha:
        raise ExternalEvidenceError("materializer provenance mismatch")

    families = receipt.get("families")
    if not isinstance(families, list):
        raise ExternalEvidenceError("materialization families missing")
    source_authority_rows: list[tuple[str, str]] = []
    materialized_authority_rows: list[tuple[str, str]] = []
    for row in families:
        if not isinstance(row, Mapping):
            raise ExternalEvidenceError("invalid materialization family row")
        family_id = str(row.get("family_id", ""))
        if row.get("stage") != "MATERIALIZED_VERIFIED":
            raise ExternalEvidenceError(f"family {family_id} is not MATERIALIZED_VERIFIED")
        source_authority_rows.append((
            family_id,
            _sha(f"source authority digest for {family_id}", row.get("source_authority_digest")),
        ))
        materialized_authority_rows.append((
            family_id,
            _sha(f"materialized authority digest for {family_id}", row.get("authority_digest")),
        ))
    source_authority_rows.sort()
    materialized_authority_rows.sort()
    if (
        {family for family, _ in source_authority_rows} != _REQUIRED_FAMILIES
        or len(source_authority_rows) != len(_REQUIRED_FAMILIES)
        or {family for family, _ in materialized_authority_rows} != _REQUIRED_FAMILIES
        or len(materialized_authority_rows) != len(_REQUIRED_FAMILIES)
    ):
        raise ExternalEvidenceError("materialization receipt must contain exactly both frozen workload families")
    declared_authorities = materials.get("source_authority_digests")
    if not isinstance(declared_authorities, list) or sorted(str(x).lower() for x in declared_authorities) != sorted(
        digest for _, digest in source_authority_rows
    ):
        raise ExternalEvidenceError("source authority provenance mismatch")

    return ExternalEvidenceReference(
        subject_type="DGC_EXTERNAL_MATERIALIZATION_GENERATION_V2",
        publication_manifest_sha256=observed_publication_digest,
        payload_manifest_sha256=observed_payload_digest,
        materialization_receipt_sha256=sha256_file(receipt_path),
        materialization_provenance_sha256=sha256_file(provenance_path),
        source_registry_sha256=source_registry_sha,
        repository_commit=expected_commit,
        repository_tree=expected_tree,
        family_source_authority_digests=tuple(source_authority_rows),
        family_materialized_authority_digests=tuple(materialized_authority_rows),
        file_count=len(observed_publication_rows),
    )
