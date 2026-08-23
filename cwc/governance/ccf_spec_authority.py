from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from cwc.governance.counterfactual_oracle_spec import parse_counterfactual_oracle_spec
from cwc.governance.execution_manifest_freeze import verify_execution_manifest_freeze_document
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file

SCHEMA = "DGC_CCF_SPEC_AUTHORITY_V1"


class CCFSpecAuthorityError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise CCFSpecAuthorityError(f"{name} must be lowercase SHA-256")
    return text


def _spec(path: Path) -> tuple[dict[str, object], str]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise CCFSpecAuthorityError("CCF oracle spec must be a regular file")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CCFSpecAuthorityError("invalid CCF oracle spec JSON") from exc
    if not isinstance(doc, dict):
        raise CCFSpecAuthorityError("CCF oracle spec must be an object")
    try:
        parsed = parse_counterfactual_oracle_spec(doc)
    except ValueError as exc:
        raise CCFSpecAuthorityError("CCF oracle spec semantics invalid") from exc
    normalized = {"schema": doc["schema"], **asdict(parsed)}
    if normalized != doc:
        raise CCFSpecAuthorityError("CCF oracle spec contains unrecognized or noncanonical fields")
    return normalized, sha256_file(candidate)


@dataclass(frozen=True, slots=True)
class CCFSpecAuthority:
    family_id: str
    execution_manifest_freeze_digest: str
    ccf_spec_sha256: str
    ccf_spec_digest: str
    authority_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "family_id": self.family_id,
            "execution_manifest_freeze_digest": self.execution_manifest_freeze_digest,
            "ccf_spec_sha256": self.ccf_spec_sha256,
            "ccf_spec_digest": self.ccf_spec_digest,
            "authority_digest": self.authority_digest,
            "frozen_pre_outcome": True,
            "p9_oracle_audit_authorized": False,
            "product_promotion_authorized": False,
        }


def build_ccf_spec_authority(
    *,
    execution_manifest_freeze_path: Path,
    ccf_spec_path: Path,
) -> CCFSpecAuthority:
    execution = verify_execution_manifest_freeze_document(Path(execution_manifest_freeze_path))
    spec_doc, spec_sha = _spec(Path(ccf_spec_path))
    spec_digest = sha256_bytes(canonical_json_bytes(spec_doc))
    payload = {
        "family_id": str(execution["family_id"]),
        "execution_manifest_freeze_digest": _sha("execution freeze_digest", execution.get("freeze_digest")),
        "ccf_spec_sha256": spec_sha,
        "ccf_spec_digest": spec_digest,
    }
    return CCFSpecAuthority(
        **payload,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_ccf_spec_authority_document(path: Path) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise CCFSpecAuthorityError("CCF spec authority must be a regular file")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CCFSpecAuthorityError("invalid CCF spec authority JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise CCFSpecAuthorityError("unexpected CCF spec authority schema")
    if doc.get("frozen_pre_outcome") is not True:
        raise CCFSpecAuthorityError("CCF spec authority must state pre-outcome freeze")
    if doc.get("p9_oracle_audit_authorized") is not False or doc.get("product_promotion_authorized") is not False:
        raise CCFSpecAuthorityError("CCF spec freeze cannot grant downstream authority")
    payload = {
        "family_id": doc.get("family_id"),
        "execution_manifest_freeze_digest": _sha(
            "execution_manifest_freeze_digest", doc.get("execution_manifest_freeze_digest")
        ),
        "ccf_spec_sha256": _sha("ccf_spec_sha256", doc.get("ccf_spec_sha256")),
        "ccf_spec_digest": _sha("ccf_spec_digest", doc.get("ccf_spec_digest")),
    }
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("authority_digest", doc.get("authority_digest")):
        raise CCFSpecAuthorityError("CCF spec authority digest mismatch")
    return doc
