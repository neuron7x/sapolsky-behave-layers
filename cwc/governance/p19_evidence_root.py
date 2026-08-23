from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.ccf_oracle_audit_authority import verify_ccf_oracle_audit_authority_document
from cwc.governance.evidence_closure import EvidenceClosureLedger, RECEIPT_SCHEMA, STAGES, sha256_file
from cwc.governance.executed_p9_anytime_authority import verify_anytime_p9_authority_document
from cwc.governance.execution_manifest_freeze import verify_execution_manifest_freeze_document
from cwc.governance.fault_tolerance_authority import verify_fault_tolerance_authority_document
from cwc.governance.generalization_anytime_authority import verify_generalization_anytime_authority_document
from cwc.governance.independent_replication_authority_v3 import verify_independent_replication_authority_v3_document
from cwc.governance.materialization_transaction import canonical_json_bytes, file_manifest, sha256_bytes
from cwc.governance.p9_scientific_authority_v3 import verify_p9_scientific_authority_v3_document
from cwc.governance.product_statistical_plan import (
    CONFSEQ_REFERENCE_COMMIT,
    PLAN_METHOD,
    PRIMARY_ASSUMPTION_BOUNDARY,
    PRIMARY_BOUNDARY_METHOD,
    PRIMARY_CLAIM_TARGET,
    PRIMARY_INFERENCE_METHOD,
    PRIMARY_PREDICTOR_RULE,
    PRIMARY_SEQUENCE_ORDER,
)

SCHEMA = "DGC_FAMILY_P19_EVIDENCE_ROOT_V2"

REQUIRED_SUBJECT_ROOTS = frozenset({
    "PRIMARY_EXECUTION",
    "PRIMARY_PHYSICAL_COST",
    "PRIMARY_CCF",
    "G1_EXECUTION",
    "G2_EXECUTION",
    "G3_EXECUTION",
    "G4_EXECUTION",
    "G5_EXECUTION",
    "FAULT_TOLERANCE",
    "REPLICA_EXECUTION",
    "REPLICA_PHYSICAL_COST",
    "REPLICA_CCF",
    "REPLICATION_ATTESTATION",
})

METHODOLOGY_ANCHORS = (
    "artifacts/dgc-product-v1/PREREGISTRATION.md",
    "artifacts/dgc-product-v1/FAULT_INJECTION_SPEC_V1.json",
    "docs/DGC_PRODUCT_STATISTICAL_PLAN_v5.md",
    "docs/DGC_STATISTICAL_AUTHORITY_v5.md",
    "docs/DGC_THEOREM_AUDIT_v5.md",
    "cwc/governance/product_statistical_plan.py",
    "cwc/governance/average_conditional_mean_cs.py",
    "cwc/governance/executed_p9_anytime_authority.py",
    "cwc/governance/p9_scientific_authority_v3.py",
    "cwc/governance/generalization_anytime_authority.py",
    "cwc/governance/fault_tolerance_authority.py",
    "cwc/governance/independent_replication_authority_v3.py",
)


class P19EvidenceError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise P19EvidenceError(f"{name} must be lowercase SHA-256")
    return text


def _repo_file(root: Path, value: str) -> tuple[Path, str]:
    rel = Path(value)
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise P19EvidenceError("P19 file path must be repository-relative")
    candidate = root / rel
    if candidate.is_symlink() or not candidate.is_file():
        raise P19EvidenceError(f"P19 required file missing or symlinked: {value}")
    return candidate.resolve(), rel.as_posix()


def _repo_dir(root: Path, value: Path) -> tuple[Path, str]:
    candidate = value if value.is_absolute() else root / value
    if candidate.is_symlink():
        raise P19EvidenceError("P19 subject root symlink rejected")
    resolved = candidate.resolve()
    try:
        rel = resolved.relative_to(root)
    except ValueError as exc:
        raise P19EvidenceError("P19 subject root must remain inside repository") from exc
    if not resolved.is_dir():
        raise P19EvidenceError("P19 subject root must be a directory")
    return resolved, rel.as_posix()


def _receipt_for(state: Mapping[str, object], stage: str) -> Mapping[str, object]:
    receipts = state.get("receipts")
    if not isinstance(receipts, list):
        raise P19EvidenceError("ledger receipts missing")
    matches = [row for row in receipts if isinstance(row, Mapping) and row.get("stage") == stage]
    if len(matches) != 1:
        raise P19EvidenceError(f"P19 requires exactly one receipt for {stage}")
    return matches[0]


