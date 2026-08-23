from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.baseline_panel import BaselineKind
from cwc.governance.confirmatory_execution_authority import verify_confirmatory_execution_authority_document
from cwc.governance.confirmatory_root_authority import verify_confirmatory_root_authority_document
from cwc.governance.distributed_eval_control import DistributedEvalSpec, WorkUnitId
from cwc.governance.empirical_bernstein_pareto import certify_multi_baseline_empirical_bernstein
from cwc.governance.executed_p9_authority import build_executed_p9_authority
from cwc.governance.execution_evidence_bundle import verify_execution_bundle
from cwc.governance.execution_manifest_freeze import verify_execution_manifest_freeze_document
from cwc.governance.harness_freeze import DGC_ROLE, verify_harness_freeze_document
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes
from cwc.governance.paired_randomness_protocol import verify_paired_randomness_protocol
from cwc.governance.pareto import PairedBaselineEvidence
from cwc.governance.physical_execution_cost_bundle import verify_physical_execution_cost_bundle
from cwc.governance.product_statistical_plan import ProductStatisticalPlan

SCHEMA = "DGC_EXECUTED_P9_FINITE_PANEL_AUTHORITY_V3"
ESTIMAND = "FROZEN_FINITE_TASK_PANEL_EQUAL_TASK_EQUAL_REPLICATE_WEIGHT_V1"
INFERENCE = "EMPIRICAL_BERNSTEIN_ONE_SIDED_LOWER_V1"


class FinitePanelP9Error(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise FinitePanelP9Error(f"{name} must be lowercase SHA-256")
    return text


def _task_digest(task_ids: tuple[str, ...]) -> str:
    return sha256_bytes(canonical_json_bytes(tuple(sorted(task_ids))))


def _roles(harness: Mapping[str, object]) -> dict[str, str]:
    rows = harness.get("policy_role_bindings")
    if not isinstance(rows, list) or not all(isinstance(row, Mapping) for row in rows):
        raise FinitePanelP9Error("frozen harness semantic role bindings missing")
    mapping = {str(row.get("role")): str(row.get("policy_id")) for row in rows}
    expected = {kind.value for kind in BaselineKind} | {DGC_ROLE}
    if set(mapping) != expected or len(set(mapping.values())) != len(expected):
        raise FinitePanelP9Error("frozen harness semantic role population malformed")
    return mapping


def _plan(execution_freeze: Mapping[str, object]) -> ProductStatisticalPlan:
    raw = execution_freeze.get("statistical_plan")
    if not isinstance(raw, Mapping):
        raise FinitePanelP9Error("frozen statistical plan payload missing")
    try:
        plan = ProductStatisticalPlan(**dict(raw))
    except (TypeError, ValueError) as exc:
        raise FinitePanelP9Error("frozen statistical plan cannot be reconstructed") from exc
    if plan.digest != execution_freeze.get("statistical_plan_digest"):
        raise FinitePanelP9Error("frozen statistical plan digest mismatch")
    return plan


def _flat_paired_evidence(
    *,
    execution_bundle,
    physical_cost_bundle,
    spec: DistributedEvalSpec,
    roles: Mapping[str, str],
    paired_panel_digest: str,
) -> tuple[PairedBaselineEvidence, ...]:
    results = {row.unit: row for row in execution_bundle.results}
    costs = physical_cost_bundle.cost_by_unit()
    if set(results) != set(spec.units()) or set(costs) != set(spec.units()):
        raise FinitePanelP9Error("finite-panel inference requires exact complete metric and physical-cost populations")
    dgc_policy = roles[DGC_ROLE]
    cap = float(physical_cost_bundle.per_unit_cost_cap_usd)
    if not math.isclose(cap, float(spec.max_cost_per_unit_usd), rel_tol=0.0, abs_tol=1e-12):
        raise FinitePanelP9Error("physical-cost support differs from frozen distributed spec")

    evidence: list[PairedBaselineEvidence] = []
    for kind in BaselineKind:
        baseline_policy = roles[kind.value]
        cost_gain: list[float] = []
        quality_gain: list[float] = []
        regret_gain: list[float] = []
        for task_id in spec.task_ids:
            for replicate in range(spec.replicates):
                baseline_unit = WorkUnitId(task_id, baseline_policy, replicate)
                dgc_unit = WorkUnitId(task_id, dgc_policy, replicate)
                baseline = results[baseline_unit]
                dgc = results[dgc_unit]
                cost_gain.append(float(costs[baseline_unit]) - float(costs[dgc_unit]))
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
class FinitePanelP9Authority:
    family_id: str
    legacy_v2_authority_digest: str
    execution_authority_digest: str
    execution_population_digest: str
    execution_bundle_digest: str
    physical_cost_bundle_digest: str
    physical_cost_population_digest: str
    harness_freeze_digest: str
    confirmatory_task_manifest_digest: str
    statistical_plan_digest: str
    replicates: int
    paired_observations_per_baseline: int
    estimand: str
    inference_method: str
    randomness_protocol: str
    randomness_schedule_digest: str
    randomness_independence_assumption: str
    randomness_assumption_verified: bool
    family_alpha: float
    per_metric_delta: float
    paired_panel_digest: str
    paired_evidence_population_digest: str
    paired_evidence: tuple[dict[str, object], ...]
    p9_certificate: dict[str, object]
    p9_certificate_digest: str
    p9_supported_under_protocol_assumption: bool
    net_cost_superiority_supported_under_protocol_assumption: bool
    authority_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            **asdict(self),
            "physical_cost_accounting_verified": True,
            "statistical_scope": "CONDITIONAL_ON_DECLARED_RANDOMNESS_ASSUMPTION",
            "generalization_authorized": self.p9_supported_under_protocol_assumption,
            "product_promotion_authorized": False,
        }


