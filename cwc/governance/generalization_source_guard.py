from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.external_evidence_reference import REFERENCE_SCHEMA
from cwc.governance.generalization_registry import GeneralizationAxis, verify_generalization_registry_document
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file


class GeneralizationSourceError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise GeneralizationSourceError(f"{name} must be lowercase SHA-256")
    return text


def _safe_repo_file(root: Path, value: object) -> Path:
    rel = Path(str(value))
    if not str(value) or rel.is_absolute() or ".." in rel.parts:
        raise GeneralizationSourceError("source authority path must be repository-relative")
    candidate = root / rel
    if candidate.is_symlink():
        raise GeneralizationSourceError("source authority symlink rejected")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise GeneralizationSourceError("source authority path escapes repository") from exc
    if not resolved.is_file():
        raise GeneralizationSourceError("source authority file missing")
    return resolved


def _json(path: Path, *, schema: str) -> dict[str, object]:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GeneralizationSourceError("invalid source authority JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != schema:
        raise GeneralizationSourceError("unexpected source authority schema")
    return doc


def _axis_row(registry: Mapping[str, object], axis: GeneralizationAxis) -> Mapping[str, object]:
    rows = registry.get("axes")
    if not isinstance(rows, list):
        raise GeneralizationSourceError("registry axes missing")
    matches = [row for row in rows if isinstance(row, Mapping) and row.get("axis") == axis.value]
    if len(matches) != 1:
        raise GeneralizationSourceError("axis missing or duplicated")
    return matches[0]


@dataclass(frozen=True, slots=True)
class GeneralizationSourceBinding:
    axis: str
    source_family_id: str
    source_authority_digest: str
    materialization_reference_path: str
    materialization_reference_digest: str
    materialization_reference_sha256: str


def verify_generalization_source_binding(
    *,
    repository_root: Path,
    registry_path: Path,
    axis: GeneralizationAxis,
) -> GeneralizationSourceBinding:
    root = Path(repository_root).resolve()
    registry = verify_generalization_registry_document(Path(registry_path))
    row = _axis_row(registry, axis)
    axis_path = _safe_repo_file(root, row.get("manifest_path"))
    if sha256_file(axis_path) != _sha("axis manifest_sha256", row.get("manifest_sha256")):
        raise GeneralizationSourceError("axis manifest changed after registry freeze")
    axis_doc = _json(axis_path, schema="DGC_GENERALIZATION_AXIS_MANIFEST_V1")
    reference_rel = str(axis_doc.get("source_materialization_reference_path", ""))
    reference_path = _safe_repo_file(root, reference_rel)
    reference = _json(reference_path, schema=REFERENCE_SCHEMA)
    declared_reference_digest = _sha("reference_digest", reference.get("reference_digest"))
    reference_payload = dict(reference)
    reference_payload.pop("reference_digest", None)
    if sha256_bytes(canonical_json_bytes(reference_payload)) != declared_reference_digest:
        raise GeneralizationSourceError("materialization reference digest mismatch")

    source_family_id = str(row.get("source_family_id", ""))
    bindings = reference.get("family_bindings")
    if not isinstance(bindings, list):
        raise GeneralizationSourceError("materialization reference family bindings missing")
    matches = [binding for binding in bindings if isinstance(binding, Mapping) and binding.get("family_id") == source_family_id]
    if len(matches) != 1:
        raise GeneralizationSourceError("generalization source family is not materialized in the frozen reference")
    observed_authority = _sha("materialized_authority_digest", matches[0].get("materialized_authority_digest"))
    expected_authority = _sha("source_authority_digest", row.get("source_authority_digest"))
    if observed_authority != expected_authority:
        raise GeneralizationSourceError("axis source authority does not equal MATERIALIZED_VERIFIED family binding")

    return GeneralizationSourceBinding(
        axis=axis.value,
        source_family_id=source_family_id,
        source_authority_digest=observed_authority,
        materialization_reference_path=reference_rel,
        materialization_reference_digest=declared_reference_digest,
        materialization_reference_sha256=sha256_file(reference_path),
    )