def _verify_pre_p19_ledger_snapshot(
    state: Mapping[str, object],
    *,
    generation_id: str,
    repository_commit: str,
    repository_tree: str,
) -> None:
    expected_stages = list(STAGES[: STAGES.index("P19_SEALED")])
    if state.get("generation_id") != generation_id:
        raise P19EvidenceError("P19 ledger snapshot generation mismatch")
    if state.get("repo_commit") != repository_commit or state.get("repo_tree") != repository_tree:
        raise P19EvidenceError("P19 ledger snapshot repository identity mismatch")
    if state.get("completed_stages") != expected_stages:
        raise P19EvidenceError("P19 ledger snapshot stage population mismatch")
    if state.get("product_qualified") is not False:
        raise P19EvidenceError("pre-P19 ledger snapshot cannot already be product-qualified")
    receipts = state.get("receipts")
    if not isinstance(receipts, list) or len(receipts) != len(expected_stages):
        raise P19EvidenceError("P19 ledger snapshot receipt population mismatch")
    prior = None
    for index, receipt in enumerate(receipts):
        if not isinstance(receipt, Mapping):
            raise P19EvidenceError("P19 ledger snapshot receipt malformed")
        row = dict(receipt)
        observed = row.pop("receipt_digest", None)
        if row.get("schema") != RECEIPT_SCHEMA:
            raise P19EvidenceError("P19 ledger snapshot receipt schema mismatch")
        if row.get("stage") != expected_stages[index]:
            raise P19EvidenceError("P19 ledger snapshot receipt stage order mismatch")
        if row.get("generation_id") != generation_id:
            raise P19EvidenceError("P19 ledger snapshot receipt generation mismatch")
        if row.get("repo_commit") != repository_commit or row.get("repo_tree") != repository_tree:
            raise P19EvidenceError("P19 ledger snapshot receipt repository mismatch")
        if row.get("prior_receipt_digest") != prior:
            raise P19EvidenceError("P19 ledger snapshot receipt chain mismatch")
        expected = sha256_bytes(canonical_json_bytes(row))
        if observed != expected:
            raise P19EvidenceError("P19 ledger snapshot receipt digest mismatch")
        prior = observed


def _single_stage_evidence(root: Path, state: Mapping[str, object], stage: str) -> tuple[Path, dict[str, object]]:
    receipt = _receipt_for(state, stage)
    evidence = receipt.get("evidence")
    if not isinstance(evidence, list) or len(evidence) != 1 or not isinstance(evidence[0], Mapping):
        raise P19EvidenceError(f"{stage} must bind exactly one evidence artifact")
    row = dict(evidence[0])
    path, rel = _repo_file(root, str(row.get("path", "")))
    observed = sha256_file(path)
    if observed != row.get("sha256"):
        raise P19EvidenceError(f"{stage} evidence changed after closure")
    row["path"] = rel
    row["sha256"] = observed
    row["bytes"] = path.stat().st_size
    return path, row


def _subject_root_manifest(root: Path, label: str, value: Path) -> dict[str, object]:
    path, rel = _repo_dir(root, value)
    rows = file_manifest(path)
    if not rows:
        raise P19EvidenceError(f"P19 subject root is empty: {label}")
    if any(row[1] != "file" for row in rows):
        raise P19EvidenceError(f"P19 subject root contains symlink/non-file object: {label}")
    manifest_digest = sha256_bytes(canonical_json_bytes(rows))
    return {
        "label": label,
        "path": rel,
        "file_count": len(rows),
        "total_bytes": sum(int(row[3]) for row in rows),
        "manifest_sha256": manifest_digest,
        "files": [
            {"path": p, "type": kind, "mode": mode, "bytes": size, "sha256": digest}
            for p, kind, mode, size, digest in rows
        ],
    }


def _theorem_identity_digest() -> str:
    return sha256_bytes(canonical_json_bytes({
        "method": PRIMARY_INFERENCE_METHOD,
        "boundary_method": PRIMARY_BOUNDARY_METHOD,
        "claim_target": PRIMARY_CLAIM_TARGET,
        "assumption_boundary": PRIMARY_ASSUMPTION_BOUNDARY,
        "sequence_order_rule": PRIMARY_SEQUENCE_ORDER,
        "predictor_rule": PRIMARY_PREDICTOR_RULE,
        "confseq_reference_commit": CONFSEQ_REFERENCE_COMMIT,
    }))


