from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.exact_finite_panel_pareto import (
    certificate_digest as exact_certificate_digest,
    certify_exact_finite_panel,
)
from cwc.governance.executed_p9_finite_panel_authority import (
    FinitePanelP9Authority,
    build_finite_panel_p9_authority,
)
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes
from cwc.governance.pareto import PairedBaselineEvidence

SCHEMA = "DGC_EXECUTED_P9_DUAL_AUTHORITY_V5"
CLAIM_SCOPE = "EXACT_PANEL_FACT_PLUS_CONDITIONAL_EXPECTED_EFFECT_REQUIRED_FOR_P9_V2"


class DualP9AuthorityError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise DualP9AuthorityError(f"{name} must be lowercase SHA-256")
    return text


def _paired_rows(base: FinitePanelP9Authority) -> tuple[PairedBaselineEvidence, ...]:
    result: list[PairedBaselineEvidence] = []
    for raw in base.paired_evidence:
        try:
            result.append(PairedBaselineEvidence(
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
            raise DualP9AuthorityError("finite-panel paired evidence cannot be reconstructed") from exc
    return tuple(result)


@dataclass(frozen=True, slots=True)
class DualP9Authority:
    family_id: str
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
    exact_panel_certificate: dict[str, object]
    exact_panel_certificate_digest: str
    exact_panel_supported: bool
    expected_effect_certificate_digest: str
    expected_effect_supported_under_independence_assumption: bool
    randomness_protocol: str
    randomness_schedule_digest: str
    randomness_independence_assumption: str
    randomness_assumption_verified: bool
    claim_scope: str
    p9_supported_under_frozen_assumptions: bool
    generalization_evaluation_authorized: bool
    authority_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            **asdict(self),
            "physical_cost_accounting_verified": True,
            "product_promotion_authorized": False,
        }


def build_dual_p9_authority(
    *,
    confirmatory_execution_authority_path: Path,
    execution_bundle_root: Path,
    physical_cost_bundle_root: Path,
    confirmatory_root_authority_path: Path,
    harness_freeze_path: Path,
    execution_manifest_freeze_path: Path,
    materialization_reference_path: Path,
    source_registry_path: Path,
) -> DualP9Authority:
    base = build_finite_panel_p9_authority(
        confirmatory_execution_authority_path=Path(confirmatory_execution_authority_path),
        execution_bundle_root=Path(execution_bundle_root),
        physical_cost_bundle_root=Path(physical_cost_bundle_root),
        confirmatory_root_authority_path=Path(confirmatory_root_authority_path),
        harness_freeze_path=Path(harness_freeze_path),
        execution_manifest_freeze_path=Path(execution_manifest_freeze_path),
        materialization_reference_path=Path(materialization_reference_path),
        source_registry_path=Path(source_registry_path),
    )
    paired = _paired_rows(base)
    conditional = base.p9_certificate
    try:
        qmargin = float(conditional["quality_noninferiority_margin"])
        cmargin = float(conditional["catastrophic_noninferiority_margin"])
    except (KeyError, TypeError, ValueError) as exc:
        raise DualP9AuthorityError("conditional P9 certificate margins missing") from exc
    exact = certify_exact_finite_panel(
        paired,
        quality_noninferiority_margin=qmargin,
        catastrophic_noninferiority_margin=cmargin,
    )
    exact_doc = asdict(exact)
    exact_digest = exact_certificate_digest(exact)
    exact_supported = bool(exact.all_baselines_observed)
    conditional_supported = bool(base.p9_supported_under_protocol_assumption)
    scientific_supported = exact_supported and conditional_supported
    payload = {
        "family_id": base.family_id,
        "finite_panel_v3_authority_digest": base.authority_digest,
        "execution_authority_digest": base.execution_authority_digest,
        "execution_population_digest": base.execution_population_digest,
        "execution_bundle_digest": base.execution_bundle_digest,
        "physical_cost_bundle_digest": base.physical_cost_bundle_digest,
        "physical_cost_population_digest": base.physical_cost_population_digest,
        "harness_freeze_digest": base.harness_freeze_digest,
        "confirmatory_task_manifest_digest": base.confirmatory_task_manifest_digest,
        "statistical_plan_digest": base.statistical_plan_digest,
        "paired_panel_digest": base.paired_panel_digest,
        "exact_panel_certificate": exact_doc,
        "exact_panel_certificate_digest": exact_digest,
        "exact_panel_supported": exact_supported,
        "expected_effect_certificate_digest": base.p9_certificate_digest,
        "expected_effect_supported_under_independence_assumption": conditional_supported,
        "randomness_protocol": base.randomness_protocol,
        "randomness_schedule_digest": base.randomness_schedule_digest,
        "randomness_independence_assumption": base.randomness_independence_assumption,
        "randomness_assumption_verified": base.randomness_assumption_verified,
        "claim_scope": CLAIM_SCOPE,
        "p9_supported_under_frozen_assumptions": scientific_supported,
        "generalization_evaluation_authorized": scientific_supported,
    }
    return DualP9Authority(
        **payload,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_dual_p9_authority_document(path: Path) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise DualP9AuthorityError("dual P9 authority must be a regular file")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DualP9AuthorityError("invalid dual P9 authority JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise DualP9AuthorityError("unexpected dual P9 authority schema")
    if doc.get("claim_scope") != CLAIM_SCOPE:
        raise DualP9AuthorityError("dual P9 claim scope mismatch")
    if doc.get("physical_cost_accounting_verified") is not True:
        raise DualP9AuthorityError("dual P9 requires complete physical cost accounting")
    if doc.get("product_promotion_authorized") is not False:
        raise DualP9AuthorityError("dual P9 cannot authorize product promotion")
    keys = (
        "family_id", "finite_panel_v3_authority_digest", "execution_authority_digest",
        "execution_population_digest", "execution_bundle_digest", "physical_cost_bundle_digest",
        "physical_cost_population_digest", "harness_freeze_digest", "confirmatory_task_manifest_digest",
        "statistical_plan_digest", "paired_panel_digest", "exact_panel_certificate",
        "exact_panel_certificate_digest", "exact_panel_supported", "expected_effect_certificate_digest",
        "expected_effect_supported_under_independence_assumption", "randomness_protocol",
        "randomness_schedule_digest", "randomness_independence_assumption", "randomness_assumption_verified",
        "claim_scope", "p9_supported_under_frozen_assumptions", "generalization_evaluation_authorized",
    )
    try:
        payload = {key: doc[key] for key in keys}
    except KeyError as exc:
        raise DualP9AuthorityError("dual P9 payload incomplete") from exc
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("authority_digest", doc.get("authority_digest")):
        raise DualP9AuthorityError("dual P9 authority digest mismatch")
    exact = doc.get("exact_panel_certificate")
    if not isinstance(exact, Mapping):
        raise DualP9AuthorityError("exact finite-panel certificate missing")
    if sha256_bytes(canonical_json_bytes(dict(exact))) != _sha(
        "exact_panel_certificate_digest", doc.get("exact_panel_certificate_digest")
    ):
        raise DualP9AuthorityError("exact finite-panel certificate digest mismatch")
    derived_exact = exact.get("all_baselines_observed") is True
    if doc.get("exact_panel_supported") is not derived_exact:
        raise DualP9AuthorityError("exact-panel support flag is not derived from exact certificate")
    derived_scientific = derived_exact and doc.get("expected_effect_supported_under_independence_assumption") is True
    if doc.get("p9_supported_under_frozen_assumptions") is not derived_scientific:
        raise DualP9AuthorityError("scientific P9 support must derive from exact + conditional certificates")
    if doc.get("generalization_evaluation_authorized") is not derived_scientific:
        raise DualP9AuthorityError("generalization evaluation requires scientific P9 support")
    for field in (
        "finite_panel_v3_authority_digest", "execution_authority_digest", "execution_population_digest",
        "execution_bundle_digest", "physical_cost_bundle_digest", "physical_cost_population_digest",
        "harness_freeze_digest", "confirmatory_task_manifest_digest", "statistical_plan_digest",
        "paired_panel_digest", "expected_effect_certificate_digest", "randomness_schedule_digest",
    ):
        _sha(field, doc.get(field))
    return doc
