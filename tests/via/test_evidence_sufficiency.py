from scripts.via_evidence_sufficiency import audit


def test_frozen_real_evidence_does_not_manufacture_instance_outcomes() -> None:
    result = audit()
    assert result["real_instance_opportunity_identified"] is False
    assert result["wp18"]["paired_per_unit_action_outcomes_present"] is False
    assert result["wp19"]["paired_per_unit_action_outcomes_present"] is False
    assert result["ascension_authorized"] is False


def test_future_contract_requires_same_unit_all_actions_and_raw_values() -> None:
    contract = audit()["required_future_artifact_contract"]
    assert contract["same_unit_all_actions"] is True
    assert contract["raw_quality_before_scalarization"] is True
    assert contract["raw_compute_per_action"] is True
    assert contract["no_preaggregation_before_evidence_seal"] is True