@dataclass(frozen=True, slots=True)
class FamilyP19EvidenceRoot:
    family_id: str
    generation_id: str
    repository_commit: str
    repository_tree: str
    ledger_schema: str
    ledger_snapshot_digest: str
    ledger_snapshot: dict[str, object]
    receipt_chain_tip_digest: str
    stage_evidence_manifest_digest: str
    stage_evidence: tuple[dict[str, object], ...]
    primary_p9_scientific_authority_digest: str
    primary_anytime_p9_authority_digest: str
    primary_ccf_oracle_audit_authority_digest: str
    generalization_authority_digest: str
    fault_tolerance_authority_digest: str
    independent_replication_authority_digest: str
    statistical_plan_digest: str
    theorem_identity_digest: str
    methodology_anchor_digest: str
    methodology_anchors: tuple[dict[str, object], ...]
    subject_root_manifest_digest: str
    subject_roots: tuple[dict[str, object], ...]
    family_p9_supported: bool
    family_generalization_supported: bool
    family_fault_tolerance_supported: bool
    family_replication_supported: bool
    family_evidence_complete: bool
    p19_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            **asdict(self),
            "p19_sealed": self.family_evidence_complete,
            "family_qualification_ready": self.family_evidence_complete,
            "global_product_qualification_authorized": False,
            "peer_family_p19_required": True,
        }