def build_finite_panel_p9_authority(
    *,
    confirmatory_execution_authority_path: Path,
    execution_bundle_root: Path,
    physical_cost_bundle_root: Path,
    confirmatory_root_authority_path: Path,
    harness_freeze_path: Path,
    execution_manifest_freeze_path: Path,
    materialization_reference_path: Path,
    source_registry_path: Path,
) -> FinitePanelP9Authority:
    # Legacy V2 is retained as an independently reproducible compatibility component.
    # V3 does not inherit its task-aggregated statistical conclusion; it only reuses
    # the already hardened lineage/source/physical-cost checks.
    legacy = build_executed_p9_authority(
        confirmatory_execution_authority_path=Path(confirmatory_execution_authority_path),
        execution_bundle_root=Path(execution_bundle_root),
        physical_cost_bundle_root=Path(physical_cost_bundle_root),
        confirmatory_root_authority_path=Path(confirmatory_root_authority_path),
        harness_freeze_path=Path(harness_freeze_path),
        execution_manifest_freeze_path=Path(execution_manifest_freeze_path),
        materialization_reference_path=Path(materialization_reference_path),
        source_registry_path=Path(source_registry_path),
    )
    execution_authority = verify_confirmatory_execution_authority_document(Path(confirmatory_execution_authority_path))
    root_authority = verify_confirmatory_root_authority_document(Path(confirmatory_root_authority_path))
    harness = verify_harness_freeze_document(Path(harness_freeze_path))
    execution_freeze = verify_execution_manifest_freeze_document(Path(execution_manifest_freeze_path))
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
    if legacy.execution_authority_digest != execution_authority.get("authority_digest"):
        raise FinitePanelP9Error("legacy V2 and V3 execution lineage differ")
    if legacy.execution_bundle_digest != execution_bundle.bundle_digest:
        raise FinitePanelP9Error("legacy V2 and V3 execution subjects differ")
    if legacy.physical_cost_bundle_digest != physical.bundle_digest:
        raise FinitePanelP9Error("legacy V2 and V3 physical-cost subjects differ")

    root_doc = root_authority.get("root")
    spec_doc = root_authority.get("distributed_spec")
    if not isinstance(root_doc, Mapping) or not isinstance(spec_doc, Mapping):
        raise FinitePanelP9Error("confirmatory root/spec payload missing")
    try:
        spec = DistributedEvalSpec(**dict(spec_doc))
    except (TypeError, ValueError) as exc:
        raise FinitePanelP9Error("distributed spec cannot be reconstructed") from exc
    if spec.digest != root_authority.get("distributed_spec_digest"):
        raise FinitePanelP9Error("distributed spec digest mismatch")
    roles = _roles(harness)
    if set(roles.values()) != set(spec.policy_ids):
        raise FinitePanelP9Error("frozen semantic roles differ from execution population")
    task_digest = _sha("confirmatory_task_manifest_digest", harness.get("confirmatory_task_manifest_digest"))
    if _task_digest(spec.task_ids) != task_digest:
        raise FinitePanelP9Error("distributed tasks differ from frozen confirmatory panel")

    root_digest = _sha("root_digest", root_doc.get("root_digest"))
    randomness = verify_paired_randomness_protocol(execution_bundle, root_digest=root_digest)
    paired_panel_digest = sha256_bytes(canonical_json_bytes({
        "task_manifest_digest": task_digest,
        "replicates": spec.replicates,
        "randomness_protocol": randomness.protocol,
        "randomness_schedule_digest": randomness.schedule_digest,
        "estimand": ESTIMAND,
    }))
    paired = _flat_paired_evidence(
        execution_bundle=execution_bundle,
        physical_cost_bundle=physical,
        spec=spec,
        roles=roles,
        paired_panel_digest=paired_panel_digest,
    )
    plan = _plan(execution_freeze)
    family_alpha = plan.familywise_alpha / plan.family_count
    try:
        certificate = certify_multi_baseline_empirical_bernstein(
            paired,
            alpha=family_alpha,
            quality_noninferiority_margin=plan.quality_noninferiority_margin,
            catastrophic_noninferiority_margin=plan.catastrophic_regret_noninferiority_margin,
        )
    except (TypeError, ValueError) as exc:
        raise FinitePanelP9Error("finite-panel empirical-Bernstein certification failed") from exc
    if not math.isclose(certificate.per_metric_delta, plan.per_claim_alpha, rel_tol=0.0, abs_tol=1e-15):
        raise FinitePanelP9Error("finite-panel multiplicity allocation differs from frozen statistical plan")

    paired_docs = tuple(asdict(row) for row in sorted(paired, key=lambda item: item.baseline_id))
    paired_digest = sha256_bytes(canonical_json_bytes(list(paired_docs)))
    certificate_doc = asdict(certificate)
    certificate_digest = sha256_bytes(canonical_json_bytes(certificate_doc))
    supported = bool(certificate.all_baselines_certified)
    payload = {
        "family_id": str(execution_authority["family_id"]),
        "legacy_v2_authority_digest": legacy.authority_digest,
        "execution_authority_digest": _sha("execution authority_digest", execution_authority.get("authority_digest")),
        "execution_population_digest": _sha("execution_population_digest", execution_authority.get("execution_population_digest")),
        "execution_bundle_digest": execution_bundle.bundle_digest,
        "physical_cost_bundle_digest": physical.bundle_digest,
        "physical_cost_population_digest": physical.physical_cost_population_digest,
        "harness_freeze_digest": _sha("harness_freeze_digest", harness.get("harness_freeze_digest")),
        "confirmatory_task_manifest_digest": task_digest,
        "statistical_plan_digest": plan.digest,
        "replicates": spec.replicates,
        "paired_observations_per_baseline": len(spec.task_ids) * spec.replicates,
        "estimand": ESTIMAND,
        "inference_method": INFERENCE,
        "randomness_protocol": randomness.protocol,
        "randomness_schedule_digest": randomness.schedule_digest,
        "randomness_independence_assumption": randomness.independence_assumption,
        "randomness_assumption_verified": randomness.assumption_verified,
        "family_alpha": family_alpha,
        "per_metric_delta": certificate.per_metric_delta,
        "paired_panel_digest": paired_panel_digest,
        "paired_evidence_population_digest": paired_digest,
        "paired_evidence": list(paired_docs),
        "p9_certificate": certificate_doc,
        "p9_certificate_digest": certificate_digest,
        "p9_supported_under_protocol_assumption": supported,
        "net_cost_superiority_supported_under_protocol_assumption": supported,
    }
    return FinitePanelP9Authority(
        **payload,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_finite_panel_p9_authority_document(path: Path) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise FinitePanelP9Error("finite-panel P9 authority must be a regular file")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FinitePanelP9Error("invalid finite-panel P9 authority JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise FinitePanelP9Error("unexpected finite-panel P9 schema")
    if doc.get("physical_cost_accounting_verified") is not True or doc.get("product_promotion_authorized") is not False:
        raise FinitePanelP9Error("finite-panel P9 claim boundary malformed")
    if doc.get("statistical_scope") != "CONDITIONAL_ON_DECLARED_RANDOMNESS_ASSUMPTION":
        raise FinitePanelP9Error("finite-panel statistical assumption boundary missing")
    keys = (
        "family_id", "legacy_v2_authority_digest", "execution_authority_digest",
        "execution_population_digest", "execution_bundle_digest", "physical_cost_bundle_digest",
        "physical_cost_population_digest", "harness_freeze_digest", "confirmatory_task_manifest_digest",
        "statistical_plan_digest", "replicates", "paired_observations_per_baseline", "estimand",
        "inference_method", "randomness_protocol", "randomness_schedule_digest",
        "randomness_independence_assumption", "randomness_assumption_verified", "family_alpha",
        "per_metric_delta", "paired_panel_digest", "paired_evidence_population_digest",
        "paired_evidence", "p9_certificate", "p9_certificate_digest",
        "p9_supported_under_protocol_assumption", "net_cost_superiority_supported_under_protocol_assumption",
    )
    try:
        payload = {key: doc[key] for key in keys}
    except KeyError as exc:
        raise FinitePanelP9Error("finite-panel P9 payload incomplete") from exc
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("authority_digest", doc.get("authority_digest")):
        raise FinitePanelP9Error("finite-panel P9 authority digest mismatch")
    if doc.get("estimand") != ESTIMAND or doc.get("inference_method") != INFERENCE:
        raise FinitePanelP9Error("finite-panel estimand/inference identity mismatch")
    if int(doc.get("replicates", 0)) <= 0 or int(doc.get("paired_observations_per_baseline", 0)) < 2:
        raise FinitePanelP9Error("finite-panel P9 observation population invalid")
    cert = doc.get("p9_certificate")
    if not isinstance(cert, Mapping):
        raise FinitePanelP9Error("finite-panel P9 certificate missing")
    if sha256_bytes(canonical_json_bytes(dict(cert))) != _sha("p9_certificate_digest", doc.get("p9_certificate_digest")):
        raise FinitePanelP9Error("finite-panel P9 certificate digest mismatch")
    supported = cert.get("all_baselines_certified") is True
    if doc.get("p9_supported_under_protocol_assumption") is not supported:
        raise FinitePanelP9Error("finite-panel support flag does not derive from statistical certificate")
    if doc.get("net_cost_superiority_supported_under_protocol_assumption") is not supported:
        raise FinitePanelP9Error("finite-panel net-cost flag does not derive from same certificate")
    if doc.get("generalization_authorized") is not supported:
        raise FinitePanelP9Error("generalization authorization does not derive from finite-panel P9 support")
    return doc
