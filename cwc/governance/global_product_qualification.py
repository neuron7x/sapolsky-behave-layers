from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.materialization_transaction import canonical_json_bytes, file_manifest, sha256_bytes, sha256_file
from cwc.governance.p19_evidence_root import REQUIRED_SUBJECT_ROOTS, verify_family_p19_evidence_root_document
from cwc.governance.product_evidence import ProductEvidenceRecord

SCHEMA = "DGC_GLOBAL_PRODUCT_QUALIFICATION_AUTHORITY_V1"
SOURCE_REGISTRY_SCHEMA = "DGC_EXTERNAL_SOURCE_AUTHORITY_REGISTRY_V1"


class GlobalProductQualificationError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise GlobalProductQualificationError(f"{name} must be lowercase SHA-256")
    return text


def _safe_repo_path(root: Path, value: object, *, directory: bool) -> Path:
    rel = Path(str(value))
    if not str(value) or rel.is_absolute() or ".." in rel.parts:
        raise GlobalProductQualificationError("P19 referenced path must be repository-relative")
    path = root / rel
    if path.is_symlink():
        raise GlobalProductQualificationError("P19 referenced symlink rejected")
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise GlobalProductQualificationError("P19 referenced path escapes repository") from exc
    if directory and not resolved.is_dir():
        raise GlobalProductQualificationError("P19 referenced subject root missing")
    if not directory and not resolved.is_file():
        raise GlobalProductQualificationError("P19 referenced evidence file missing")
    return resolved


def _rehash_family_p19_subjects(doc: Mapping[str, object], *, repository_root: Path) -> None:
    root = Path(repository_root).resolve()
    stage_rows = doc.get("stage_evidence")
    if not isinstance(stage_rows, list) or not stage_rows:
        raise GlobalProductQualificationError("P19 stage evidence manifest missing")
    for row in stage_rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("evidence"), Mapping):
            raise GlobalProductQualificationError("P19 stage evidence row malformed")
        evidence = row["evidence"]
        path = _safe_repo_path(root, evidence.get("path"), directory=False)
        if sha256_file(path) != evidence.get("sha256") or path.stat().st_size != int(evidence.get("bytes", -1)):
            raise GlobalProductQualificationError("P19 stage evidence bytes changed after seal")
    if sha256_bytes(canonical_json_bytes(stage_rows)) != doc.get("stage_evidence_manifest_digest"):
        raise GlobalProductQualificationError("P19 stage evidence manifest digest mismatch")

    anchors = doc.get("methodology_anchors")
    if not isinstance(anchors, list) or not anchors:
        raise GlobalProductQualificationError("P19 methodology anchors missing")
    for row in anchors:
        if not isinstance(row, Mapping):
            raise GlobalProductQualificationError("P19 methodology anchor malformed")
        path = _safe_repo_path(root, row.get("path"), directory=False)
        if sha256_file(path) != row.get("sha256") or path.stat().st_size != int(row.get("bytes", -1)):
            raise GlobalProductQualificationError("P19 methodology anchor bytes changed after seal")
    if sha256_bytes(canonical_json_bytes(anchors)) != doc.get("methodology_anchor_digest"):
        raise GlobalProductQualificationError("P19 methodology anchor digest mismatch")

    roots = doc.get("subject_roots")
    if not isinstance(roots, list) or {str(row.get("label")) for row in roots if isinstance(row, Mapping)} != REQUIRED_SUBJECT_ROOTS:
        raise GlobalProductQualificationError("P19 raw subject-root population mismatch")
    rebuilt_roots: list[dict[str, object]] = []
    for row in sorted(roots, key=lambda item: str(item.get("label"))):
        if not isinstance(row, Mapping):
            raise GlobalProductQualificationError("P19 raw subject-root row malformed")
        path = _safe_repo_path(root, row.get("path"), directory=True)
        manifest = file_manifest(path)
        if any(item[1] != "file" for item in manifest):
            raise GlobalProductQualificationError("P19 raw subject root contains symlink/non-file")
        expected_files = [
            {"path": p, "type": kind, "mode": mode, "bytes": size, "sha256": digest}
            for p, kind, mode, size, digest in manifest
        ]
        manifest_digest = sha256_bytes(canonical_json_bytes(manifest))
        if manifest_digest != row.get("manifest_sha256"):
            raise GlobalProductQualificationError("P19 raw subject manifest changed after seal")
        if expected_files != row.get("files"):
            raise GlobalProductQualificationError("P19 raw subject file population changed after seal")
        if len(manifest) != int(row.get("file_count", -1)):
            raise GlobalProductQualificationError("P19 raw subject file count changed after seal")
        if sum(int(item[3]) for item in manifest) != int(row.get("total_bytes", -1)):
            raise GlobalProductQualificationError("P19 raw subject byte count changed after seal")
        rebuilt_roots.append(dict(row))
    if sha256_bytes(canonical_json_bytes(rebuilt_roots)) != doc.get("subject_root_manifest_digest"):
        raise GlobalProductQualificationError("P19 aggregate subject-root manifest digest mismatch")


