from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from cwc.governance.generalization_dual_authority import verify_generalization_dual_authority_document
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes

SCHEMA = "DGC_GENERALIZATION_SCIENTIFIC_AUTHORITY_V3"
CLAIM_SCOPE = "EXACT_G1_G5_FACTS_PLUS_CONDITIONAL_BOUNDED_INFERENCE_REQUIRED_V1"


class GeneralizationScientificV3Error(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise GeneralizationScientificV3Error(f"{name} must be lowercase SHA-256")
    return text


@dataclass(frozen=True, slots=True)
class GeneralizationScientificAuthorityV3:
    generalization_dual_authority_digest: str
    registry_digest: str
    p9_scientific_authority_digest: str
    frozen_dgc_policy_digest: str
    exact_g1_g5_supported: bool
    expected_g1_g5_supported_under_independence_assumption: bool
    generalization_supported_under_frozen_assumptions: bool
    independent_replication_evaluation_authorized: bool
    authority_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            **asdict(self),
            "claim_scope": CLAIM_SCOPE,
            "product_promotion_authorized": False,
        }


def build_generalization_scientific_authority_v3(
    generalization_dual_authority_path: Path,
) -> GeneralizationScientificAuthorityV3:
    dual = verify_generalization_dual_authority_document(Path(generalization_dual_authority_path))
    exact = dual.get("exact_g1_g5_supported") is True
    conditional = dual.get("expected_g1_g5_supported_under_independence_assumption") is True
    supported = exact and conditional
    payload = {
        "generalization_dual_authority_digest": _sha(
            "generalization dual authority_digest", dual.get("authority_digest")
        ),
        "registry_digest": _sha("registry_digest", dual.get("registry_digest")),
        "p9_scientific_authority_digest": _sha(
            "p9_scientific_v2_authority_digest", dual.get("p9_scientific_v2_authority_digest")
        ),
        "frozen_dgc_policy_digest": _sha("frozen_dgc_policy_digest", dual.get("frozen_dgc_policy_digest")),
        "exact_g1_g5_supported": exact,
        "expected_g1_g5_supported_under_independence_assumption": conditional,
        "generalization_supported_under_frozen_assumptions": supported,
        "independent_replication_evaluation_authorized": supported,
    }
    return GeneralizationScientificAuthorityV3(
        **payload,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_generalization_scientific_authority_v3_document(path: Path) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise GeneralizationScientificV3Error("generalization scientific V3 must be a regular file")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GeneralizationScientificV3Error("invalid generalization scientific V3 JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise GeneralizationScientificV3Error("unexpected generalization scientific V3 schema")
    if doc.get("claim_scope") != CLAIM_SCOPE:
        raise GeneralizationScientificV3Error("generalization scientific V3 claim scope mismatch")
    if doc.get("product_promotion_authorized") is not False:
        raise GeneralizationScientificV3Error("generalization scientific V3 cannot authorize product promotion")
    keys = (
        "generalization_dual_authority_digest", "registry_digest", "p9_scientific_authority_digest",
        "frozen_dgc_policy_digest", "exact_g1_g5_supported",
        "expected_g1_g5_supported_under_independence_assumption",
        "generalization_supported_under_frozen_assumptions",
        "independent_replication_evaluation_authorized",
    )
    try:
        payload = {key: doc[key] for key in keys}
    except KeyError as exc:
        raise GeneralizationScientificV3Error("generalization scientific V3 payload incomplete") from exc
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("authority_digest", doc.get("authority_digest")):
        raise GeneralizationScientificV3Error("generalization scientific V3 authority digest mismatch")
    supported = (
        doc.get("exact_g1_g5_supported") is True
        and doc.get("expected_g1_g5_supported_under_independence_assumption") is True
    )
    if doc.get("generalization_supported_under_frozen_assumptions") is not supported:
        raise GeneralizationScientificV3Error("generalization support must derive from exact+conditional G1-G5")
    if doc.get("independent_replication_evaluation_authorized") is not supported:
        raise GeneralizationScientificV3Error("replication evaluation requires scientific G1-G5 support")
    for field in (
        "generalization_dual_authority_digest", "registry_digest",
        "p9_scientific_authority_digest", "frozen_dgc_policy_digest",
    ):
        _sha(field, doc.get(field))
    return doc
