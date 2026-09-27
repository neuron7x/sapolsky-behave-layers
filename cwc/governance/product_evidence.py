from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class ProductEvidenceStage(IntEnum):
    RESEARCH_HYPOTHESIS = 0
    EXPERIMENTALLY_SUPPORTED = 1
    REAL_WORKLOAD_SUPPORTED = 2
    INDEPENDENTLY_REPLICATED = 3
    PRODUCT_QUALIFIED = 4


@dataclass(frozen=True, slots=True)
class ProductEvidenceRecord:
    claim_frozen: bool
    metrics_frozen: bool
    baselines_frozen: bool
    harness_frozen: bool
    statistical_plan_frozen: bool
    synthetic_mechanism_supported: bool
    external_real_workload_supported: bool
    quality_noninferiority_supported: bool
    catastrophic_regret_noninferiority_supported: bool
    coverage_equivalence_supported: bool
    physical_cost_accounting_verified: bool
    net_cost_superiority_supported: bool
    generalization_supported: bool
    fault_tolerance_supported: bool
    independent_replication_supported: bool
    evidence_bundle_complete: bool
    production_provider_trace_supported: bool = False
    shadow_mode_qualified: bool = False
    bounded_canary_qualified: bool = False

    @property
    def p0_frozen(self) -> bool:
        return all((
            self.claim_frozen,
            self.metrics_frozen,
            self.baselines_frozen,
            self.harness_frozen,
            self.statistical_plan_frozen,
        ))

    @property
    def real_workload_core(self) -> bool:
        return all((
            self.p0_frozen,
            self.external_real_workload_supported,
            self.quality_noninferiority_supported,
            self.catastrophic_regret_noninferiority_supported,
            self.coverage_equivalence_supported,
            self.physical_cost_accounting_verified,
            self.net_cost_superiority_supported,
            self.fault_tolerance_supported,
        ))

    @property
    def product_qualified(self) -> bool:
        return all((
            self.real_workload_core,
            self.generalization_supported,
            self.independent_replication_supported,
            self.evidence_bundle_complete,
        ))

    @property
    def production_control_authorized(self) -> bool:
        return all((
            self.product_qualified,
            self.production_provider_trace_supported,
            self.shadow_mode_qualified,
            self.bounded_canary_qualified,
        ))

    @property
    def stage(self) -> ProductEvidenceStage:
        if self.product_qualified:
            return ProductEvidenceStage.PRODUCT_QUALIFIED
        if self.real_workload_core and self.independent_replication_supported:
            return ProductEvidenceStage.INDEPENDENTLY_REPLICATED
        if self.real_workload_core:
            return ProductEvidenceStage.REAL_WORKLOAD_SUPPORTED
        if self.p0_frozen and self.synthetic_mechanism_supported:
            return ProductEvidenceStage.EXPERIMENTALLY_SUPPORTED
        return ProductEvidenceStage.RESEARCH_HYPOTHESIS

    def missing_for_product_qualified(self) -> tuple[str, ...]:
        fields = (
            "claim_frozen",
            "metrics_frozen",
            "baselines_frozen",
            "harness_frozen",
            "statistical_plan_frozen",
            "external_real_workload_supported",
            "quality_noninferiority_supported",
            "catastrophic_regret_noninferiority_supported",
            "coverage_equivalence_supported",
            "physical_cost_accounting_verified",
            "net_cost_superiority_supported",
            "generalization_supported",
            "fault_tolerance_supported",
            "independent_replication_supported",
            "evidence_bundle_complete",
        )
        return tuple(name for name in fields if not getattr(self, name))


def require_stage(record: ProductEvidenceRecord, required: ProductEvidenceStage) -> None:
    if record.stage < required:
        missing = ",".join(record.missing_for_product_qualified())
        raise RuntimeError(
            f"product evidence stage {record.stage.name} < required {required.name}; missing={missing}"
        )
