from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.average_conditional_mean_cs import (
    ASSUMPTION_BOUNDARY,
    CLAIM_TARGET,
    METHOD,
    SEQUENCE_ORDER_RULE,
    certify_multi_baseline_anytime_valid,
)
from cwc.governance.baseline_panel import BaselineKind
from cwc.governance.confirmatory_root_authority import verify_confirmatory_root_authority_document
from cwc.governance.distributed_eval_control import DistributedEvalSpec, WorkUnitId
from cwc.governance.exact_finite_panel_pareto import (
    certificate_digest as exact_certificate_digest,
    certify_exact_finite_panel,
)
from cwc.governance.executed_p9_authority import build_executed_p9_authority
from cwc.governance.execution_evidence_bundle import verify_execution_bundle
from cwc.governance.harness_freeze import DGC_ROLE, verify_harness_freeze_document
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes
from cwc.governance.pareto import PairedBaselineEvidence
from cwc.governance.physical_execution_cost_bundle import verify_physical_execution_cost_bundle

SCHEMA = "DGC_EXECUTED_P9_ANYTIME_AUTHORITY_V7"
CLAIM_SCOPE = "EXACT_FROZEN_PANEL_PLUS_ANYTIME_VALID_AVERAGE_CONDITIONAL_MEAN_V2"


class AnytimeP9AuthorityError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise AnytimeP9AuthorityError(f"{name} must be lowercase SHA-256")
    return text


def _policy_roles(harness: Mapping[str, object]) -> dict[str, str]:
    rows = harness.get("policy_role_bindings")
    if not isinstance(rows, list) or not all(isinstance(row, Mapping) for row in rows):
        raise AnytimeP9AuthorityError("frozen harness policy-role bindings missing")
    mapping = {str(row.get("role")): str(row.get("policy_id")) for row in rows}
    expected = {kind.value for kind in BaselineKind} | {DGC_ROLE}
    if set(mapping) != expected or len(set(mapping.values())) != len(expected):
        raise AnytimeP9AuthorityError("frozen harness policy-role bindings malformed")
    return mapping


def _task_digest(task_ids: tuple[str, ...]) -> str:
    return sha256_bytes(canonical_json_bytes(tuple(sorted(task_ids))))


def _micro_paired_evidence(
    *,
    execution_bundle,
    physical_cost_bundle,
    spec: DistributedEvalSpec,
    roles: Mapping[str, str],
    confirmatory_task_digest: str,
    execution_population_digest: str,
) -> tuple[PairedBaselineEvidence, ...]:
    results = {row.unit: row for row in execution_bundle.results}
    costs = physical_cost_bundle.cost_by_unit()
    expected_units = set(spec.units())
    if set(results) != expected_units or set(costs) != expected_units:
        raise AnytimeP9AuthorityError("P9 V7 requires exact complete metric and physical-cost populations")
    cap = float(physical_cost_bundle.per_unit_cost_cap_usd)
    if not math.isclose(cap, float(spec.max_cost_per_unit_usd), rel_tol=0.0, abs_tol=1e-12):
        raise AnytimeP9AuthorityError("physical-cost support differs from frozen distributed spec")
    paired_panel_digest = sha256_bytes(canonical_json_bytes({
        "confirmatory_task_manifest_digest": confirmatory_task_digest,
        "execution_population_digest": execution_population_digest,
        "replicates": spec.replicates,
        "sequence_order_rule": SEQUENCE_ORDER_RULE,
        "claim_target": CLAIM_TARGET,
    }))
    dgc_policy = roles[DGC_ROLE]
    evidence: list[PairedBaselineEvidence] = []
    for kind in BaselineKind:
        baseline_policy = roles[kind.value]
        cost_gain: list[float] = []
        quality_gain: list[float] = []
        regret_gain: list[float] = []
        for task_id in spec.task_ids:  # DistributedEvalSpec canonicalizes ascending task ids.
            for replicate in range(spec.replicates):
                b_unit = WorkUnitId(task_id, baseline_policy, replicate)
                d_unit = WorkUnitId(task_id, dgc_policy, replicate)
                baseline = results[b_unit]
                dgc = results[d_unit]
                cost_gain.append(float(costs[b_unit]) - float(costs[d_unit]))
                quality_gain.append(float(dgc.quality) - float(baseline.quality))
                regret_gain.append(float(baseline.catastrophic_regret) - float(dgc.catastrophic_regret))
        evidence.append(PairedBaselineEvidence(
            baseline_id=kind.value,
            paired_task_digest=paired_panel_digest,
            coverage=1.0,
            baseline_minus_dgc_cost=tuple(cost_gain),
            dgc_minus_baseline_quality=tuple(quality_gain),
            baseline_minus_dgc_catastrophic_regret=tuple(regret_gain),
            cost_gain_support=(-cap, cap),
            quality_gain_support=(-1.0, 1.0),
            catastrophic_gain_support=(-1.0, 1.0),
        ))
    return tuple(evidence)