def build_family_p19_evidence_root(
    *,
    ledger: EvidenceClosureLedger,
    primary_anytime_p9_authority_path: Path,
    primary_ccf_oracle_audit_authority_path: Path,
    subject_roots: Mapping[str, Path],
) -> FamilyP19EvidenceRoot:
    if ledger.next_stage() != "P19_SEALED":
        raise P19EvidenceError("P19 can be built only after all pre-P19 stages")
    state = ledger.load()
    expected_completed = list(STAGES[: STAGES.index("P19_SEALED")])
    if state.get("completed_stages") != expected_completed:
        raise P19EvidenceError("P19 ledger does not contain exact pre-P19 stage population")
    if set(subject_roots) != REQUIRED_SUBJECT_ROOTS:
        raise P19EvidenceError("P19 requires exact raw-subject root population")
    _verify_pre_p19_ledger_snapshot(
        state,
        generation_id=ledger.generation_id,
        repository_commit=ledger.repo_commit,
        repository_tree=ledger.repo_tree,
    )

    root = ledger.repository_root
    stage_rows: list[dict[str, object]] = []
    for stage in expected_completed:
        _, evidence = _single_stage_evidence(root, state, stage)
        receipt = _receipt_for(state, stage)
        stage_rows.append({
            "stage": stage,
            "receipt_digest": _sha(f"{stage}.receipt_digest", receipt.get("receipt_digest")),
            "evidence": evidence,
        })
    stage_manifest_digest = sha256_bytes(canonical_json_bytes(stage_rows))

    execution_path, _ = _single_stage_evidence(root, state, "EXECUTION_MANIFESTS_FROZEN")
    p9_path, _ = _single_stage_evidence(root, state, "P9_SUPPORTED")
    generalization_path, _ = _single_stage_evidence(root, state, "GENERALIZATION_SUPPORTED")
    fault_path, _ = _single_stage_evidence(root, state, "FAULT_TOLERANCE_SUPPORTED")
    replication_path, _ = _single_stage_evidence(root, state, "INDEPENDENT_REPLICATION_SUPPORTED")

    execution = verify_execution_manifest_freeze_document(execution_path)
    p9 = verify_p9_scientific_authority_v3_document(p9_path)
    generalization = verify_generalization_anytime_authority_document(generalization_path)
    fault = verify_fault_tolerance_authority_document(fault_path)
    replication = verify_independent_replication_authority_v3_document(replication_path)
    anytime = verify_anytime_p9_authority_document(Path(primary_anytime_p9_authority_path))
    ccf = verify_ccf_oracle_audit_authority_document(Path(primary_ccf_oracle_audit_authority_path))

    if p9.get("scientific_p9_supported") is not True:
        raise P19EvidenceError("P19 primary P9 is unsupported")
    if generalization.get("generalization_supported_without_iid_assumption") is not True:
        raise P19EvidenceError("P19 G1-G5 is unsupported")
    if fault.get("fault_tolerance_supported") is not True:
        raise P19EvidenceError("P19 fault tolerance is unsupported")
    if replication.get("independent_replication_supported") is not True:
        raise P19EvidenceError("P19 independent replication is unsupported")
    if p9.get("anytime_p9_authority_digest") != anytime.get("authority_digest"):
        raise P19EvidenceError("P19 P9/anytime component mismatch")
    if p9.get("ccf_oracle_audit_authority_digest") != ccf.get("authority_digest"):
        raise P19EvidenceError("P19 P9/CCF component mismatch")
    if generalization.get("p9_scientific_v3_authority_digest") != p9.get("authority_digest"):
        raise P19EvidenceError("P19 generalization/P9 lineage mismatch")
    if replication.get("primary_p9_scientific_authority_digest") != p9.get("authority_digest"):
        raise P19EvidenceError("P19 replication/P9 lineage mismatch")
    if replication.get("primary_generalization_authority_digest") != generalization.get("authority_digest"):
        raise P19EvidenceError("P19 replication/generalization lineage mismatch")
    family_id = str(p9.get("family_id", ""))
    if not family_id or fault.get("family_id") != family_id or execution.get("family_id") != family_id:
        raise P19EvidenceError("P19 family lineage mismatch")

    plan = execution.get("statistical_plan")
    if not isinstance(plan, Mapping):
        raise P19EvidenceError("P19 execution freeze lacks statistical plan")
    required_plan_identity = {
        "method": PLAN_METHOD,
        "primary_inference_method": PRIMARY_INFERENCE_METHOD,
        "primary_boundary_method": PRIMARY_BOUNDARY_METHOD,
        "primary_claim_target": PRIMARY_CLAIM_TARGET,
        "primary_assumption_boundary": PRIMARY_ASSUMPTION_BOUNDARY,
        "primary_sequence_order": PRIMARY_SEQUENCE_ORDER,
        "primary_predictor_rule": PRIMARY_PREDICTOR_RULE,
        "confseq_reference_commit": CONFSEQ_REFERENCE_COMMIT,
    }
    for field, expected in required_plan_identity.items():
        if plan.get(field) != expected:
            raise P19EvidenceError(f"P19 execution freeze is not V5 for {field}")
    if anytime.get("statistical_plan_digest") != execution.get("statistical_plan_digest"):
        raise P19EvidenceError("P19 anytime P9 statistical plan differs from execution freeze")
    theorem_digest = _theorem_identity_digest()
    if generalization.get("theorem_identity_digest") != theorem_digest:
        raise P19EvidenceError("P19 G1-G5 theorem identity differs from V5")
    anytime_theorem = sha256_bytes(canonical_json_bytes({
        "method": anytime.get("anytime_method"),
        "boundary_method": anytime.get("anytime_boundary_method"),
        "claim_target": anytime.get("anytime_claim_target"),
        "assumption_boundary": anytime.get("anytime_assumption_boundary"),
        "sequence_order_rule": anytime.get("sequence_order_rule"),
        "predictor_rule": anytime.get("predictor_rule"),
        "confseq_reference_commit": anytime.get("confseq_reference_commit"),
    }))
    if anytime_theorem != theorem_digest:
        raise P19EvidenceError("P19 primary P9 theorem identity differs from V5")

    anchors: list[dict[str, object]] = []
    for rel in METHODOLOGY_ANCHORS:
        path, normalized = _repo_file(root, rel)
        anchors.append({
            "path": normalized,
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
        })
    methodology_anchor_digest = sha256_bytes(canonical_json_bytes(anchors))

    root_rows = tuple(
        _subject_root_manifest(root, label, subject_roots[label])
        for label in sorted(REQUIRED_SUBJECT_ROOTS)
    )
    subject_root_manifest_digest = sha256_bytes(canonical_json_bytes(root_rows))

    receipts = state["receipts"]
    assert isinstance(receipts, list) and receipts
    receipt_tip = _sha("receipt_chain_tip_digest", receipts[-1]["receipt_digest"])
    ledger_snapshot = json.loads(json.dumps(state, sort_keys=True))
    ledger_snapshot_digest = sha256_bytes(canonical_json_bytes(ledger_snapshot))
    family_complete = all((
        p9.get("scientific_p9_supported") is True,
        generalization.get("generalization_supported_without_iid_assumption") is True,
        fault.get("fault_tolerance_supported") is True,
        replication.get("independent_replication_supported") is True,
        len(stage_rows) == len(expected_completed),
        len(root_rows) == len(REQUIRED_SUBJECT_ROOTS),
    ))
    payload = {
        "family_id": family_id,
        "generation_id": ledger.generation_id,
        "repository_commit": ledger.repo_commit,
        "repository_tree": ledger.repo_tree,
        "ledger_schema": str(state["schema"]),
        "ledger_snapshot_digest": ledger_snapshot_digest,
        "ledger_snapshot": ledger_snapshot,
        "receipt_chain_tip_digest": receipt_tip,
        "stage_evidence_manifest_digest": stage_manifest_digest,
        "stage_evidence": stage_rows,
        "primary_p9_scientific_authority_digest": _sha("P9 authority", p9.get("authority_digest")),
        "primary_anytime_p9_authority_digest": _sha("anytime P9 authority", anytime.get("authority_digest")),
        "primary_ccf_oracle_audit_authority_digest": _sha("CCF authority", ccf.get("authority_digest")),
        "generalization_authority_digest": _sha("generalization authority", generalization.get("authority_digest")),
        "fault_tolerance_authority_digest": _sha("fault tolerance authority", fault.get("authority_digest")),
        "independent_replication_authority_digest": _sha("replication authority", replication.get("authority_digest")),
        "statistical_plan_digest": _sha("statistical_plan_digest", execution.get("statistical_plan_digest")),
        "theorem_identity_digest": theorem_digest,
        "methodology_anchor_digest": methodology_anchor_digest,
        "methodology_anchors": anchors,
        "subject_root_manifest_digest": subject_root_manifest_digest,
        "subject_roots": list(root_rows),
        "family_p9_supported": True,
        "family_generalization_supported": True,
        "family_fault_tolerance_supported": True,
        "family_replication_supported": True,
        "family_evidence_complete": family_complete,
    }
    p19_digest = sha256_bytes(canonical_json_bytes(payload))
    return FamilyP19EvidenceRoot(
        family_id=family_id,
        generation_id=ledger.generation_id,
        repository_commit=ledger.repo_commit,
        repository_tree=ledger.repo_tree,
        ledger_schema=payload["ledger_schema"],
        ledger_snapshot_digest=ledger_snapshot_digest,
        ledger_snapshot=ledger_snapshot,
        receipt_chain_tip_digest=receipt_tip,
        stage_evidence_manifest_digest=stage_manifest_digest,
        stage_evidence=tuple(stage_rows),
        primary_p9_scientific_authority_digest=payload["primary_p9_scientific_authority_digest"],
        primary_anytime_p9_authority_digest=payload["primary_anytime_p9_authority_digest"],
        primary_ccf_oracle_audit_authority_digest=payload["primary_ccf_oracle_audit_authority_digest"],
        generalization_authority_digest=payload["generalization_authority_digest"],
        fault_tolerance_authority_digest=payload["fault_tolerance_authority_digest"],
        independent_replication_authority_digest=payload["independent_replication_authority_digest"],
        statistical_plan_digest=payload["statistical_plan_digest"],
        theorem_identity_digest=theorem_digest,
        methodology_anchor_digest=methodology_anchor_digest,
        methodology_anchors=tuple(anchors),
        subject_root_manifest_digest=subject_root_manifest_digest,
        subject_roots=root_rows,
        family_p9_supported=True,
        family_generalization_supported=True,
        family_fault_tolerance_supported=True,
        family_replication_supported=True,
        family_evidence_complete=family_complete,
        p19_digest=p19_digest,
    )


