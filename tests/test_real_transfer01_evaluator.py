from __future__ import annotations

import pytest

from experiments.real_transfer_01.contract import Action, ContractError
from experiments.real_transfer_01.evaluator import (
    AVeriTeCDecision,
    HybridQADecision,
    ResourceUsage,
    evaluate_averitec,
    evaluate_hybridqa,
)

POLICIES = (
    "ALWAYS_ACT", "ALWAYS_QUERY", "ALWAYS_ABSTAIN", "MAX_SCORE_MARGIN",
    "MODEL_ID_MAXIMIN", "DECISION_RELEVANT",
)


def _u(q=0, calls=1, toks=10):
    return ResourceUsage(q, calls, toks, 0)


def av_rows(candidate_override=None, candidate_usage=None):
    gold = [Action.ACT_SUPPORTED, Action.ACT_REFUTED, Action.ABSTAIN, Action.REJECT_SINGLE_VERDICT_MODEL] * 10
    rows = []
    for p in POLICIES:
        for i, g in enumerate(gold):
            if p == "ALWAYS_ACT":
                pred = Action.ACT_SUPPORTED if g is not Action.ACT_REFUTED else Action.ACT_REFUTED
            elif p == "ALWAYS_ABSTAIN":
                pred = Action.ABSTAIN
            elif p == "MODEL_ID_MAXIMIN":
                pred = g if g in (Action.ACT_SUPPORTED, Action.ACT_REFUTED) else Action.ACT_SUPPORTED
            else:
                pred = g
            if p == "DECISION_RELEVANT" and candidate_override:
                pred = candidate_override(i, g, pred)
            usage = candidate_usage or _u()
            if p in ("MAX_SCORE_MARGIN", "MODEL_ID_MAXIMIN"):
                usage = _u(calls=2, toks=20)
            rows.append(AVeriTeCDecision(p, f"c{i}", g, pred, usage))
    return rows


def test_averitec_gate_passes_coherent_external_decisions():
    result = evaluate_averitec(av_rows())
    assert result.passed, result.reasons
    assert result.metrics["forced_verdict_error"] == 0.0
    assert result.metrics["nei_recall"] == 1.0
    assert result.metrics["conflict_recall"] == 1.0


def test_averitec_forced_nei_verdict_fails():
    def mutate(i, gold, pred):
        return Action.ACT_SUPPORTED if gold is Action.ABSTAIN else pred
    result = evaluate_averitec(av_rows(candidate_override=mutate))
    assert not result.passed
    assert not result.endpoints["nei_recall"]


def test_averitec_conflict_to_plain_abstain_fails():
    def mutate(i, gold, pred):
        return Action.ABSTAIN if gold is Action.REJECT_SINGLE_VERDICT_MODEL else pred
    result = evaluate_averitec(av_rows(candidate_override=mutate))
    assert not result.passed
    assert not result.endpoints["conflict_recall"]


def test_averitec_higher_compute_cannot_count_as_matched():
    result = evaluate_averitec(av_rows(candidate_usage=_u(calls=3, toks=30)))
    assert not result.passed
    assert not result.endpoints["matched_max_score_margin"]


def test_missing_comparator_fails_closed():
    rows = [r for r in av_rows() if r.policy != "MODEL_ID_MAXIMIN"]
    with pytest.raises(ContractError):
        evaluate_averitec(rows)


def hybrid_rows(n=100):
    rows = []
    # Cases 0..9 are deliberately impossible for every queried policy. This allows
    # the decision policy to skip them without degrading EM relative to ALWAYS_QUERY.
    for p in POLICIES:
        for i in range(n):
            gold = f"answer {i}"
            if p == "ALWAYS_ACT":
                stage0 = Action.ACT_ANSWER; post = None; q = 0
            elif p == "ALWAYS_ABSTAIN":
                stage0 = Action.ABSTAIN; post = None; q = 0
            elif p == "DECISION_RELEVANT":
                if i < 10:
                    stage0 = Action.ABSTAIN; post = None; q = 0
                else:
                    stage0 = Action.QUERY_COMPLEMENT; post = gold; q = 1
            elif p == "MAX_SCORE_MARGIN":
                if i < 5:
                    stage0 = Action.ACT_ANSWER; post = None; q = 0
                else:
                    stage0 = Action.QUERY_COMPLEMENT; post = "wrong" if i < 10 else gold; q = 1
            elif p == "MODEL_ID_MAXIMIN":
                stage0 = Action.QUERY_COMPLEMENT; post = "wrong" if i < 10 else gold; q = 1
            else:  # ALWAYS_QUERY
                stage0 = Action.QUERY_COMPLEMENT; post = "wrong" if i < 10 else gold; q = 1
            # Eligible direct comparators have >= candidate resource budget.
            calls = 2 if p in ("MAX_SCORE_MARGIN", "MODEL_ID_MAXIMIN") else 1
            toks = 20 if p in ("MAX_SCORE_MARGIN", "MODEL_ID_MAXIMIN") else 10
            rows.append(HybridQADecision(p, f"h{i}", gold, stage0, post, _u(q=q, calls=calls, toks=toks)))
    return rows


def test_hybridqa_gate_can_pass_without_query_collapse():
    result = evaluate_hybridqa(hybrid_rows())
    assert result.passed, result.reasons
    assert result.metrics["DECISION_RELEVANT.necessary_query_recall"] == 0.9
    assert result.metrics["DECISION_RELEVANT.premature_answer_rate"] == 0.0
    assert result.metrics["DECISION_RELEVANT.post_query_em"] == 0.9


def test_hybridqa_premature_answer_fails():
    rows = hybrid_rows()
    mutated = []
    for r in rows:
        if r.policy == "DECISION_RELEVANT" and int(r.case_id[1:]) < 10:
            r = HybridQADecision(r.policy, r.case_id, r.gold_answer, Action.ACT_ANSWER, None, r.usage)
        mutated.append(r)
    result = evaluate_hybridqa(mutated)
    assert not result.passed
    assert not result.endpoints["premature_answer_rate"]


def test_hybridqa_unmatched_direct_comparator_blocks_full_pass():
    rows = []
    for r in hybrid_rows():
        if r.policy == "DECISION_RELEVANT":
            r = HybridQADecision(r.policy, r.case_id, r.gold_answer, r.stage0_action, r.post_query_answer,
                                 ResourceUsage(r.usage.external_query_units, 3, 30, 0))
        rows.append(r)
    result = evaluate_hybridqa(rows)
    assert not result.passed
    assert not result.endpoints["matched_model_id_maximin"]
