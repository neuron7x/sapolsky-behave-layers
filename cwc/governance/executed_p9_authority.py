from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import fmean
from typing import Mapping

from cwc.governance.baseline_panel import BaselineKind
from cwc.governance.confirmatory_execution_authority import (
    verify_confirmatory_execution_authority_document,
)
from cwc.governance.confirmatory_root_authority import (
    REFERENCE_SCHEMA,
    REGISTRY_SCHEMA,
    _json as _root_json,
    _materialized_authority,
    verify_confirmatory_root_authority_document,
)
from cwc.governance.distributed_eval_control import DistributedEvalSpec
from cwc.governance.executed_p9 import ExecutedPairedBaselineEvidence, ExecutedP9Certificate, certify_executed_p9
from cwc.governance.execution_evidence_bundle import VerifiedExecutionBundle, verify_execution_bundle
from cwc.governance.execution_manifest_freeze import verify_execution_manifest_freeze_document
from cwc.governance.external_source_authority import promote_executed
from cwc.governance.harness_freeze import DGC_ROLE, verify_harness_freeze_document
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes
from cwc.governance.pareto import PairedBaselineEvidence
from cwc.governance.physical_execution_cost_bundle import (
    VerifiedPhysicalExecutionCostBundle,
    verify_physical_execution_cost_bundle,
)
from cwc.governance.product_statistical_plan import ProductStatisticalPlan

SCHEMA = "DGC_EXECUTED_P9_AUTHORITY_V2"
COST_MEASURE = "TOTAL_OPERATIONAL_USD_V1"


class ExecutedP9AuthorityError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise ExecutedP9AuthorityError(f"{name} must be lowercase SHA-256")
    return text


def _policy_roles(harness: Mapping[str, object]) -> dict[str, str]:
    rows = harness.get("policy_role_bindings")
    if not isinstance(rows, list) or not all(isinstance(row, Mapping) for row in rows):
        raise ExecutedP9AuthorityError("frozen harness policy-role bindings missing")
    mapping = {str(row.get("role")): str(row.get("policy_id")) for row in rows}
    expected = {kind.value for kind in BaselineKind} | {DGC_ROLE}
    if set(mapping) != expected or len(set(mapping.values())) != len(expected):
        raise ExecutedP9AuthorityError("frozen harness policy-role bindings malformed")
    return mapping


def _reconstruct_plan(execution_freeze: Mapping[str, object]) -> ProductStatisticalPlan:
    payload = execution_freeze.get("statistical_plan")
    if not isinstance(payload, Mapping):
        raise ExecutedP9AuthorityError("frozen statistical plan payload missing")
    try:
        plan = ProductStatisticalPlan(**dict(payload))
    except (TypeError, ValueError) as exc:
        raise ExecutedP9AuthorityError("frozen statistical plan cannot be reconstructed") from exc
    if plan.digest != _sha("statistical_plan_digest", execution_freeze.get("statistical_plan_digest")):
        raise ExecutedP9AuthorityError("statistical plan digest mismatch")
    if plan.baseline_count != 4 or plan.endpoint_count != 3:
        raise ExecutedP9AuthorityError("P9 requires preregistered four-baseline/three-endpoint plan")
    return plan


def _task_digest(task_ids: tuple[str, ...]) -> str:
    return sha256_bytes(canonical_json_bytes(tuple(sorted(task_ids))))


