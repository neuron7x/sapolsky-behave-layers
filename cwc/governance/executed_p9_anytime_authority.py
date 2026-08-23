from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

from cwc.governance.average_conditional_mean_cs import (
    ASSUMPTION_BOUNDARY,
    CLAIM_TARGET,
    METHOD,
    SEQUENCE_ORDER_RULE,
    certify_multi_baseline_anytime_valid,
)
from cwc.governance.executed_p9_dual_authority import build_dual_p9_authority
from cwc.governance.executed_p9_finite_panel_authority import build_finite_panel_p9_authority
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes
from cwc.governance.pareto import PairedBaselineEvidence

SCHEMA = "DGC_EXECUTED_P9_ANYTIME_AUTHORITY_V6"
CLAIM_SCOPE = "EXACT_FROZEN_PANEL_PLUS_ANYTIME_VALID_AVERAGE_CONDITIONAL_MEAN_V1"


class AnytimeP9AuthorityError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise AnytimeP9AuthorityError(f"{name} must be lowercase SHA-256")
    return text


def _paired_rows(raw_rows: tuple[dict[str, object], ...]) -> tuple[PairedBaselineEvidence, ...]:
    rows: list[PairedBaselineEvidence] = []
    for raw in raw_rows:
        try:
            rows.append(PairedBaselineEvidence(
                baseline_id=str(raw["baseline_id"]),
                paired_task_digest=str(raw["paired_task_digest"]),
                coverage=float(raw["coverage"]),
                baseline_minus_dgc_cost=tuple(float(x) for x in raw["baseline_minus_dgc_cost"]),
                dgc_minus_baseline_quality=tuple(float(x) for x in raw["dgc_minus_baseline_quality"]),
                baseline_minus_dgc_catastrophic_regret=tuple(
                    float(x) for x in raw["baseline_minus_dgc_catastrophic_regret"]
                ),
                cost_gain_support=tuple(float(x) for x in raw["cost_gain_support"]),
                quality_gain_support=tuple(float(x) for x in raw["quality_gain_support"]),
                catastrophic_gain_support=tuple(float(x) for x in raw["catastrophic_gain_support"]),
            ))
        except (KeyError, TypeError, ValueError) as exc:
            raise AnytimeP9AuthorityError("paired P9 evidence cannot be reconstructed") from exc
    return tuple(rows)


@dataclass(frozen=True, slots=True)
class AnytimeP9Authority:
    family_id: str
    dual_v5_authority_digest: str
    finite_panel_v3_authority_digest: str
    execution_authority_digest: str
    execution_population_digest: str
    execution_bundle_digest: str
    physical_cost_bundle_digest: str
    physical_cost_population_digest: str
    harness_freeze_digest: str
    confirmatory_task_manifest_digest: str
    statistical_plan_digest: str
    paired_panel_digest: str
    exact_panel_certificate_digest: str
    exact_panel_supported: bool
    anytime_certificate: dict[str, object]
    anytime_certificate_digest: str
    anytime_average_conditional_mean_supported: bool
    anytime_method: str
    anytime_claim_target: str
    anytime_assumption_boundary: str
    sequence_order_rule: str
    legacy_micro_eb_certificate_digest: str
    legacy_micro_eb_supported_under_cross_pair_independence: bool
    p9_supported_without_iid_assumption: bool
    generalization_evaluation_authorized: bool
    authority_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            **asdict(self),
            "physical_cost_accounting_verified": True,
            "iid_assumption_required": False,
            "provider_request_independence_required": False,
            "product_promotion_authorized": False,
        }


