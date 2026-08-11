from __future__ import annotations

import copy
import hashlib
import json

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
    validate_source_manifest,
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


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json_sha(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def test_model_manifest_requires_real_content_addresses_and_binds_decoding():
    decoding = {"temperature": 0, "top_p": 1.0}
    good = {
        "runner_version": "1",
        "weights_sha256": _sha("weights"),
        "tokenizer_sha256": _sha("tokenizer"),
        "prompt_template_sha256": _sha("prompt"),
        "decoding_parameters": decoding,
        "decoding_parameters_sha256": _json_sha(decoding),
        "calibration_procedure_sha256": _sha("calibration"),
        "governor_parameters_sha256": _sha("governor"),
        "training_corpus_provenance": "UNKNOWN",
    }
    validate_model_manifest(good)

    missing = copy.deepcopy(good); del missing["weights_sha256"]
    with pytest.raises(ContractError):
        validate_model_manifest(missing)

    short_hash = copy.deepcopy(good); short_hash["weights_sha256"] = "w"
    with pytest.raises(ContractError):
        validate_model_manifest(short_hash)

    unbound_decoding = copy.deepcopy(good); unbound_decoding["decoding_parameters"]["temperature"] = 0.7
    with pytest.raises(ContractError):
        validate_model_manifest(unbound_decoding)


def _manifest_cohort(prefix: str, n: int = 3):
    hashes = [_sha(f"{prefix}-{i}") for i in range(n)]
    return {
        "count": n,
        "cohort_sha256": hashlib.sha256("\n".join(hashes).encode("utf-8")).hexdigest(),
        "record_hashes": hashes,
    }


def _source_manifest():
    return {
        "experiment": "REAL-TRANSFER-01",
        "sources": [
            {
                "family": "AVeriTeC",
                "canonical_url": "https://example.invalid/averitec",
                "ref": "main",
                "path": "data/dev.json",
                "byte_length": 123,
                "sha256": _sha("averitec-source"),
                "upstream_commit_sha": "a" * 40,
                "license": "CC BY-NC 4.0",
                "acquired_at": "2026-08-11T16:00:00Z",
            },
            {
                "family": "HybridQA",
                "canonical_url": "https://example.invalid/hybridqa",
                "ref": "master",
                "path": "released_data/dev.json",
                "byte_length": 456,
                "sha256": _sha("hybrid-source"),
                "upstream_commit_sha": None,
                "license": "MIT",
                "acquired_at": "2026-08-11T16:00:00Z",
            },
        ],
        "cohorts": {
            "AVeriTeC": {
                "CALIBRATION": _manifest_cohort("av-cal"),
                "PRIMARY": _manifest_cohort("av-primary"),
                "REPLICATION": _manifest_cohort("av-rep"),
            },
            "HybridQA": {
                "CALIBRATION": _manifest_cohort("hq-cal"),
                "PRIMARY": _manifest_cohort("hq-primary"),
                "REPLICATION": _manifest_cohort("hq-rep"),
            },
        },
        "collision_audit": {
            "repository_exact_collision_count": 0,
            "training_exact_collision_count": None,
            "training_collision_audit_complete": False,
        },
    }


def test_source_manifest_enforces_frozen_provenance_and_per_record_hashes():
    good = _source_manifest()
    validate_source_manifest(good)

    permuted = copy.deepcopy(good)
    for family in ("AVeriTeC", "HybridQA"):
        groups = permuted["cohorts"][family]
        permuted["cohorts"][family] = {
            "REPLICATION": groups["REPLICATION"],
            "CALIBRATION": groups["CALIBRATION"],
            "PRIMARY": groups["PRIMARY"],
        }
    validate_source_manifest(permuted)

    bad_sha = copy.deepcopy(good); bad_sha["sources"][0]["sha256"] = "abc"
    with pytest.raises(ContractError):
        validate_source_manifest(bad_sha)

    overlap = copy.deepcopy(good)
    overlap["cohorts"]["AVeriTeC"]["REPLICATION"]["record_hashes"][0] = \
        overlap["cohorts"]["AVeriTeC"]["PRIMARY"]["record_hashes"][0]
    with pytest.raises(ContractError):
        validate_source_manifest(overlap)

    inconsistent_audit = copy.deepcopy(good)
    inconsistent_audit["collision_audit"]["training_collision_audit_complete"] = True
    with pytest.raises(ContractError):
        validate_source_manifest(inconsistent_audit)