def _paired_evidence(
    *,
    execution_bundle: VerifiedExecutionBundle,
    physical_cost_bundle: VerifiedPhysicalExecutionCostBundle,
    spec: DistributedEvalSpec,
    roles: Mapping[str, str],
    confirmatory_task_digest: str,
    execution_population_digest: str,
) -> tuple[ExecutedPairedBaselineEvidence, ...]:
    by_task_policy: dict[tuple[str, str], list] = {}
    for row in execution_bundle.results:
        by_task_policy.setdefault((row.unit.task_id, row.unit.policy_id), []).append(row)
    physical_costs = physical_cost_bundle.cost_by_unit()
    expected_reps = tuple(range(spec.replicates))
    means: dict[tuple[str, str], tuple[float, float, float]] = {}
    for task in spec.task_ids:
        for policy in spec.policy_ids:
            rows = sorted(by_task_policy.get((task, policy), []), key=lambda item: item.unit.replicate)
            if tuple(item.unit.replicate for item in rows) != expected_reps:
                raise ExecutedP9AuthorityError("P9 requires exact frozen replicate population for every task/policy")
            try:
                physical = [physical_costs[item.unit] for item in rows]
            except KeyError as exc:
                raise ExecutedP9AuthorityError("P9 physical-cost population is incomplete") from exc
            means[(task, policy)] = (
                fmean(physical),
                fmean(item.quality for item in rows),
                fmean(item.catastrophic_regret for item in rows),
            )

    dgc_policy = roles[DGC_ROLE]
    cost_bound = float(physical_cost_bundle.per_unit_cost_cap_usd)
    if not math.isclose(cost_bound, float(spec.max_cost_per_unit_usd), rel_tol=0.0, abs_tol=1e-12):
        raise ExecutedP9AuthorityError("P9 physical-cost support differs from preregistered cost cap")
    evidence_rows: list[ExecutedPairedBaselineEvidence] = []
    for kind in BaselineKind:
        role = kind.value
        baseline_policy = roles[role]
        cost_gain: list[float] = []
        quality_gain: list[float] = []
        catastrophic_gain: list[float] = []
        for task in spec.task_ids:
            baseline_cost, baseline_quality, baseline_regret = means[(task, baseline_policy)]
            dgc_cost, dgc_quality, dgc_regret = means[(task, dgc_policy)]
            cost_gain.append(baseline_cost - dgc_cost)
            quality_gain.append(dgc_quality - baseline_quality)
            catastrophic_gain.append(baseline_regret - dgc_regret)
        paired = PairedBaselineEvidence(
            baseline_id=role,
            paired_task_digest=confirmatory_task_digest,
            coverage=1.0,
            baseline_minus_dgc_cost=tuple(cost_gain),
            dgc_minus_baseline_quality=tuple(quality_gain),
            baseline_minus_dgc_catastrophic_regret=tuple(catastrophic_gain),
            cost_gain_support=(-cost_bound, cost_bound),
            quality_gain_support=(-1.0, 1.0),
            catastrophic_gain_support=(-1.0, 1.0),
        )
        evidence_rows.append(ExecutedPairedBaselineEvidence(
            execution_population_digest=execution_population_digest,
            evidence=paired,
        ))
    return tuple(evidence_rows)


@dataclass(frozen=True, slots=True)
class ExecutedP9Authority:
    family_id: str
    execution_authority_digest: str
    executed_source_authority_digest: str
    execution_population_digest: str
    execution_bundle_digest: str
    metric_population_digest: str
    physical_cost_bundle_digest: str
    physical_cost_population_digest: str
    physical_cost_accounting_verified: bool
    cost_measure: str
    harness_freeze_digest: str
    confirmatory_task_manifest_digest: str
    statistical_plan_digest: str
    family_alpha: float
    per_metric_delta: float
    quality_noninferiority_margin: float
    catastrophic_noninferiority_margin: float
    paired_evidence_population_digest: str
    paired_evidence: tuple[dict[str, object], ...]
    p9_certificate: dict[str, object]
    p9_certificate_digest: str
    p9_supported: bool
    net_cost_superiority_supported: bool
    authority_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": SCHEMA,
            "family_id": self.family_id,
            "execution_authority_digest": self.execution_authority_digest,
            "executed_source_authority_digest": self.executed_source_authority_digest,
            "execution_population_digest": self.execution_population_digest,
            "execution_bundle_digest": self.execution_bundle_digest,
            "metric_population_digest": self.metric_population_digest,
            "physical_cost_bundle_digest": self.physical_cost_bundle_digest,
            "physical_cost_population_digest": self.physical_cost_population_digest,
            "physical_cost_accounting_verified": self.physical_cost_accounting_verified,
            "cost_measure": self.cost_measure,
            "harness_freeze_digest": self.harness_freeze_digest,
            "confirmatory_task_manifest_digest": self.confirmatory_task_manifest_digest,
            "statistical_plan_digest": self.statistical_plan_digest,
            "family_alpha": self.family_alpha,
            "per_metric_delta": self.per_metric_delta,
            "quality_noninferiority_margin": self.quality_noninferiority_margin,
            "catastrophic_noninferiority_margin": self.catastrophic_noninferiority_margin,
            "paired_evidence_population_digest": self.paired_evidence_population_digest,
            "paired_evidence": list(self.paired_evidence),
            "p9_certificate": self.p9_certificate,
            "p9_certificate_digest": self.p9_certificate_digest,
            "p9_supported": self.p9_supported,
            "net_cost_superiority_supported": self.net_cost_superiority_supported,
            "authority_digest": self.authority_digest,
            "generalization_authorized": self.p9_supported,
            "product_promotion_authorized": False,
        }


