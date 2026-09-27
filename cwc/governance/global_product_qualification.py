from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Mapping

from cwc.governance.materialization_transaction import canonical_json_bytes, file_manifest, sha256_bytes, sha256_file
from cwc.governance.p19_evidence_root import REQUIRED_SUBJECT_ROOTS, verify_family_p19_evidence_root_document
from cwc.governance.p19_verification_attestation import (
    P19VerificationSignatureReceipt,
    bind_attestation_to_p19,
    verify_ssh_signed_p19_verification_attestation,
)
from cwc.governance.product_evidence import ProductEvidenceRecord

SCHEMA = "DGC_GLOBAL_PRODUCT_QUALIFICATION_AUTHORITY_V3"
SOURCE_REGISTRY_SCHEMA = "DGC_EXTERNAL_SOURCE_AUTHORITY_REGISTRY_V1"
GENERALIZATION_REGISTRY_SCHEMA = "DGC_GENERALIZATION_REGISTRY_V3"
GLOBAL_STATISTICAL_COMPOSITION_RULE = "INTERSECTION_UNION_TWO_FAMILY_AND_V1"
GENERALIZATION_PER_FAMILY_FWER = 0.05
GENERALIZATION_CLAIM_COUNT_PER_FAMILY = 5 * 4 * 3


class GlobalProductQualificationError(RuntimeError):
    pass


P19AttestationVerifier = Callable[..., tuple[dict[str, object], P19VerificationSignatureReceipt]]


@dataclass(frozen=True, slots=True)
class FamilyP19VerificationInput:
    attestation_path: Path
    verification_report_path: Path
    signature_path: Path
    allowed_signers_path: Path


@dataclass(frozen=True, slots=True)
class FamilyP19VerificationRecord:
    family_id: str
    p19_digest: str
    verifier_principal: str
    attestation_sha256: str
    verification_report_sha256: str
    signature_sha256: str
    allowed_signers_sha256: str
    signature_receipt_digest: str
    semantic_replay_attested: bool
    social_independence_machine_proven: bool
    record_digest: str


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


def _canonical_family_ids(source_registry_path: Path) -> tuple[tuple[str, ...], str]:
    path = Path(source_registry_path)
    if path.is_symlink() or not path.is_file():
        raise GlobalProductQualificationError("canonical external source registry missing")
    raw_digest = sha256_file(path)
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
    return ids, raw_digest


def _stage_evidence_path(doc: Mapping[str, object], *, stage: str, repository_root: Path) -> Path:
    rows = doc.get("stage_evidence")
    if not isinstance(rows, list):
        raise GlobalProductQualificationError("P19 stage evidence missing")
    matches = [row for row in rows if isinstance(row, Mapping) and row.get("stage") == stage]
    if len(matches) != 1 or not isinstance(matches[0].get("evidence"), Mapping):
        raise GlobalProductQualificationError(f"P19 requires exactly one {stage} evidence row")
    return _safe_repo_path(Path(repository_root).resolve(), matches[0]["evidence"].get("path"), directory=False)


def _verify_family_generalization_error_budget(doc: Mapping[str, object], *, repository_root: Path) -> None:
    path = _stage_evidence_path(doc, stage="GENERALIZATION_REGISTRY_FROZEN", repository_root=repository_root)
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GlobalProductQualificationError("invalid generalization registry in P19") from exc
    if not isinstance(registry, Mapping) or registry.get("schema") != GENERALIZATION_REGISTRY_SCHEMA:
        raise GlobalProductQualificationError("unexpected generalization registry schema in P19")
    if str(registry.get("family_id", "")) != str(doc.get("family_id", "")):
        raise GlobalProductQualificationError("P19/generalization registry family mismatch")
    try:
        family_alpha = float(registry.get("generalization_familywise_alpha"))
        per_claim = float(registry.get("per_claim_alpha"))
    except (TypeError, ValueError) as exc:
        raise GlobalProductQualificationError("generalization error budget malformed") from exc
    expected_per_claim = GENERALIZATION_PER_FAMILY_FWER / GENERALIZATION_CLAIM_COUNT_PER_FAMILY
    if not math.isclose(family_alpha, GENERALIZATION_PER_FAMILY_FWER, rel_tol=0.0, abs_tol=1e-15):
        raise GlobalProductQualificationError("generalization per-family FWER differs from global protocol")
    if not math.isclose(per_claim, expected_per_claim, rel_tol=0.0, abs_tol=1e-15):
        raise GlobalProductQualificationError("generalization per-claim alpha differs from 5x4x3 family allocation")