def _canonical_family_ids(source_registry_path: Path) -> tuple[str, ...]:
    path = Path(source_registry_path)
    if path.is_symlink() or not path.is_file():
        raise GlobalProductQualificationError("canonical external source registry missing")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GlobalProductQualificationError("invalid external source registry JSON") from exc
    if not isinstance(doc, Mapping) or doc.get("schema") != SOURCE_REGISTRY_SCHEMA:
        raise GlobalProductQualificationError("unexpected external source registry schema")
    families = doc.get("families")
    if not isinstance(families, list) or len(families) != 2:
        raise GlobalProductQualificationError("global product protocol requires exactly two canonical families")
    ids = tuple(sorted(str(row.get("family_id", "")) for row in families if isinstance(row, Mapping)))
    if len(ids) != 2 or any(not value for value in ids) or len(set(ids)) != 2:
        raise GlobalProductQualificationError("canonical source family identity population malformed")
    return ids


@dataclass(frozen=True, slots=True)
class GlobalProductQualificationAuthority:
    canonical_family_ids: tuple[str, ...]
    family_p19_digests: tuple[tuple[str, str], ...]
    repository_commit: str
    repository_tree: str
    statistical_plan_digest: str
    methodology_anchor_digest: str
    family_count: int
    all_family_p19_complete: bool
    product_evidence_record: dict[str, object]
    product_qualified: bool
    production_control_authorized: bool
    authority_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            **asdict(self),
            "global_product_qualification_authorized": self.product_qualified,
            "production_provider_trace_supported": False,
            "shadow_mode_qualified": False,
            "bounded_canary_qualified": False,
        }


