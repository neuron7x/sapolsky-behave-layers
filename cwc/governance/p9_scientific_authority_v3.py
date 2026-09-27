from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from cwc.governance.ccf_oracle_audit_authority import verify_ccf_oracle_audit_authority_document
from cwc.governance.executed_p9_anytime_authority import verify_anytime_p9_authority_document
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes

SCHEMA = "DGC_P9_SCIENTIFIC_AUTHORITY_V3"
CLAIM_SCOPE = "EXACT_PANEL_PLUS_ANYTIME_VALID_ACM_PLUS_CCF_V1"


class P9ScientificV3Error(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise P9ScientificV3Error(f"{name} must be lowercase SHA-256")
    return text


@dataclass(frozen=True, slots=True)
class P9ScientificAuthorityV3:
    family_id: str
    anytime_p9_authority_digest: str
    ccf_oracle_audit_authority_digest: str
    execution_authority_digest: str
    execution_population_digest: str
    execution_bundle_digest: str
    physical_cost_bundle_digest: str
    physical_cost_population_digest: str
    harness_freeze_digest: str
    confirmatory_task_manifest_digest: str
    exact_panel_certificate_digest: str
    exact_panel_supported: bool
    anytime_certificate_digest: str
    anytime_average_conditional_mean_supported: bool
    ccf_headroom_audit_complete: bool
    ccf_total_value_regret_units: int
    ccf_total_avoidable_cost_units: int
    ccf_max_value_regret_units: int
    ccf_max_avoidable_cost_units: int
    scientific_p9_supported: bool
    generalization_evaluation_authorized: bool
    authority_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            **asdict(self),
            "claim_scope": CLAIM_SCOPE,
            "iid_assumption_required": False,
            "provider_request_independence_required": False,
            "product_promotion_authorized": False,
        }


