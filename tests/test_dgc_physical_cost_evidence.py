import pytest

from cwc.governance.physical_cost_evidence import (
    CostAuthority,
    CostComponentEvidence,
    PRODUCT_COST_COMPONENTS,
    certify_physical_trial_cost,
)


def _evidence():
    out = {}
    for index, component in enumerate(PRODUCT_COST_COMPONENTS):
        value = float(index) / 100.0
        authority = CostAuthority.ZERO_BY_CONTRACT if value == 0.0 else CostAuthority.INFRA_METER
        out[component] = CostComponentEvidence(
            component=component,
            value_usd=value,
            authority=authority,
            source_digest=f"source-{component}",
        )
    return out


def test_complete_physical_cost_evidence_seals_trial():
    cert = certify_physical_trial_cost(trial_id="trial-1", evidence=_evidence())
    assert cert.trial_id == "trial-1"
    assert len(cert.component_evidence) == len(PRODUCT_COST_COMPONENTS)
    assert len(cert.digest) == 64
    assert cert.cost.total_operational_usd == pytest.approx(sum(i / 100 for i in range(10)))


def test_missing_cost_component_fails_closed():
    evidence = _evidence()
    evidence.pop("human_review_usd")
    with pytest.raises(ValueError):
        certify_physical_trial_cost(trial_id="trial-1", evidence=evidence)


def test_key_component_mismatch_fails_closed():
    evidence = _evidence()
    evidence["model_usd"] = CostComponentEvidence(
        component="router_usd",
        value_usd=0.0,
        authority=CostAuthority.ZERO_BY_CONTRACT,
        source_digest="x",
    )
    with pytest.raises(ValueError):
        certify_physical_trial_cost(trial_id="trial-1", evidence=evidence)


def test_nonzero_cost_cannot_claim_zero_by_contract():
    with pytest.raises(ValueError):
        CostComponentEvidence(
            component="model_usd",
            value_usd=1.0,
            authority=CostAuthority.ZERO_BY_CONTRACT,
            source_digest="x",
        )


def test_missing_source_digest_fails_closed():
    with pytest.raises(ValueError):
        CostComponentEvidence(
            component="model_usd",
            value_usd=0.0,
            authority=CostAuthority.ZERO_BY_CONTRACT,
            source_digest="",
        )