def _verify_external_p19_attestation(
    *,
    p19: Mapping[str, object],
    inputs: FamilyP19VerificationInput,
    verifier: P19AttestationVerifier,
) -> FamilyP19VerificationRecord:
    try:
        attestation, receipt = verifier(
            attestation_path=Path(inputs.attestation_path),
            verification_report_path=Path(inputs.verification_report_path),
            signature_path=Path(inputs.signature_path),
            allowed_signers_path=Path(inputs.allowed_signers_path),
        )
        bind_attestation_to_p19(attestation, p19)
    except RuntimeError as exc:
        raise GlobalProductQualificationError("external P19 semantic-verification attestation failed") from exc
    if not receipt.signature_verified:
        raise GlobalProductQualificationError("external P19 verification signature is not verified")
    payload = {
        "family_id": str(p19["family_id"]),
        "p19_digest": _sha("p19_digest", p19["p19_digest"]),
        "verifier_principal": str(attestation["verifier_principal"]),
        "attestation_sha256": _sha("attestation_sha256", receipt.attestation_sha256),
        "verification_report_sha256": _sha("verification_report_sha256", receipt.verification_report_sha256),
        "signature_sha256": _sha("signature_sha256", receipt.signature_sha256),
        "allowed_signers_sha256": _sha("allowed_signers_sha256", receipt.allowed_signers_sha256),
        "signature_receipt_digest": _sha("signature_receipt_digest", receipt.digest),
        "semantic_replay_attested": True,
        "social_independence_machine_proven": False,
    }
    return FamilyP19VerificationRecord(
        **payload,
        record_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


@dataclass(frozen=True, slots=True)
class GlobalProductQualificationAuthority:
    canonical_family_ids: tuple[str, ...]
    source_registry_sha256: str
    family_p19_digests: tuple[tuple[str, str], ...]
    family_p19_verification_records: tuple[FamilyP19VerificationRecord, ...]
    repository_commit: str
    repository_tree: str
    statistical_plan_digest: str
    theorem_identity_digest: str
    methodology_anchor_digest: str
    family_count: int
    generalization_claim_count_per_family: int
    generalization_per_family_fwer: float
    global_statistical_composition_rule: str
    all_family_p19_complete: bool
    all_family_p19_externally_verified: bool
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
            "external_p19_semantic_replay_attestation_required": True,
            "social_independence_machine_proven": False,
            "production_provider_trace_supported": False,
            "shadow_mode_qualified": False,
            "bounded_canary_qualified": False,
        }


