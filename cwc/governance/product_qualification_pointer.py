from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.evidence_closure import EvidenceClosureLedger, STAGES, sha256_file
from cwc.governance.global_product_qualification_v4 import verify_global_product_qualification_authority_v4_document
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes

SCHEMA = "DGC_PRODUCT_QUALIFICATION_POINTER_V1"
CANONICAL_POINTER_PATH = "artifacts/dgc-product-v1/PRODUCT_QUALIFICATION_POINTER_V1.json"


class ProductQualificationPointerError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise ProductQualificationPointerError(f"{name} must be lowercase SHA-256")
    return text


def _oid(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 40 or any(ch not in "0123456789abcdef" for ch in text):
        raise ProductQualificationPointerError(f"{name} must be lowercase 40-hex Git object id")
    return text


def _safe_repo_file(root: Path, value: object, *, label: str) -> Path:
    rel = Path(str(value))
    if not str(value) or rel.is_absolute() or ".." in rel.parts:
        raise ProductQualificationPointerError(f"{label} must be repository-relative")
    candidate = root / rel
    if candidate.is_symlink():
        raise ProductQualificationPointerError(f"{label} symlink rejected")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ProductQualificationPointerError(f"{label} escapes repository") from exc
    if not resolved.is_file() or resolved.stat().st_size <= 0:
        raise ProductQualificationPointerError(f"{label} missing/empty")
    return resolved


@dataclass(frozen=True, slots=True)
class VerifiedProductQualificationPointer:
    generation_id: str
    repo_commit: str
    repo_tree: str
    ledger_path: str
    ledger_sha256: str
    global_v4_authority_path: str
    global_v4_authority_sha256: str
    global_v4_authority_digest: str
    ledger_tip_receipt_digest: str
    pointer_digest: str


def load_product_qualification_pointer(path: Path) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise ProductQualificationPointerError("product qualification pointer must be a regular file")
    try:
        raw = candidate.read_bytes()
        doc = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ProductQualificationPointerError("invalid product qualification pointer JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise ProductQualificationPointerError("unexpected product qualification pointer schema")
    if raw != canonical_json_bytes(doc) + b"\n":
        raise ProductQualificationPointerError("product qualification pointer must use canonical JSON bytes")
    payload_keys = (
        "pointer_generation", "activation_authorized", "ledger_path", "global_v4_authority_path",
        "generation_id", "repo_commit", "repo_tree", "ledger_sha256", "global_v4_authority_sha256",
        "global_v4_authority_digest", "product_qualified_claimed", "production_control_authorized",
    )
    try:
        payload = {key: doc[key] for key in payload_keys}
    except KeyError as exc:
        raise ProductQualificationPointerError("product qualification pointer payload incomplete") from exc
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("pointer_digest", doc.get("pointer_digest")):
        raise ProductQualificationPointerError("product qualification pointer digest mismatch")
    if doc.get("production_control_authorized") is not False:
        raise ProductQualificationPointerError("product qualification pointer cannot authorize production control")
    return doc


def verify_product_qualification_pointer(
    *,
    repository_root: Path,
    pointer_path: Path = Path(CANONICAL_POINTER_PATH),
    expected_repo_commit: str | None = None,
    expected_repo_tree: str | None = None,
) -> VerifiedProductQualificationPointer:
    root = Path(repository_root).resolve()
    path = Path(pointer_path)
    if not path.is_absolute():
        path = root / path
    doc = load_product_qualification_pointer(path)
    if doc.get("activation_authorized") is not True or doc.get("product_qualified_claimed") is not True:
        raise ProductQualificationPointerError("product qualification pointer is not activated")
    generation_id = str(doc.get("generation_id", "")).strip()
    if not generation_id or generation_id == "UNCONFIGURED":
        raise ProductQualificationPointerError("product qualification generation_id is not configured")
    repo_commit = _oid("repo_commit", doc.get("repo_commit"))
    repo_tree = _oid("repo_tree", doc.get("repo_tree"))
    if expected_repo_commit is not None and repo_commit != str(expected_repo_commit).lower():
        raise ProductQualificationPointerError("qualification pointer commit differs from release HEAD")
    if expected_repo_tree is not None and repo_tree != str(expected_repo_tree).lower():
        raise ProductQualificationPointerError("qualification pointer tree differs from release HEAD")

    ledger_path = _safe_repo_file(root, doc.get("ledger_path"), label="qualification ledger")
    global_path = _safe_repo_file(root, doc.get("global_v4_authority_path"), label="global V4 authority")
    ledger_sha = sha256_file(ledger_path)
    global_sha = sha256_file(global_path)
    if ledger_sha != _sha("ledger_sha256", doc.get("ledger_sha256")):
        raise ProductQualificationPointerError("qualification ledger bytes differ from pointer")
    if global_sha != _sha("global_v4_authority_sha256", doc.get("global_v4_authority_sha256")):
        raise ProductQualificationPointerError("global V4 authority bytes differ from pointer")

    global_doc = verify_global_product_qualification_authority_v4_document(global_path)
    global_digest = _sha("global_v4_authority_digest", global_doc.get("authority_digest"))
    if global_digest != _sha("pointer.global_v4_authority_digest", doc.get("global_v4_authority_digest")):
        raise ProductQualificationPointerError("global V4 authority digest differs from pointer")
    if global_doc.get("repository_commit") != repo_commit or global_doc.get("repository_tree") != repo_tree:
        raise ProductQualificationPointerError("global V4 repository identity differs from pointer")

    ledger = EvidenceClosureLedger(
        repository_root=root,
        ledger_path=ledger_path,
        generation_id=generation_id,
        repo_commit=repo_commit,
        repo_tree=repo_tree,
    )
    state = ledger.load()
    if state.get("completed_stages") != list(STAGES) or state.get("product_qualified") is not True:
        raise ProductQualificationPointerError("qualification ledger is not terminal PRODUCT_QUALIFIED")
    receipts = state.get("receipts")
    if not isinstance(receipts, list) or not receipts:
        raise ProductQualificationPointerError("qualification ledger receipt chain missing")
    final = receipts[-1]
    if not isinstance(final, Mapping) or final.get("stage") != "PRODUCT_QUALIFIED":
        raise ProductQualificationPointerError("qualification ledger terminal receipt malformed")
    evidence = final.get("evidence")
    if not isinstance(evidence, list) or len(evidence) != 1 or not isinstance(evidence[0], Mapping):
        raise ProductQualificationPointerError("PRODUCT_QUALIFIED receipt must bind one global V4 artifact")
    row = evidence[0]
    try:
        receipt_evidence_path = (root / str(row.get("path", ""))).resolve().relative_to(root).as_posix()
        pointer_global_path = global_path.relative_to(root).as_posix()
    except ValueError as exc:
        raise ProductQualificationPointerError("PRODUCT_QUALIFIED evidence path escapes repository") from exc
    if receipt_evidence_path != pointer_global_path:
        raise ProductQualificationPointerError("PRODUCT_QUALIFIED receipt references a different global authority")
    if row.get("sha256") != global_sha or int(row.get("bytes", -1)) != global_path.stat().st_size:
        raise ProductQualificationPointerError("PRODUCT_QUALIFIED receipt/global authority byte binding mismatch")
    tip = _sha("ledger_tip_receipt_digest", final.get("receipt_digest"))
    return VerifiedProductQualificationPointer(
        generation_id=generation_id,
        repo_commit=repo_commit,
        repo_tree=repo_tree,
        ledger_path=ledger_path.relative_to(root).as_posix(),
        ledger_sha256=ledger_sha,
        global_v4_authority_path=pointer_global_path,
        global_v4_authority_sha256=global_sha,
        global_v4_authority_digest=global_digest,
        ledger_tip_receipt_digest=tip,
        pointer_digest=_sha("pointer_digest", doc.get("pointer_digest")),
    )