def verify_family_p19_evidence_root_document(path: Path) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise P19EvidenceError("P19 evidence root must be a regular file")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise P19EvidenceError("invalid P19 JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise P19EvidenceError("unexpected P19 schema")
    if doc.get("p19_sealed") is not True or doc.get("family_qualification_ready") is not True:
        raise P19EvidenceError("P19 family evidence is incomplete")
    if doc.get("global_product_qualification_authorized") is not False or doc.get("peer_family_p19_required") is not True:
        raise P19EvidenceError("P19 global claim boundary malformed")
    keys = (
        "family_id", "generation_id", "repository_commit", "repository_tree", "ledger_schema",
        "ledger_snapshot_digest", "ledger_snapshot", "receipt_chain_tip_digest",
        "stage_evidence_manifest_digest", "stage_evidence", "primary_p9_scientific_authority_digest",
        "primary_anytime_p9_authority_digest", "primary_ccf_oracle_audit_authority_digest",
        "generalization_authority_digest", "fault_tolerance_authority_digest",
        "independent_replication_authority_digest", "statistical_plan_digest", "theorem_identity_digest",
        "methodology_anchor_digest", "methodology_anchors", "subject_root_manifest_digest", "subject_roots",
        "family_p9_supported", "family_generalization_supported", "family_fault_tolerance_supported",
        "family_replication_supported", "family_evidence_complete",
    )
    try:
        payload = {key: doc[key] for key in keys}
    except KeyError as exc:
        raise P19EvidenceError("P19 payload incomplete") from exc
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("p19_digest", doc.get("p19_digest")):
        raise P19EvidenceError("P19 digest mismatch")
    snapshot = doc.get("ledger_snapshot")
    if not isinstance(snapshot, Mapping):
        raise P19EvidenceError("P19 ledger snapshot missing")
    if doc.get("ledger_schema") != snapshot.get("schema"):
        raise P19EvidenceError("P19 ledger schema differs from embedded snapshot")
    if sha256_bytes(canonical_json_bytes(snapshot)) != _sha("ledger_snapshot_digest", doc.get("ledger_snapshot_digest")):
        raise P19EvidenceError("P19 ledger snapshot digest mismatch")
    _verify_pre_p19_ledger_snapshot(
        snapshot,
        generation_id=str(doc.get("generation_id", "")),
        repository_commit=str(doc.get("repository_commit", "")),
        repository_tree=str(doc.get("repository_tree", "")),
    )
    receipts = snapshot.get("receipts")
    assert isinstance(receipts, list) and receipts
    if doc.get("receipt_chain_tip_digest") != receipts[-1].get("receipt_digest"):
        raise P19EvidenceError("P19 receipt-chain tip differs from embedded ledger snapshot")
    stage_rows = doc.get("stage_evidence")
    if not isinstance(stage_rows, list) or sha256_bytes(canonical_json_bytes(stage_rows)) != doc.get("stage_evidence_manifest_digest"):
        raise P19EvidenceError("P19 stage evidence manifest digest mismatch")
    completed = snapshot.get("completed_stages")
    if [row.get("stage") for row in stage_rows if isinstance(row, Mapping)] != completed:
        raise P19EvidenceError("P19 stage evidence order differs from embedded ledger")
    if len(stage_rows) != len(receipts):
        raise P19EvidenceError("P19 stage evidence/receipt population mismatch")
    for stage_row, receipt in zip(stage_rows, receipts, strict=True):
        if not isinstance(stage_row, Mapping) or not isinstance(receipt, Mapping):
            raise P19EvidenceError("P19 stage/receipt row malformed")
        if stage_row.get("receipt_digest") != receipt.get("receipt_digest"):
            raise P19EvidenceError("P19 stage manifest references a different receipt chain")
        evidence = receipt.get("evidence")
        if not isinstance(evidence, list) or len(evidence) != 1 or not isinstance(evidence[0], Mapping):
            raise P19EvidenceError("P19 embedded receipt evidence malformed")
        if dict(stage_row.get("evidence", {})) != dict(evidence[0]):
            raise P19EvidenceError("P19 stage evidence differs from embedded receipt evidence")
    if doc.get("theorem_identity_digest") != _theorem_identity_digest():
        raise P19EvidenceError("P19 theorem identity is not current V5")
    if not all(doc.get(field) is True for field in (
        "family_p9_supported", "family_generalization_supported",
        "family_fault_tolerance_supported", "family_replication_supported", "family_evidence_complete",
    )):
        raise P19EvidenceError("P19 family support flags incomplete")
    roots = doc.get("subject_roots")
    if not isinstance(roots, list) or {str(row.get("label")) for row in roots if isinstance(row, Mapping)} != REQUIRED_SUBJECT_ROOTS:
        raise P19EvidenceError("P19 subject root population mismatch")
    return doc