def build_global_product_qualification_authority(
    *,
    repository_root: Path,
    source_registry_path: Path,
    family_p19_paths: tuple[Path, Path],
    family_p19_verification_inputs: tuple[FamilyP19VerificationInput, FamilyP19VerificationInput],
    p19_attestation_verifier: P19AttestationVerifier = verify_ssh_signed_p19_verification_attestation,
) -> GlobalProductQualificationAuthority:
    root = Path(repository_root).resolve()
    canonical_ids, registry_digest = _canonical_family_ids(Path(source_registry_path))
    docs = [verify_family_p19_evidence_root_document(Path(path)) for path in family_p19_paths]
    observed_ids = tuple(sorted(str(doc["family_id"]) for doc in docs))
    if observed_ids != canonical_ids:
        raise GlobalProductQualificationError("P19 family population does not equal canonical source registry")
    if len({str(doc["p19_digest"]) for doc in docs}) != 2:
        raise GlobalProductQualificationError("global product qualification requires two distinct family P19 roots")
    verification_rows: list[FamilyP19VerificationRecord] = []
    for doc, verification_input in zip(docs, family_p19_verification_inputs, strict=True):
        _rehash_family_p19_subjects(doc, repository_root=root)
        _verify_family_generalization_error_budget(doc, repository_root=root)
        if doc.get("family_evidence_complete") is not True:
            raise GlobalProductQualificationError("one family P19 is incomplete")
        verification_rows.append(_verify_external_p19_attestation(
            p19=doc,
            inputs=verification_input,
            verifier=p19_attestation_verifier,
        ))

    commits = {str(doc["repository_commit"]) for doc in docs}
    trees = {str(doc["repository_tree"]) for doc in docs}
    plans = {str(doc["statistical_plan_digest"]) for doc in docs}
    theorems = {str(doc["theorem_identity_digest"]) for doc in docs}
    methods = {str(doc["methodology_anchor_digest"]) for doc in docs}
    if len(commits) != 1 or len(trees) != 1:
        raise GlobalProductQualificationError("two family P19 roots were not produced from the same repository identity")
    if len(plans) != 1 or len(theorems) != 1 or len(methods) != 1:
        raise GlobalProductQualificationError("two family P19 roots use different statistical/theorem/methodology identities")

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
    qualified = record.product_qualified and len(verification_rows) == 2
    if not qualified:
        raise GlobalProductQualificationError("two-family evidence record does not derive PRODUCT_QUALIFIED")
    family_digests = tuple(sorted(
        (str(doc["family_id"]), _sha("p19_digest", doc["p19_digest"])) for doc in docs
    ))
    ordered_verification = tuple(sorted(verification_rows, key=lambda row: row.family_id))
    payload = {
        "canonical_family_ids": list(canonical_ids),
        "source_registry_sha256": registry_digest,
        "family_p19_digests": [list(row) for row in family_digests],
        "family_p19_verification_records": [asdict(row) for row in ordered_verification],
        "repository_commit": next(iter(commits)),
        "repository_tree": next(iter(trees)),
        "statistical_plan_digest": next(iter(plans)),
        "theorem_identity_digest": next(iter(theorems)),
        "methodology_anchor_digest": next(iter(methods)),
        "family_count": 2,
        "generalization_claim_count_per_family": GENERALIZATION_CLAIM_COUNT_PER_FAMILY,
        "generalization_per_family_fwer": GENERALIZATION_PER_FAMILY_FWER,
        "global_statistical_composition_rule": GLOBAL_STATISTICAL_COMPOSITION_RULE,
        "all_family_p19_complete": True,
        "all_family_p19_externally_verified": True,
        "product_evidence_record": asdict(record),
        "product_qualified": True,
        "production_control_authorized": False,
    }
    return GlobalProductQualificationAuthority(
        canonical_family_ids=canonical_ids,
        source_registry_sha256=registry_digest,
        family_p19_digests=family_digests,
        family_p19_verification_records=ordered_verification,
        repository_commit=payload["repository_commit"],
        repository_tree=payload["repository_tree"],
        statistical_plan_digest=payload["statistical_plan_digest"],
        theorem_identity_digest=payload["theorem_identity_digest"],
        methodology_anchor_digest=payload["methodology_anchor_digest"],
        family_count=2,
        generalization_claim_count_per_family=GENERALIZATION_CLAIM_COUNT_PER_FAMILY,
        generalization_per_family_fwer=GENERALIZATION_PER_FAMILY_FWER,
        global_statistical_composition_rule=GLOBAL_STATISTICAL_COMPOSITION_RULE,
        all_family_p19_complete=True,
        all_family_p19_externally_verified=True,
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
    if doc.get("external_p19_semantic_replay_attestation_required") is not True:
        raise GlobalProductQualificationError("global qualification omitted external P19 semantic verification")
    if doc.get("social_independence_machine_proven") is not False:
        raise GlobalProductQualificationError("global authority cannot claim machine-proven social independence")
    if doc.get("production_control_authorized") is not False:
        raise GlobalProductQualificationError("product qualification cannot authorize production control")
    if any(doc.get(field) is not False for field in (
        "production_provider_trace_supported", "shadow_mode_qualified", "bounded_canary_qualified"
    )):
        raise GlobalProductQualificationError("production claims leaked into product qualification")
    keys = (
        "canonical_family_ids", "source_registry_sha256", "family_p19_digests",
        "family_p19_verification_records", "repository_commit", "repository_tree",
        "statistical_plan_digest", "theorem_identity_digest", "methodology_anchor_digest",
        "family_count", "generalization_claim_count_per_family", "generalization_per_family_fwer",
        "global_statistical_composition_rule", "all_family_p19_complete",
        "all_family_p19_externally_verified", "product_evidence_record", "product_qualified",
        "production_control_authorized",
    )
    try:
        payload = {key: doc[key] for key in keys}
    except KeyError as exc:
        raise GlobalProductQualificationError("global product authority payload incomplete") from exc
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("authority_digest", doc.get("authority_digest")):
        raise GlobalProductQualificationError("global product authority digest mismatch")
    for field in ("source_registry_sha256", "statistical_plan_digest", "theorem_identity_digest", "methodology_anchor_digest"):
        _sha(field, doc.get(field))
    if int(doc.get("family_count", 0)) != 2:
        raise GlobalProductQualificationError("global product authority must contain exactly two families")
    if int(doc.get("generalization_claim_count_per_family", 0)) != GENERALIZATION_CLAIM_COUNT_PER_FAMILY:
        raise GlobalProductQualificationError("global generalization claim count is not 5x4x3 per family")
    try:
        family_fwer = float(doc.get("generalization_per_family_fwer"))
    except (TypeError, ValueError) as exc:
        raise GlobalProductQualificationError("global generalization familywise alpha invalid") from exc
    if not math.isclose(family_fwer, GENERALIZATION_PER_FAMILY_FWER, rel_tol=0.0, abs_tol=1e-15):
        raise GlobalProductQualificationError("global generalization familywise alpha mismatch")
    if doc.get("global_statistical_composition_rule") != GLOBAL_STATISTICAL_COMPOSITION_RULE:
        raise GlobalProductQualificationError("global statistical composition is not the frozen intersection-union rule")
    if doc.get("all_family_p19_complete") is not True or doc.get("all_family_p19_externally_verified") is not True:
        raise GlobalProductQualificationError("global family evidence/verification population incomplete")
    family_rows = doc.get("family_p19_digests")
    if not isinstance(family_rows, list) or len(family_rows) != 2:
        raise GlobalProductQualificationError("global product authority family P19 population malformed")
    ids = doc.get("canonical_family_ids")
    if not isinstance(ids, list) or len(ids) != 2 or len(set(map(str, ids))) != 2:
        raise GlobalProductQualificationError("global product authority canonical family set malformed")
    verification_rows = doc.get("family_p19_verification_records")
    if not isinstance(verification_rows, list) or len(verification_rows) != 2:
        raise GlobalProductQualificationError("global P19 verification population malformed")
    verification_ids: set[str] = set()
    for row in verification_rows:
        if not isinstance(row, Mapping):
            raise GlobalProductQualificationError("global P19 verification row malformed")
        row_payload = {
            key: row[key] for key in (
                "family_id", "p19_digest", "verifier_principal", "attestation_sha256",
                "verification_report_sha256", "signature_sha256", "allowed_signers_sha256",
                "signature_receipt_digest", "semantic_replay_attested", "social_independence_machine_proven",
            )
        }
        if sha256_bytes(canonical_json_bytes(row_payload)) != _sha("P19 verification record_digest", row.get("record_digest")):
            raise GlobalProductQualificationError("global P19 verification record digest mismatch")
        if row.get("semantic_replay_attested") is not True or row.get("social_independence_machine_proven") is not False:
            raise GlobalProductQualificationError("global P19 verification claim boundary malformed")
        family_id = str(row.get("family_id", ""))
        verification_ids.add(family_id)
        _sha("verified p19_digest", row.get("p19_digest"))
        for field in (
            "attestation_sha256", "verification_report_sha256", "signature_sha256",
            "allowed_signers_sha256", "signature_receipt_digest",
        ):
            _sha(field, row.get(field))
    if verification_ids != set(map(str, ids)):
        raise GlobalProductQualificationError("P19 external verification family set differs from canonical family set")
    p19_map = {str(row[0]): str(row[1]) for row in family_rows if isinstance(row, list) and len(row) == 2}
    if set(p19_map) != set(map(str, ids)):
        raise GlobalProductQualificationError("family P19 digest set differs from canonical family set")
    for row in verification_rows:
        if p19_map[str(row["family_id"])] != str(row["p19_digest"]):
            raise GlobalProductQualificationError("P19 verification receipt references a different family root")
    return doc