def build_global_product_qualification_authority(
    *,
    repository_root: Path,
    source_registry_path: Path,
    family_p19_paths: tuple[Path, Path],
) -> GlobalProductQualificationAuthority:
    root = Path(repository_root).resolve()
    canonical_ids = _canonical_family_ids(Path(source_registry_path))
    docs = [verify_family_p19_evidence_root_document(Path(path)) for path in family_p19_paths]
    observed_ids = tuple(sorted(str(doc["family_id"]) for doc in docs))
    if observed_ids != canonical_ids:
        raise GlobalProductQualificationError("P19 family population does not equal canonical source registry")
    if len({str(doc["p19_digest"]) for doc in docs}) != 2:
        raise GlobalProductQualificationError("global product qualification requires two distinct family P19 roots")
    for doc in docs:
        _rehash_family_p19_subjects(doc, repository_root=root)
        if doc.get("family_evidence_complete") is not True:
            raise GlobalProductQualificationError("one family P19 is incomplete")

    commits = {str(doc["repository_commit"]) for doc in docs}
    trees = {str(doc["repository_tree"]) for doc in docs}
    plans = {str(doc["statistical_plan_digest"]) for doc in docs}
    methods = {str(doc["methodology_anchor_digest"]) for doc in docs}
    if len(commits) != 1 or len(trees) != 1:
        raise GlobalProductQualificationError("two family P19 roots were not produced from the same repository identity")
    if len(plans) != 1 or len(methods) != 1:
        raise GlobalProductQualificationError("two family P19 roots use different statistical/methodological identities")

    record = ProductEvidenceRecord(
        claim_frozen=True,
        metrics_frozen=True,
        baselines_frozen=True,
        harness_frozen=True,
        statistical_plan_frozen=True,
        synthetic_mechanism_supported=False,
        external_real_workload_supported=True,
        quality_noninferiority_supported=True,
        catastrophic_regret_noninferiority_supported=True,
        coverage_equivalence_supported=True,
        physical_cost_accounting_verified=True,
        net_cost_superiority_supported=True,
        generalization_supported=True,
        fault_tolerance_supported=True,
        independent_replication_supported=True,
        evidence_bundle_complete=True,
        production_provider_trace_supported=False,
        shadow_mode_qualified=False,
        bounded_canary_qualified=False,
    )
    qualified = record.product_qualified
    if not qualified:
        raise GlobalProductQualificationError("two-family evidence record does not derive PRODUCT_QUALIFIED")
    family_digests = tuple(sorted(
        (str(doc["family_id"]), _sha("p19_digest", doc["p19_digest"])) for doc in docs
    ))
    payload = {
        "canonical_family_ids": list(canonical_ids),
        "family_p19_digests": [list(row) for row in family_digests],
        "repository_commit": next(iter(commits)),
        "repository_tree": next(iter(trees)),
        "statistical_plan_digest": next(iter(plans)),
        "methodology_anchor_digest": next(iter(methods)),
        "family_count": 2,
        "all_family_p19_complete": True,
        "product_evidence_record": asdict(record),
        "product_qualified": True,
        "production_control_authorized": False,
    }
    return GlobalProductQualificationAuthority(
        canonical_family_ids=canonical_ids,
        family_p19_digests=family_digests,
        repository_commit=payload["repository_commit"],
        repository_tree=payload["repository_tree"],
        statistical_plan_digest=payload["statistical_plan_digest"],
        methodology_anchor_digest=payload["methodology_anchor_digest"],
        family_count=2,
        all_family_p19_complete=True,
        product_evidence_record=payload["product_evidence_record"],
        product_qualified=True,
        production_control_authorized=False,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_global_product_qualification_authority_document(path: Path) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise GlobalProductQualificationError("global product authority must be a regular file")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GlobalProductQualificationError("invalid global product authority JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise GlobalProductQualificationError("unexpected global product authority schema")
    if doc.get("product_qualified") is not True or doc.get("global_product_qualification_authorized") is not True:
        raise GlobalProductQualificationError("global product qualification is not established")
    if doc.get("production_control_authorized") is not False:
        raise GlobalProductQualificationError("product qualification cannot authorize production control")
    if any(doc.get(field) is not False for field in (
        "production_provider_trace_supported", "shadow_mode_qualified", "bounded_canary_qualified"
    )):
        raise GlobalProductQualificationError("production claims leaked into product qualification")
    keys = (
        "canonical_family_ids", "family_p19_digests", "repository_commit", "repository_tree",
        "statistical_plan_digest", "methodology_anchor_digest", "family_count",
        "all_family_p19_complete", "product_evidence_record", "product_qualified",
        "production_control_authorized",
    )
    try:
        payload = {key: doc[key] for key in keys}
    except KeyError as exc:
        raise GlobalProductQualificationError("global product authority payload incomplete") from exc
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("authority_digest", doc.get("authority_digest")):
        raise GlobalProductQualificationError("global product authority digest mismatch")
    if int(doc.get("family_count", 0)) != 2:
        raise GlobalProductQualificationError("global product authority must contain exactly two families")
    family_rows = doc.get("family_p19_digests")
    if not isinstance(family_rows, list) or len(family_rows) != 2:
        raise GlobalProductQualificationError("global product authority family P19 population malformed")
    return doc