def build_p9_scientific_authority_v3(
    *,
    anytime_p9_authority_path: Path,
    ccf_oracle_audit_authority_path: Path,
) -> P9ScientificAuthorityV3:
    p9 = verify_anytime_p9_authority_document(Path(anytime_p9_authority_path))
    ccf = verify_ccf_oracle_audit_authority_document(Path(ccf_oracle_audit_authority_path))
    if p9.get("family_id") != ccf.get("family_id"):
        raise P9ScientificV3Error("P9/CCF family lineage mismatch")
    for field in (
        "execution_authority_digest", "execution_population_digest", "execution_bundle_digest",
        "physical_cost_bundle_digest", "physical_cost_population_digest", "harness_freeze_digest",
        "confirmatory_task_manifest_digest",
    ):
        if p9.get(field) != ccf.get(field):
            raise P9ScientificV3Error(f"P9/CCF lineage mismatch for {field}")
    exact = p9.get("exact_panel_supported") is True
    anytime = p9.get("anytime_average_conditional_mean_supported") is True
    ccf_complete = ccf.get("headroom_audit_complete") is True
    scientific = exact and anytime and ccf_complete
    payload = {
        "family_id": str(p9["family_id"]),
        "anytime_p9_authority_digest": _sha("anytime P9 authority_digest", p9.get("authority_digest")),
        "ccf_oracle_audit_authority_digest": _sha("CCF authority_digest", ccf.get("authority_digest")),
        "execution_authority_digest": _sha("execution_authority_digest", p9.get("execution_authority_digest")),
        "execution_population_digest": _sha("execution_population_digest", p9.get("execution_population_digest")),
        "execution_bundle_digest": _sha("execution_bundle_digest", p9.get("execution_bundle_digest")),
        "physical_cost_bundle_digest": _sha("physical_cost_bundle_digest", p9.get("physical_cost_bundle_digest")),
        "physical_cost_population_digest": _sha("physical_cost_population_digest", p9.get("physical_cost_population_digest")),
        "harness_freeze_digest": _sha("harness_freeze_digest", p9.get("harness_freeze_digest")),
        "confirmatory_task_manifest_digest": _sha(
            "confirmatory_task_manifest_digest", p9.get("confirmatory_task_manifest_digest")
        ),
        "exact_panel_certificate_digest": _sha(
            "exact_panel_certificate_digest", p9.get("exact_panel_certificate_digest")
        ),
        "exact_panel_supported": exact,
        "anytime_certificate_digest": _sha("anytime_certificate_digest", p9.get("anytime_certificate_digest")),
        "anytime_average_conditional_mean_supported": anytime,
        "ccf_headroom_audit_complete": ccf_complete,
        "ccf_total_value_regret_units": int(ccf["total_value_regret_units"]),
        "ccf_total_avoidable_cost_units": int(ccf["total_avoidable_cost_units"]),
        "ccf_max_value_regret_units": int(ccf["max_value_regret_units"]),
        "ccf_max_avoidable_cost_units": int(ccf["max_avoidable_cost_units"]),
        "scientific_p9_supported": scientific,
        "generalization_evaluation_authorized": scientific,
    }
    return P9ScientificAuthorityV3(
        **payload,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_p9_scientific_authority_v3_document(path: Path) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise P9ScientificV3Error("P9 scientific V3 authority must be a regular file")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise P9ScientificV3Error("invalid P9 scientific V3 JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise P9ScientificV3Error("unexpected P9 scientific V3 schema")
    if doc.get("claim_scope") != CLAIM_SCOPE:
        raise P9ScientificV3Error("P9 scientific V3 claim scope mismatch")
    if doc.get("iid_assumption_required") is not False or doc.get("provider_request_independence_required") is not False:
        raise P9ScientificV3Error("P9 scientific V3 incorrectly requires iid/independence")
    if doc.get("product_promotion_authorized") is not False:
        raise P9ScientificV3Error("P9 scientific V3 cannot authorize product promotion")
    keys = (
        "family_id", "anytime_p9_authority_digest", "ccf_oracle_audit_authority_digest",
        "execution_authority_digest", "execution_population_digest", "execution_bundle_digest",
        "physical_cost_bundle_digest", "physical_cost_population_digest", "harness_freeze_digest",
        "confirmatory_task_manifest_digest", "exact_panel_certificate_digest", "exact_panel_supported",
        "anytime_certificate_digest", "anytime_average_conditional_mean_supported",
        "ccf_headroom_audit_complete", "ccf_total_value_regret_units", "ccf_total_avoidable_cost_units",
        "ccf_max_value_regret_units", "ccf_max_avoidable_cost_units", "scientific_p9_supported",
        "generalization_evaluation_authorized",
    )
    try:
        payload = {key: doc[key] for key in keys}
    except KeyError as exc:
        raise P9ScientificV3Error("P9 scientific V3 payload incomplete") from exc
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("authority_digest", doc.get("authority_digest")):
        raise P9ScientificV3Error("P9 scientific V3 authority digest mismatch")
    derived = (
        doc.get("exact_panel_supported") is True
        and doc.get("anytime_average_conditional_mean_supported") is True
        and doc.get("ccf_headroom_audit_complete") is True
    )
    if doc.get("scientific_p9_supported") is not derived:
        raise P9ScientificV3Error("scientific P9 support is not derivable from exact + anytime + CCF")
    if doc.get("generalization_evaluation_authorized") is not derived:
        raise P9ScientificV3Error("generalization evaluation authority is not derivable from scientific P9")
    for field in (
        "anytime_p9_authority_digest", "ccf_oracle_audit_authority_digest", "execution_authority_digest",
        "execution_population_digest", "execution_bundle_digest", "physical_cost_bundle_digest",
        "physical_cost_population_digest", "harness_freeze_digest", "confirmatory_task_manifest_digest",
        "exact_panel_certificate_digest", "anytime_certificate_digest",
    ):
        _sha(field, doc.get(field))
    return doc
