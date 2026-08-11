from __future__ import annotations

import copy

import pytest

from experiments.real_transfer_01.contract import (
    AVeriTeCLabel,
    Action,
    ContractError,
    FrozenQuotaError,
    hybridqa_exact_match,
    make_averitec_case,
    make_hybridqa_case,
    normalize_hybridqa_answer,
    split_averitec,
    split_hybridqa,
)
from experiments.real_transfer_01.preflight import (
    authority_from_contamination,
    validate_averitec_model_input,
    validate_calibration_binding,
    validate_cohorts,
    validate_comparators,
    validate_hybridqa_stage0,
    validate_model_manifest,
)

LABELS = [
    "Supported",
    "Refuted",
    "Not Enough Evidence",
    "Conflicting Evidence/Cherrypicking",
]


def av_record(i: int, label: str) -> dict:
    return {
        "claim": f"claim {label} {i}",
        "label": label,
        "justification": f"gold justification {i}",
        "fact_checking_article": f"https://gold/{i}",
        "questions": [
            {
                "question": f"q{i}",
                "answers": [
                    {
                        "answer": f"answer {i}",
                        "answer_type": "Extractive",
                        "source_medium": "Web text",
                        "source_url": f"https://source/{i}",
                    }
                ],
            }
        ],
    }


def h_case(i: int):
    return make_hybridqa_case(
        {
            "question_id": f"id-{i}",
            "question": f"Question {i}?",
            "table_id": f"table-{i}",
            "answer-text": f"The Answer {i}",
        },
        table_payload={"rows": [[i]]},
        text_payload={"passages": [f"p{i}"]},
    )


def test_averitec_aliases_and_actions_are_exact():
    conflict_a = make_averitec_case(av_record(1, "Conflicting Evidence/Cherrypicking"))
    conflict_b = make_averitec_case(av_record(1, "Conflicting Evidence/Cherry-picking"))
    assert conflict_a.gold_label is AVeriTeCLabel.CONFLICTING_EVIDENCE
    assert conflict_b.gold_label is AVeriTeCLabel.CONFLICTING_EVIDENCE
    assert conflict_a.gold_action is Action.REJECT_SINGLE_VERDICT_MODEL
    with pytest.raises(ContractError):
        make_averitec_case(av_record(2, "Conflicting Evidence"))


def test_averitec_model_input_excludes_gold_and_urls():
    case = make_averitec_case(av_record(3, "Supported"))
    text = repr(case.model_input)
    for forbidden in ("justification", "fact_checking_article", "source_url", "gold", "record_hash"):
        assert forbidden not in text
    validate_averitec_model_input(case.model_input)


def test_averitec_input_validator_kills_gold_leakage():
    payload = dict(make_averitec_case(av_record(4, "Refuted")).model_input)
    payload["label"] = "Refuted"
    with pytest.raises(ContractError):
        validate_averitec_model_input(payload)


def test_averitec_split_is_file_order_invariant_and_stratified():
    records = [av_record(i, label) for label in LABELS for i in range(30)]
    a = split_averitec(records)
    b = split_averitec(list(reversed(records)))
    assert a.hashes() == b.hashes()
    assert len(a.calibration) == 24  # 6 x 4 labels
    assert len(a.primary) == 48      # 12 x 4 labels
    assert len(a.replication) == 48
    validate_cohorts(a)


def test_averitec_frozen_minimum_fails_closed():
    records = [av_record(i, label) for label in LABELS for i in range(30)]
    records = [r for r in records if r["label"] != "Not Enough Evidence" or int(r["claim"].split()[-1]) < 20]
    with pytest.raises(FrozenQuotaError):
        split_averitec(records)


def test_hybridqa_stage0_contains_exactly_one_modality():
    case = h_case(1)
    payload = case.stage0_input()
    validate_hybridqa_stage0(payload, case.initial_modality)
    assert ("table" in payload) ^ ("linked_text" in payload)
    post = case.post_query_input()
    assert "table" in post and "linked_text" in post


def test_hybridqa_stage0_leak_is_rejected():
    case = h_case(2)
    payload = case.stage0_input()
    payload["table"] = case.table_payload
    payload["linked_text"] = case.text_payload
    with pytest.raises(ContractError):
        validate_hybridqa_stage0(payload, case.initial_modality)


def test_hybridqa_modality_and_cohort_assignment_are_order_invariant():
    cases = [h_case(i) for i in range(576)]
    a = split_hybridqa(cases)
    b = split_hybridqa(list(reversed(cases)))
    assert a.hashes() == b.hashes()
    assert len(a.calibration) == 64
    assert len(a.primary) == 256
    assert len(a.replication) == 256


def test_hybridqa_quota_fails_closed():
    with pytest.raises(FrozenQuotaError):
        split_hybridqa([h_case(i) for i in range(575)])


def test_hybridqa_em_normalization_is_frozen():
    assert normalize_hybridqa_answer(" The, Answer! ") == "answer"
    assert hybridqa_exact_match("An APPLE.", "apple") == 1
    assert hybridqa_exact_match("apple pie", "apple") == 0


def test_calibration_binding_blocks_primary_tuning():
    validate_calibration_binding({"threshold_fit_cohort": "CALIBRATION", "observed_cohorts_before_freeze": []})
    with pytest.raises(ContractError):
        validate_calibration_binding({"threshold_fit_cohort": "PRIMARY", "observed_cohorts_before_freeze": ["PRIMARY"]})


def test_contamination_unknown_never_promotes_to_audited():
    assert authority_from_contamination("UNKNOWN", False) == "TRANSFER_OBSERVED_CONTAMINATION_UNKNOWN"
    assert authority_from_contamination("sha256:abc", True) == "TRANSFER_OBSERVED_CONTAMINATION_AUDITED"


def test_required_comparator_contract_is_exact():
    policies = (
        "ALWAYS_ACT", "ALWAYS_QUERY", "ALWAYS_ABSTAIN", "MAX_SCORE_MARGIN",
        "MODEL_ID_MAXIMIN", "DECISION_RELEVANT",
    )
    validate_comparators(policies)
    with pytest.raises(ContractError):
        validate_comparators(policies[:-1])


def test_model_manifest_requires_content_addressed_runner_parts():
    good = {
        "runner_version": "1",
        "weights_sha256": "w",
        "tokenizer_sha256": "t",
        "prompt_template_sha256": "p",
        "decoding_parameters": {"temperature": 0},
        "calibration_procedure_sha256": "c",
        "governor_parameters_sha256": "g",
        "training_corpus_provenance": "UNKNOWN",
    }
    validate_model_manifest(good)
    bad = copy.deepcopy(good); del bad["weights_sha256"]
    with pytest.raises(ContractError):
        validate_model_manifest(bad)