@dataclass(frozen=True, slots=True)
class AnytimeP9Authority:
    family_id: str
    lineage_v2_authority_digest: str
    execution_authority_digest: str
    execution_population_digest: str
    execution_bundle_digest: str
    physical_cost_bundle_digest: str
    physical_cost_population_digest: str
    harness_freeze_digest: str
    confirmatory_task_manifest_digest: str
    statistical_plan_digest: str
    paired_panel_digest: str
    paired_evidence_population_digest: str
    paired_observations_per_baseline: int
    exact_panel_certificate: dict[str, object]
    exact_panel_certificate_digest: str
    exact_panel_supported: bool
    anytime_certificate: dict[str, object]
    anytime_certificate_digest: str
    anytime_average_conditional_mean_supported: bool
    anytime_method: str
    anytime_claim_target: str
    anytime_assumption_boundary: str
    sequence_order_rule: str
    legacy_task_aggregated_hoeffding_certificate_digest: str
    legacy_task_aggregated_hoeffding_supported: bool
    p9_supported_without_iid_assumption: bool
    generalization_evaluation_authorized: bool
    authority_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            **asdict(self),
            "claim_scope": CLAIM_SCOPE,
            "physical_cost_accounting_verified": True,
            "iid_assumption_required": False,
            "provider_request_independence_required": False,
            "legacy_statistics_promotion_authorized": False,
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
    # Reuse the mature V2 implementation only as a non-promoting lineage verifier.
    lineage = build_executed_p9_authority(
        confirmatory_execution_authority_path=Path(confirmatory_execution_authority_path),
        execution_bundle_root=Path(execution_bundle_root),
        physical_cost_bundle_root=Path(physical_cost_bundle_root),
        confirmatory_root_authority_path=Path(confirmatory_root_authority_path),
        harness_freeze_path=Path(harness_freeze_path),
        execution_manifest_freeze_path=Path(execution_manifest_freeze_path),
        materialization_reference_path=Path(materialization_reference_path),
        source_registry_path=Path(source_registry_path),
    )
    root_authority = verify_confirmatory_root_authority_document(Path(confirmatory_root_authority_path))
    harness = verify_harness_freeze_document(Path(harness_freeze_path))
    execution_bundle = verify_execution_bundle(
        Path(execution_bundle_root),
        confirmatory_root_authority_path=Path(confirmatory_root_authority_path),
    )
    physical = verify_physical_execution_cost_bundle(
        Path(physical_cost_bundle_root),
        confirmatory_execution_authority_path=Path(confirmatory_execution_authority_path),
        execution_bundle_root=Path(execution_bundle_root),
        confirmatory_root_authority_path=Path(confirmatory_root_authority_path),
    )
    spec_doc = root_authority.get("distributed_spec")
    if not isinstance(spec_doc, Mapping):
        raise AnytimeP9AuthorityError("frozen distributed spec missing")
    try:
        spec = DistributedEvalSpec(**dict(spec_doc))
    except (TypeError, ValueError) as exc:
        raise AnytimeP9AuthorityError("frozen distributed spec cannot be reconstructed") from exc
    if spec.digest != root_authority.get("distributed_spec_digest"):
        raise AnytimeP9AuthorityError("distributed spec digest mismatch")
    roles = _policy_roles(harness)
    if set(roles.values()) != set(spec.policy_ids):
        raise AnytimeP9AuthorityError("frozen semantic roles differ from execution population")
    confirmatory_digest = _sha(
        "confirmatory_task_manifest_digest", harness.get("confirmatory_task_manifest_digest")
    )
    if _task_digest(spec.task_ids) != confirmatory_digest:
        raise AnytimeP9AuthorityError("distributed tasks differ from frozen confirmatory panel")
    if lineage.confirmatory_task_manifest_digest != confirmatory_digest:
        raise AnytimeP9AuthorityError("lineage verifier and V7 task identities differ")
    if lineage.execution_bundle_digest != execution_bundle.bundle_digest:
        raise AnytimeP9AuthorityError("lineage verifier and V7 execution subjects differ")
    if lineage.physical_cost_bundle_digest != physical.bundle_digest:
        raise AnytimeP9AuthorityError("lineage verifier and V7 physical-cost subjects differ")

    paired = _micro_paired_evidence(
        execution_bundle=execution_bundle,
        physical_cost_bundle=physical,
        spec=spec,
        roles=roles,
        confirmatory_task_digest=confirmatory_digest,
        execution_population_digest=lineage.execution_population_digest,
    )
    qmargin = float(lineage.quality_noninferiority_margin)
    cmargin = float(lineage.catastrophic_noninferiority_margin)
    exact = certify_exact_finite_panel(
        paired,
        quality_noninferiority_margin=qmargin,
        catastrophic_noninferiority_margin=cmargin,
    )
    anytime = certify_multi_baseline_anytime_valid(
        paired,
        alpha=float(lineage.family_alpha),
        quality_noninferiority_margin=qmargin,
        catastrophic_noninferiority_margin=cmargin,
    )
    if not math.isclose(anytime.per_metric_alpha, float(lineage.per_metric_delta), rel_tol=0.0, abs_tol=1e-15):
        raise AnytimeP9AuthorityError("anytime-valid multiplicity differs from frozen V4 plan")

    paired_docs = tuple(asdict(row) for row in sorted(paired, key=lambda item: item.baseline_id))
    paired_digest = sha256_bytes(canonical_json_bytes(list(paired_docs)))
    exact_doc = asdict(exact)
    exact_digest = exact_certificate_digest(exact)
    anytime_doc = asdict(anytime)
    anytime_digest = sha256_bytes(canonical_json_bytes(anytime_doc))
    exact_supported = bool(exact.all_baselines_observed)
    anytime_supported = bool(anytime.all_baselines_certified)
    scientific_supported = exact_supported and anytime_supported
    payload = {
        "family_id": lineage.family_id,
        "lineage_v2_authority_digest": lineage.authority_digest,
        "execution_authority_digest": lineage.execution_authority_digest,
        "execution_population_digest": lineage.execution_population_digest,
        "execution_bundle_digest": lineage.execution_bundle_digest,
        "physical_cost_bundle_digest": lineage.physical_cost_bundle_digest,
        "physical_cost_population_digest": lineage.physical_cost_population_digest,
        "harness_freeze_digest": lineage.harness_freeze_digest,
        "confirmatory_task_manifest_digest": confirmatory_digest,
        "statistical_plan_digest": lineage.statistical_plan_digest,
        "paired_panel_digest": exact.paired_panel_digest,
        "paired_evidence_population_digest": paired_digest,
        "paired_observations_per_baseline": len(spec.task_ids) * spec.replicates,
        "exact_panel_certificate": exact_doc,
        "exact_panel_certificate_digest": exact_digest,
        "exact_panel_supported": exact_supported,
        "anytime_certificate": anytime_doc,
        "anytime_certificate_digest": anytime_digest,
        "anytime_average_conditional_mean_supported": anytime_supported,
        "anytime_method": METHOD,
        "anytime_claim_target": CLAIM_TARGET,
        "anytime_assumption_boundary": ASSUMPTION_BOUNDARY,
        "sequence_order_rule": SEQUENCE_ORDER_RULE,
        "legacy_task_aggregated_hoeffding_certificate_digest": lineage.p9_certificate_digest,
        "legacy_task_aggregated_hoeffding_supported": bool(lineage.p9_supported),
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
    if doc.get("claim_scope") != CLAIM_SCOPE:
        raise AnytimeP9AuthorityError("anytime P9 claim scope mismatch")
    if doc.get("iid_assumption_required") is not False or doc.get("provider_request_independence_required") is not False:
        raise AnytimeP9AuthorityError("anytime P9 incorrectly requires iid/provider independence")
    if doc.get("legacy_statistics_promotion_authorized") is not False:
        raise AnytimeP9AuthorityError("legacy statistics cannot authorize V7 promotion")
    if doc.get("physical_cost_accounting_verified") is not True or doc.get("product_promotion_authorized") is not False:
        raise AnytimeP9AuthorityError("anytime P9 promotion boundary malformed")
    keys = (
        "family_id", "lineage_v2_authority_digest", "execution_authority_digest",
        "execution_population_digest", "execution_bundle_digest", "physical_cost_bundle_digest",
        "physical_cost_population_digest", "harness_freeze_digest", "confirmatory_task_manifest_digest",
        "statistical_plan_digest", "paired_panel_digest", "paired_evidence_population_digest",
        "paired_observations_per_baseline", "exact_panel_certificate", "exact_panel_certificate_digest",
        "exact_panel_supported", "anytime_certificate", "anytime_certificate_digest",
        "anytime_average_conditional_mean_supported", "anytime_method", "anytime_claim_target",
        "anytime_assumption_boundary", "sequence_order_rule",
        "legacy_task_aggregated_hoeffding_certificate_digest", "legacy_task_aggregated_hoeffding_supported",
        "p9_supported_without_iid_assumption", "generalization_evaluation_authorized",
    )
    try:
        payload = {key: doc[key] for key in keys}
    except KeyError as exc:
        raise AnytimeP9AuthorityError("anytime P9 payload incomplete") from exc
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("authority_digest", doc.get("authority_digest")):
        raise AnytimeP9AuthorityError("anytime P9 authority digest mismatch")
    exact = doc.get("exact_panel_certificate")
    anytime = doc.get("anytime_certificate")
    if not isinstance(exact, dict) or not isinstance(anytime, dict):
        raise AnytimeP9AuthorityError("exact/anytime P9 certificates missing")
    if sha256_bytes(canonical_json_bytes(exact)) != _sha(
        "exact_panel_certificate_digest", doc.get("exact_panel_certificate_digest")
    ):
        raise AnytimeP9AuthorityError("exact P9 certificate digest mismatch")
    if sha256_bytes(canonical_json_bytes(anytime)) != _sha(
        "anytime_certificate_digest", doc.get("anytime_certificate_digest")
    ):
        raise AnytimeP9AuthorityError("anytime P9 certificate digest mismatch")
    if doc.get("anytime_method") != METHOD or doc.get("anytime_claim_target") != CLAIM_TARGET:
        raise AnytimeP9AuthorityError("anytime P9 theorem identity mismatch")
    if doc.get("anytime_assumption_boundary") != ASSUMPTION_BOUNDARY or doc.get("sequence_order_rule") != SEQUENCE_ORDER_RULE:
        raise AnytimeP9AuthorityError("anytime P9 assumption/order identity mismatch")
    derived_exact = exact.get("all_baselines_observed") is True
    derived_anytime = anytime.get("all_baselines_certified") is True
    if doc.get("exact_panel_supported") is not derived_exact:
        raise AnytimeP9AuthorityError("exact support flag is not certificate-derived")
    if doc.get("anytime_average_conditional_mean_supported") is not derived_anytime:
        raise AnytimeP9AuthorityError("anytime support flag is not certificate-derived")
    derived = derived_exact and derived_anytime
    if doc.get("p9_supported_without_iid_assumption") is not derived:
        raise AnytimeP9AuthorityError("P9 support must derive from exact + anytime-valid certificates")
    if doc.get("generalization_evaluation_authorized") is not derived:
        raise AnytimeP9AuthorityError("generalization evaluation must derive from exact + anytime-valid P9")
    if int(doc.get("paired_observations_per_baseline", 0)) <= 0:
        raise AnytimeP9AuthorityError("paired observation population must be non-empty")
    for field in (
        "lineage_v2_authority_digest", "execution_authority_digest", "execution_population_digest",
        "execution_bundle_digest", "physical_cost_bundle_digest", "physical_cost_population_digest",
        "harness_freeze_digest", "confirmatory_task_manifest_digest", "statistical_plan_digest",
        "paired_panel_digest", "paired_evidence_population_digest",
        "legacy_task_aggregated_hoeffding_certificate_digest",
    ):
        _sha(field, doc.get(field))
    return doc