def build_anytime_p9_authority(
    *,
    confirmatory_execution_authority_path: Path,
    execution_bundle_root: Path,
    physical_cost_bundle_root: Path,
    confirmatory_root_authority_path: Path,
    harness_freeze_path: Path,
    execution_manifest_freeze_path: Path,
    materialization_reference_path: Path,
    source_registry_path: Path,
) -> AnytimeP9Authority:
    dual = build_dual_p9_authority(
        confirmatory_execution_authority_path=Path(confirmatory_execution_authority_path),
        execution_bundle_root=Path(execution_bundle_root),
        physical_cost_bundle_root=Path(physical_cost_bundle_root),
        confirmatory_root_authority_path=Path(confirmatory_root_authority_path),
        harness_freeze_path=Path(harness_freeze_path),
        execution_manifest_freeze_path=Path(execution_manifest_freeze_path),
        materialization_reference_path=Path(materialization_reference_path),
        source_registry_path=Path(source_registry_path),
    )
    finite = build_finite_panel_p9_authority(
        confirmatory_execution_authority_path=Path(confirmatory_execution_authority_path),
        execution_bundle_root=Path(execution_bundle_root),
        physical_cost_bundle_root=Path(physical_cost_bundle_root),
        confirmatory_root_authority_path=Path(confirmatory_root_authority_path),
        harness_freeze_path=Path(harness_freeze_path),
        execution_manifest_freeze_path=Path(execution_manifest_freeze_path),
        materialization_reference_path=Path(materialization_reference_path),
        source_registry_path=Path(source_registry_path),
    )
    if dual.finite_panel_v3_authority_digest != finite.authority_digest:
        raise AnytimeP9AuthorityError("dual and finite-panel lineages differ")
    paired = _paired_rows(finite.paired_evidence)
    conditional = finite.p9_certificate
    try:
        family_alpha = float(finite.family_alpha)
        qmargin = float(conditional["quality_noninferiority_margin"])
        cmargin = float(conditional["catastrophic_noninferiority_margin"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AnytimeP9AuthorityError("frozen P9 alpha/margins unavailable") from exc
    anytime = certify_multi_baseline_anytime_valid(
        paired,
        alpha=family_alpha,
        quality_noninferiority_margin=qmargin,
        catastrophic_noninferiority_margin=cmargin,
    )
    if not math.isclose(anytime.per_metric_alpha, finite.per_metric_delta, rel_tol=0.0, abs_tol=1e-15):
        raise AnytimeP9AuthorityError("anytime-valid multiplicity differs from frozen plan")
    anytime_doc = asdict(anytime)
    anytime_digest = sha256_bytes(canonical_json_bytes(anytime_doc))
    exact_supported = bool(dual.exact_panel_supported)
    anytime_supported = bool(anytime.all_baselines_certified)
    scientific_supported = exact_supported and anytime_supported
    payload = {
        "family_id": finite.family_id,
        "dual_v5_authority_digest": dual.authority_digest,
        "finite_panel_v3_authority_digest": finite.authority_digest,
        "execution_authority_digest": finite.execution_authority_digest,
        "execution_population_digest": finite.execution_population_digest,
        "execution_bundle_digest": finite.execution_bundle_digest,
        "physical_cost_bundle_digest": finite.physical_cost_bundle_digest,
        "physical_cost_population_digest": finite.physical_cost_population_digest,
        "harness_freeze_digest": finite.harness_freeze_digest,
        "confirmatory_task_manifest_digest": finite.confirmatory_task_manifest_digest,
        "statistical_plan_digest": finite.statistical_plan_digest,
        "paired_panel_digest": finite.paired_panel_digest,
        "exact_panel_certificate_digest": dual.exact_panel_certificate_digest,
        "exact_panel_supported": exact_supported,
        "anytime_certificate": anytime_doc,
        "anytime_certificate_digest": anytime_digest,
        "anytime_average_conditional_mean_supported": anytime_supported,
        "anytime_method": METHOD,
        "anytime_claim_target": CLAIM_TARGET,
        "anytime_assumption_boundary": ASSUMPTION_BOUNDARY,
        "sequence_order_rule": SEQUENCE_ORDER_RULE,
        "legacy_micro_eb_certificate_digest": finite.p9_certificate_digest,
        "legacy_micro_eb_supported_under_cross_pair_independence": bool(
            finite.p9_supported_under_protocol_assumption
        ),
        "p9_supported_without_iid_assumption": scientific_supported,
        "generalization_evaluation_authorized": scientific_supported,
    }
    return AnytimeP9Authority(
        **payload,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_anytime_p9_authority_document(path: Path) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise AnytimeP9AuthorityError("anytime P9 authority must be a regular file")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise AnytimeP9AuthorityError("invalid anytime P9 authority JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise AnytimeP9AuthorityError("unexpected anytime P9 schema")
    if doc.get("iid_assumption_required") is not False or doc.get("provider_request_independence_required") is not False:
        raise AnytimeP9AuthorityError("anytime P9 claim boundary incorrectly requires iid/independence")
    if doc.get("physical_cost_accounting_verified") is not True or doc.get("product_promotion_authorized") is not False:
        raise AnytimeP9AuthorityError("anytime P9 promotion boundary malformed")
    keys = (
        "family_id", "dual_v5_authority_digest", "finite_panel_v3_authority_digest",
        "execution_authority_digest", "execution_population_digest", "execution_bundle_digest",
        "physical_cost_bundle_digest", "physical_cost_population_digest", "harness_freeze_digest",
        "confirmatory_task_manifest_digest", "statistical_plan_digest", "paired_panel_digest",
        "exact_panel_certificate_digest", "exact_panel_supported", "anytime_certificate",
        "anytime_certificate_digest", "anytime_average_conditional_mean_supported", "anytime_method",
        "anytime_claim_target", "anytime_assumption_boundary", "sequence_order_rule",
        "legacy_micro_eb_certificate_digest", "legacy_micro_eb_supported_under_cross_pair_independence",
        "p9_supported_without_iid_assumption", "generalization_evaluation_authorized",
    )
    try:
        payload = {key: doc[key] for key in keys}
    except KeyError as exc:
        raise AnytimeP9AuthorityError("anytime P9 payload incomplete") from exc
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("authority_digest", doc.get("authority_digest")):
        raise AnytimeP9AuthorityError("anytime P9 authority digest mismatch")
    cert = doc.get("anytime_certificate")
    if not isinstance(cert, dict):
        raise AnytimeP9AuthorityError("anytime P9 certificate missing")
    if sha256_bytes(canonical_json_bytes(cert)) != _sha("anytime_certificate_digest", doc.get("anytime_certificate_digest")):
        raise AnytimeP9AuthorityError("anytime P9 certificate digest mismatch")
    if doc.get("anytime_method") != METHOD or doc.get("anytime_claim_target") != CLAIM_TARGET:
        raise AnytimeP9AuthorityError("anytime P9 theorem identity mismatch")
    if doc.get("anytime_assumption_boundary") != ASSUMPTION_BOUNDARY or doc.get("sequence_order_rule") != SEQUENCE_ORDER_RULE:
        raise AnytimeP9AuthorityError("anytime P9 assumption/order identity mismatch")
    derived_anytime = cert.get("all_baselines_certified") is True
    if doc.get("anytime_average_conditional_mean_supported") is not derived_anytime:
        raise AnytimeP9AuthorityError("anytime support flag is not derived from certificate")
    derived = doc.get("exact_panel_supported") is True and derived_anytime
    if doc.get("p9_supported_without_iid_assumption") is not derived:
        raise AnytimeP9AuthorityError("P9 support must derive from exact + anytime-valid certificates")
    if doc.get("generalization_evaluation_authorized") is not derived:
        raise AnytimeP9AuthorityError("generalization evaluation must derive from exact + anytime-valid P9")
    for field in (
        "dual_v5_authority_digest", "finite_panel_v3_authority_digest", "execution_authority_digest",
        "execution_population_digest", "execution_bundle_digest", "physical_cost_bundle_digest",
        "physical_cost_population_digest", "harness_freeze_digest", "confirmatory_task_manifest_digest",
        "statistical_plan_digest", "paired_panel_digest", "exact_panel_certificate_digest",
        "legacy_micro_eb_certificate_digest",
    ):
        _sha(field, doc.get(field))
    return doc
