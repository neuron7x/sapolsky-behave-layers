import pytest

from cwc.governance.product_evidence import (
    ProductEvidenceRecord,
    ProductEvidenceStage,
    require_stage,
)


def _record(**overrides) -> ProductEvidenceRecord:
    data = dict(
        claim_frozen=True,
        metrics_frozen=True,
        baselines_frozen=True,
        harness_frozen=True,
        statistical_plan_frozen=True,
        synthetic_mechanism_supported=True,
        external_real_workload_supported=False,
        quality_noninferiority_supported=False,
        catastrophic_regret_noninferiority_supported=False,
        coverage_equivalence_supported=False,
        physical_cost_accounting_verified=False,
        net_cost_superiority_supported=False,
        generalization_supported=False,
        fault_tolerance_supported=True,
        independent_replication_supported=False,
        evidence_bundle_complete=False,
    )
    data.update(overrides)
    return ProductEvidenceRecord(**data)


def test_internal_synthetic_support_promotes_only_to_experimental():
    assert _record().stage is ProductEvidenceStage.EXPERIMENTALLY_SUPPORTED


def test_real_workload_stage_requires_full_core_chain():
    rec = _record(
        external_real_workload_supported=True,
        quality_noninferiority_supported=True,
        catastrophic_regret_noninferiority_supported=True,
        coverage_equivalence_supported=True,
        physical_cost_accounting_verified=True,
        net_cost_superiority_supported=True,
    )
    assert rec.stage is ProductEvidenceStage.REAL_WORKLOAD_SUPPORTED


def test_independent_replication_is_distinct_stage():
    rec = _record(
        external_real_workload_supported=True,
        quality_noninferiority_supported=True,
        catastrophic_regret_noninferiority_supported=True,
        coverage_equivalence_supported=True,
        physical_cost_accounting_verified=True,
        net_cost_superiority_supported=True,
        independent_replication_supported=True,
    )
    assert rec.stage is ProductEvidenceStage.INDEPENDENTLY_REPLICATED
    assert not rec.product_qualified


def test_product_qualified_requires_generalization_and_complete_bundle():
    rec = _record(
        external_real_workload_supported=True,
        quality_noninferiority_supported=True,
        catastrophic_regret_noninferiority_supported=True,
        coverage_equivalence_supported=True,
        physical_cost_accounting_verified=True,
        net_cost_superiority_supported=True,
        generalization_supported=True,
        independent_replication_supported=True,
        evidence_bundle_complete=True,
    )
    assert rec.stage is ProductEvidenceStage.PRODUCT_QUALIFIED
    assert rec.product_qualified


def test_production_control_requires_shadow_canary_and_provider_trace_even_after_product_qualification():
    rec = _record(
        external_real_workload_supported=True,
        quality_noninferiority_supported=True,
        catastrophic_regret_noninferiority_supported=True,
        coverage_equivalence_supported=True,
        physical_cost_accounting_verified=True,
        net_cost_superiority_supported=True,
        generalization_supported=True,
        independent_replication_supported=True,
        evidence_bundle_complete=True,
    )
    assert rec.product_qualified
    assert not rec.production_control_authorized


def test_require_stage_fails_closed_and_exposes_missing_obligations():
    with pytest.raises(RuntimeError) as exc:
        require_stage(_record(), ProductEvidenceStage.PRODUCT_QUALIFIED)
    assert "external_real_workload_supported" in str(exc.value)
    assert "independent_replication_supported" in str(exc.value)
