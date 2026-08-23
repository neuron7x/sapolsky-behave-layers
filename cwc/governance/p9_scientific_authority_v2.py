from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from cwc.governance.ccf_oracle_audit_authority import verify_ccf_oracle_audit_authority_document
from cwc.governance.executed_p9_dual_authority import verify_dual_p9_authority_document
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes

SCHEMA = "DGC_P9_SCIENTIFIC_AUTHORITY_V2"


class P9ScientificAuthorityV2Error(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise P9ScientificAuthorityV2Error(f"{name} must be lowercase SHA-256")
    return text


@dataclass(frozen=True, slots=True)
class P9ScientificAuthorityV2:
    family_id: str
    dual_p9_authority_digest: str
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
    expected_effect_certificate_digest: str
    expected_effect_supported_under_independence_assumption: bool
    randomness_independence_assumption: str
    randomness_assumption_verified: bool
    ccf_headroom_audit_complete: bool
    ccf_total_value_regret_units: int
    ccf_total_avoidable_cost_units: int
    ccf_max_value_regret_units: int
    ccf_max_avoidable_cost_units: int
    generalization_evaluation_authorized: bool
    authority_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            **asdict(self),
            "claim_scope": "EXACT_PRIMARY_PANEL_PLUS_CCF_WITH_CONDITIONAL_EXPECTATION_AUXILIARY_V1",
            "product_promotion_authorized": False,
        }


def build_p9_scientific_authority_v2(
    *,
    dual_p9_authority_path: Path,
    ccf_oracle_audit_authority_path: Path,
) -> P9ScientificAuthorityV2:
    p9 = verify_dual_p9_authority_document(Path(dual_p9_authority_path))
    ccf = verify_ccf_oracle_audit_authority_document(Path(ccf_oracle_audit_authority_path))
    if p9.get("family_id") != ccf.get("family_id"):
        raise P9ScientificAuthorityV2Error("P9/CCF family lineage mismatch")
    for field in (
        "execution_authority_digest", "execution_population_digest", "execution_bundle_digest",
        "physical_cost_bundle_digest", "physical_cost_population_digest", "harness_freeze_digest",
        "confirmatory_task_manifest_digest",
    ):
        if p9.get(field) != ccf.get(field):
            raise P9ScientificAuthorityV2Error(f"P9/CCF lineage mismatch for {field}")
    exact = p9.get("exact_panel_supported") is True
    ccf_complete = ccf.get("headroom_audit_complete") is True
    authorize_generalization = exact and ccf_complete
    payload = {
        "family_id": str(p9["family_id"]),
        "dual_p9_authority_digest": _sha("dual P9 authority_digest", p9.get("authority_digest")),
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
        "expected_effect_certificate_digest": _sha(
            "expected_effect_certificate_digest", p9.get("expected_effect_certificate_digest")
        ),
        "expected_effect_supported_under_independence_assumption": p9.get(
            "expected_effect_supported_under_independence_assumption"
        ) is True,
        "randomness_independence_assumption": str(p9.get("randomness_independence_assumption", "")),
        "randomness_assumption_verified": p9.get("randomness_assumption_verified") is True,
        "ccf_headroom_audit_complete": ccf_complete,
        "ccf_total_value_regret_units": int(ccf["total_value_regret_units"]),
        "ccf_total_avoidable_cost_units": int(ccf["total_avoidable_cost_units"]),
        "ccf_max_value_regret_units": int(ccf["max_value_regret_units"]),
        "ccf_max_avoidable_cost_units": int(ccf["max_avoidable_cost_units"]),
        "generalization_evaluation_authorized": authorize_generalization,
    }
    return P9ScientificAuthorityV2(
        **payload,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_p9_scientific_authority_v2_document(path: Path) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise P9ScientificAuthorityV2Error("P9 scientific V2 authority must be a regular file")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise P9ScientificAuthorityV2Error("invalid P9 scientific V2 JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise P9ScientificAuthorityV2Error("unexpected P9 scientific V2 schema")
    if doc.get("claim_scope") != "EXACT_PRIMARY_PANEL_PLUS_CCF_WITH_CONDITIONAL_EXPECTATION_AUXILIARY_V1":
        raise P9ScientificAuthorityV2Error("P9 scientific V2 claim scope mismatch")
    if doc.get("product_promotion_authorized") is not False:
        raise P9ScientificAuthorityV2Error("P9 scientific V2 cannot authorize product promotion")
    keys = (
        "family_id", "dual_p9_authority_digest", "ccf_oracle_audit_authority_digest",
        "execution_authority_digest", "execution_population_digest", "execution_bundle_digest",
        "physical_cost_bundle_digest", "physical_cost_population_digest", "harness_freeze_digest",
        "confirmatory_task_manifest_digest", "exact_panel_certificate_digest", "exact_panel_supported",
        "expected_effect_certificate_digest", "expected_effect_supported_under_independence_assumption",
        "randomness_independence_assumption", "randomness_assumption_verified", "ccf_headroom_audit_complete",
        "ccf_total_value_regret_units", "ccf_total_avoidable_cost_units", "ccf_max_value_regret_units",
        "ccf_max_avoidable_cost_units", "generalization_evaluation_authorized",
    )
    try:
        payload = {key: doc[key] for key in keys}
    except KeyError as exc:
        raise P9ScientificAuthorityV2Error("P9 scientific V2 payload incomplete") from exc
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("authority_digest", doc.get("authority_digest")):
        raise P9ScientificAuthorityV2Error("P9 scientific V2 authority digest mismatch")
    derived = doc.get("exact_panel_supported") is True and doc.get("ccf_headroom_audit_complete") is True
    if doc.get("generalization_evaluation_authorized") is not derived:
        raise P9ScientificAuthorityV2Error("generalization evaluation authority is not derivable from exact P9 + CCF")
    for field in (
        "dual_p9_authority_digest", "ccf_oracle_audit_authority_digest", "execution_authority_digest",
        "execution_population_digest", "execution_bundle_digest", "physical_cost_bundle_digest",
        "physical_cost_population_digest", "harness_freeze_digest", "confirmatory_task_manifest_digest",
        "exact_panel_certificate_digest", "expected_effect_certificate_digest",
    ):
        _sha(field, doc.get(field))
    return doc