def build_executed_p9_authority(
    *,
    confirmatory_execution_authority_path: Path,
    execution_bundle_root: Path,
    physical_cost_bundle_root: Path,
    confirmatory_root_authority_path: Path,
    harness_freeze_path: Path,
    execution_manifest_freeze_path: Path,
    materialization_reference_path: Path,
    source_registry_path: Path,
) -> ExecutedP9Authority:
    execution_authority = verify_confirmatory_execution_authority_document(
        Path(confirmatory_execution_authority_path)
    )
    root_authority = verify_confirmatory_root_authority_document(Path(confirmatory_root_authority_path))
    harness = verify_harness_freeze_document(Path(harness_freeze_path))
    execution_freeze = verify_execution_manifest_freeze_document(Path(execution_manifest_freeze_path))
    execution_bundle = verify_execution_bundle(
        Path(execution_bundle_root),
        confirmatory_root_authority_path=Path(confirmatory_root_authority_path),
    )
    physical_cost_bundle = verify_physical_execution_cost_bundle(
        Path(physical_cost_bundle_root),
        confirmatory_execution_authority_path=Path(confirmatory_execution_authority_path),
        execution_bundle_root=Path(execution_bundle_root),
        confirmatory_root_authority_path=Path(confirmatory_root_authority_path),
    )
    if execution_authority.get("root_authority_digest") != root_authority.get("authority_digest"):
        raise ExecutedP9AuthorityError("P9 execution/root authority lineage mismatch")
    if execution_authority.get("execution_bundle_digest") != execution_bundle.bundle_digest:
        raise ExecutedP9AuthorityError("P9 execution bundle differs from EXECUTED authority subject")
    metric_digest = sha256_bytes(canonical_json_bytes([
        (row.unit.stable_id, row.quality, row.catastrophic_regret, row.actual_cost_usd)
        for row in sorted(execution_bundle.results, key=lambda item: item.unit)
    ]))
    if execution_authority.get("metric_population_digest") != metric_digest:
        raise ExecutedP9AuthorityError("P9 quality/regret population differs from EXECUTED authority")
    if physical_cost_bundle.execution_population_digest != execution_authority.get("execution_population_digest"):
        raise ExecutedP9AuthorityError("P9 physical costs belong to a different execution population")
    if physical_cost_bundle.execution_bundle_digest != execution_bundle.bundle_digest:
        raise ExecutedP9AuthorityError("P9 physical costs belong to a different execution subject")
    if harness.get("family_id") != execution_authority.get("family_id") or execution_freeze.get("family_id") != harness.get("family_id"):
        raise ExecutedP9AuthorityError("P9 family lineage mismatch")

    spec_doc = root_authority.get("distributed_spec")
    if not isinstance(spec_doc, Mapping):
        raise ExecutedP9AuthorityError("frozen distributed spec missing")
    try:
        spec = DistributedEvalSpec(**dict(spec_doc))
    except (TypeError, ValueError) as exc:
        raise ExecutedP9AuthorityError("frozen distributed spec cannot be reconstructed") from exc
    if spec.digest != root_authority.get("distributed_spec_digest"):
        raise ExecutedP9AuthorityError("P9 distributed spec digest mismatch")
    roles = _policy_roles(harness)
    if set(roles.values()) != set(spec.policy_ids):
        raise ExecutedP9AuthorityError("P9 policy roles differ from frozen distributed execution population")
    confirmatory_digest = _sha(
        "confirmatory_task_manifest_digest", harness.get("confirmatory_task_manifest_digest")
    )
    if _task_digest(spec.task_ids) != confirmatory_digest:
        raise ExecutedP9AuthorityError("P9 distributed task set differs from frozen held-out task manifest")

    plan = _reconstruct_plan(execution_freeze)
    family_alpha = plan.familywise_alpha / plan.family_count
    evidence_rows = _paired_evidence(
        execution_bundle=execution_bundle,
        physical_cost_bundle=physical_cost_bundle,
        spec=spec,
        roles=roles,
        confirmatory_task_digest=confirmatory_digest,
        execution_population_digest=_sha(
            "execution_population_digest", execution_authority.get("execution_population_digest")
        ),
    )

    reference = _root_json(Path(materialization_reference_path), REFERENCE_SCHEMA)
    registry = _root_json(Path(source_registry_path), REGISTRY_SCHEMA)
    materialized = _materialized_authority(
        reference=reference,
        registry=registry,
        family_id=str(execution_authority["family_id"]),
    )
    executed = promote_executed(
        materialized,
        execution_population_digest=str(execution_authority["execution_population_digest"]),
    )
    if executed.digest != execution_authority.get("executed_source_authority_digest"):
        raise ExecutedP9AuthorityError("P9 cannot reconstruct EXECUTED source authority")

    try:
        certificate: ExecutedP9Certificate = certify_executed_p9(
            executed,
            evidence_rows,
            alpha=family_alpha,
            quality_noninferiority_margin=plan.quality_noninferiority_margin,
            catastrophic_noninferiority_margin=plan.catastrophic_regret_noninferiority_margin,
        )
    except (TypeError, ValueError, RuntimeError) as exc:
        raise ExecutedP9AuthorityError("executed P9 certification failed") from exc
    if certificate.pareto.paired_task_digest != confirmatory_digest:
        raise ExecutedP9AuthorityError("P9 certificate lost held-out task identity")
    if not math.isclose(
        certificate.pareto.per_metric_delta,
        plan.per_claim_alpha,
        rel_tol=0.0,
        abs_tol=1e-15,
    ):
        raise ExecutedP9AuthorityError("P9 multiplicity allocation differs from preregistered per-claim alpha")

    paired_docs = tuple(asdict(row) for row in sorted(evidence_rows, key=lambda row: row.evidence.baseline_id))
    paired_digest = sha256_bytes(canonical_json_bytes(list(paired_docs)))
    certificate_doc = asdict(certificate)
    supported = bool(certificate.pareto.all_baselines_certified)
    payload = {
        "family_id": str(execution_authority["family_id"]),
        "execution_authority_digest": _sha("execution authority_digest", execution_authority.get("authority_digest")),
        "executed_source_authority_digest": executed.digest,
        "execution_population_digest": str(execution_authority["execution_population_digest"]),
        "execution_bundle_digest": execution_bundle.bundle_digest,
        "metric_population_digest": str(execution_authority["metric_population_digest"]),
        "physical_cost_bundle_digest": physical_cost_bundle.bundle_digest,
        "physical_cost_population_digest": physical_cost_bundle.physical_cost_population_digest,
        "physical_cost_accounting_verified": True,
        "cost_measure": COST_MEASURE,
        "harness_freeze_digest": _sha("harness_freeze_digest", harness.get("harness_freeze_digest")),
        "confirmatory_task_manifest_digest": confirmatory_digest,
        "statistical_plan_digest": plan.digest,
        "family_alpha": family_alpha,
        "per_metric_delta": certificate.pareto.per_metric_delta,
        "quality_noninferiority_margin": plan.quality_noninferiority_margin,
        "catastrophic_noninferiority_margin": plan.catastrophic_regret_noninferiority_margin,
        "paired_evidence_population_digest": paired_digest,
        "paired_evidence": list(paired_docs),
        "p9_certificate": certificate_doc,
        "p9_certificate_digest": certificate.certificate_digest,
        "p9_supported": supported,
        "net_cost_superiority_supported": supported,
    }
    return ExecutedP9Authority(
        family_id=payload["family_id"],
        execution_authority_digest=payload["execution_authority_digest"],
        executed_source_authority_digest=payload["executed_source_authority_digest"],
        execution_population_digest=payload["execution_population_digest"],
        execution_bundle_digest=payload["execution_bundle_digest"],
        metric_population_digest=payload["metric_population_digest"],
        physical_cost_bundle_digest=payload["physical_cost_bundle_digest"],
        physical_cost_population_digest=payload["physical_cost_population_digest"],
        physical_cost_accounting_verified=True,
        cost_measure=COST_MEASURE,
        harness_freeze_digest=payload["harness_freeze_digest"],
        confirmatory_task_manifest_digest=payload["confirmatory_task_manifest_digest"],
        statistical_plan_digest=payload["statistical_plan_digest"],
        family_alpha=family_alpha,
        per_metric_delta=certificate.pareto.per_metric_delta,
        quality_noninferiority_margin=plan.quality_noninferiority_margin,
        catastrophic_noninferiority_margin=plan.catastrophic_regret_noninferiority_margin,
        paired_evidence_population_digest=paired_digest,
        paired_evidence=paired_docs,
        p9_certificate=certificate_doc,
        p9_certificate_digest=certificate.certificate_digest,
        p9_supported=supported,
        net_cost_superiority_supported=supported,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_executed_p9_authority_document(path: Path) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise ExecutedP9AuthorityError("P9 authority must be a regular file")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExecutedP9AuthorityError("invalid P9 authority JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise ExecutedP9AuthorityError("unexpected P9 authority schema")
    if doc.get("product_promotion_authorized") is not False:
        raise ExecutedP9AuthorityError("P9 authority cannot authorize product promotion")
    if doc.get("generalization_authorized") is not bool(doc.get("p9_supported")):
        raise ExecutedP9AuthorityError("P9 generalization authority must derive from P9 support")
    if doc.get("physical_cost_accounting_verified") is not True:
        raise ExecutedP9AuthorityError("P9 requires complete source-bound physical cost accounting")
    if doc.get("cost_measure") != COST_MEASURE:
        raise ExecutedP9AuthorityError("P9 cost measure is not all-in total operational USD")
    if doc.get("net_cost_superiority_supported") is not bool(doc.get("p9_supported")):
        raise ExecutedP9AuthorityError("net cost superiority must derive from physically costed P9 support")

    payload_keys = (
        "family_id", "execution_authority_digest", "executed_source_authority_digest",
        "execution_population_digest", "execution_bundle_digest", "metric_population_digest",
        "physical_cost_bundle_digest", "physical_cost_population_digest",
        "physical_cost_accounting_verified", "cost_measure",
        "harness_freeze_digest", "confirmatory_task_manifest_digest", "statistical_plan_digest",
        "family_alpha", "per_metric_delta", "quality_noninferiority_margin",
        "catastrophic_noninferiority_margin", "paired_evidence_population_digest",
        "paired_evidence", "p9_certificate", "p9_certificate_digest", "p9_supported",
        "net_cost_superiority_supported",
    )
    try:
        payload = {key: doc[key] for key in payload_keys}
    except KeyError as exc:
        raise ExecutedP9AuthorityError("P9 authority payload incomplete") from exc
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("authority_digest", doc.get("authority_digest")):
        raise ExecutedP9AuthorityError("P9 authority digest mismatch")
    for name in (
        "execution_authority_digest", "executed_source_authority_digest", "execution_population_digest",
        "execution_bundle_digest", "metric_population_digest", "physical_cost_bundle_digest",
        "physical_cost_population_digest", "harness_freeze_digest", "confirmatory_task_manifest_digest",
        "statistical_plan_digest", "paired_evidence_population_digest", "p9_certificate_digest",
    ):
        _sha(name, doc.get(name))
    evidence = doc.get("paired_evidence")
    if not isinstance(evidence, list) or len(evidence) != 4:
        raise ExecutedP9AuthorityError("P9 authority must bind exactly four baseline evidence rows")
    if sha256_bytes(canonical_json_bytes(evidence)) != doc.get("paired_evidence_population_digest"):
        raise ExecutedP9AuthorityError("P9 paired evidence population digest mismatch")
    cert = doc.get("p9_certificate")
    if not isinstance(cert, Mapping) or cert.get("certificate_digest") != doc.get("p9_certificate_digest"):
        raise ExecutedP9AuthorityError("P9 certificate digest binding mismatch")
    pareto = cert.get("pareto")
    if not isinstance(pareto, Mapping):
        raise ExecutedP9AuthorityError("P9 Pareto certificate missing")
    if pareto.get("paired_task_digest") != doc.get("confirmatory_task_manifest_digest"):
        raise ExecutedP9AuthorityError("P9 certificate task identity mismatch")
    if bool(pareto.get("all_baselines_certified")) is not bool(doc.get("p9_supported")):
        raise ExecutedP9AuthorityError("P9 support flag does not derive from certificate")
    if not math.isclose(float(pareto.get("per_metric_delta", -1)), float(doc.get("per_metric_delta", -2)), rel_tol=0.0, abs_tol=1e-15):
        raise ExecutedP9AuthorityError("P9 per-metric delta mismatch")
    return doc
