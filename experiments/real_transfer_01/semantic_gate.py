from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Callable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from experiments.real_transfer_01.contract import (
    Action,
    ContractError,
    FrozenQuotaError,
    make_averitec_case,
    make_hybridqa_case,
    split_averitec,
    split_hybridqa,
)
from experiments.real_transfer_01.evaluator import (
    AVeriTeCDecision,
    HybridQADecision,
    ResourceUsage,
    evaluate_averitec,
    evaluate_hybridqa,
)
from experiments.real_transfer_01.preflight import (
    authority_from_contamination,
    validate_averitec_model_input,
    validate_calibration_binding,
    validate_cohorts,
    validate_comparators,
    validate_hybridqa_stage0,
)

POLICIES = (
    "ALWAYS_ACT", "ALWAYS_QUERY", "ALWAYS_ABSTAIN", "MAX_SCORE_MARGIN",
    "MODEL_ID_MAXIMIN", "DECISION_RELEVANT",
)


@dataclass(frozen=True, slots=True)
class MutationResult:
    mutation: str
    killed: bool
    detail: str


def _av(i: int, label: str) -> dict:
    return {
        "claim": f"claim-{label}-{i}",
        "label": label,
        "justification": "GOLD",
        "fact_checking_article": "https://gold.invalid",
        "questions": [{
            "question": f"q{i}",
            "answers": [{"answer": f"a{i}", "answer_type": "Extractive", "source_medium": "Web text"}],
        }],
    }


def _h(i: int):
    return make_hybridqa_case(
        {"question_id": f"id-{i}", "question": f"q{i}", "table_id": f"t{i}", "answer-text": f"a{i}"},
        table_payload={"row": i}, text_payload={"text": f"p{i}"},
    )


def _usage(q=0, calls=1, tokens=10):
    return ResourceUsage(q, calls, tokens, 0)


def _av_rows(*, nei_forced=False, conflict_abstain=False, expensive_candidate=False):
    golds = [Action.ACT_SUPPORTED, Action.ACT_REFUTED, Action.ABSTAIN, Action.REJECT_SINGLE_VERDICT_MODEL] * 10
    rows = []
    for p in POLICIES:
        for i, gold in enumerate(golds):
            if p == "ALWAYS_ACT":
                pred = Action.ACT_REFUTED if gold is Action.ACT_REFUTED else Action.ACT_SUPPORTED
            elif p == "ALWAYS_ABSTAIN":
                pred = Action.ABSTAIN
            elif p == "MODEL_ID_MAXIMIN":
                pred = gold if gold in (Action.ACT_SUPPORTED, Action.ACT_REFUTED) else Action.ACT_SUPPORTED
            else:
                pred = gold
            if p == "DECISION_RELEVANT" and nei_forced and gold is Action.ABSTAIN:
                pred = Action.ACT_SUPPORTED
            if p == "DECISION_RELEVANT" and conflict_abstain and gold is Action.REJECT_SINGLE_VERDICT_MODEL:
                pred = Action.ABSTAIN
            usage = _usage(calls=3, tokens=30) if p == "DECISION_RELEVANT" and expensive_candidate else _usage()
            if p in ("MAX_SCORE_MARGIN", "MODEL_ID_MAXIMIN"):
                usage = _usage(calls=2, tokens=20)
            rows.append(AVeriTeCDecision(p, f"a{i}", gold, pred, usage))
    return rows


def _hybrid_rows(*, premature=False):
    rows = []
    for p in POLICIES:
        for i in range(100):
            gold = f"answer {i}"
            if p == "ALWAYS_ACT":
                stage, post, q = Action.ACT_ANSWER, None, 0
            elif p == "ALWAYS_ABSTAIN":
                stage, post, q = Action.ABSTAIN, None, 0
            elif p == "DECISION_RELEVANT":
                if i < 10:
                    stage, post, q = Action.ABSTAIN, None, 0
                else:
                    stage, post, q = Action.QUERY_COMPLEMENT, gold, 1
                if premature and i < 10:
                    stage = Action.ACT_ANSWER
            elif p == "MAX_SCORE_MARGIN":
                if i < 5:
                    stage, post, q = Action.ACT_ANSWER, None, 0
                else:
                    stage, post, q = Action.QUERY_COMPLEMENT, ("wrong" if i < 10 else gold), 1
            else:
                stage, post, q = Action.QUERY_COMPLEMENT, ("wrong" if i < 10 else gold), 1
            calls = 2 if p in ("MAX_SCORE_MARGIN", "MODEL_ID_MAXIMIN") else 1
            toks = 20 if p in ("MAX_SCORE_MARGIN", "MODEL_ID_MAXIMIN") else 10
            rows.append(HybridQADecision(p, f"h{i}", gold, stage, post, _usage(q, calls, toks)))
    return rows


def _expect_exception(fn: Callable[[], object]) -> bool:
    try:
        fn()
    except (ContractError, FrozenQuotaError):
        return True
    return False


def _run_mutation(name: str, fn: Callable[[], bool]) -> MutationResult:
    try:
        killed = bool(fn())
        return MutationResult(name, killed, "detected" if killed else "SURVIVED")
    except Exception as exc:  # a semantic-gate crash is not a mutation kill
        return MutationResult(name, False, f"gate_error:{type(exc).__name__}:{exc}")


def self_test() -> tuple[MutationResult, ...]:
    labels = ["Supported", "Refuted", "Not Enough Evidence", "Conflicting Evidence/Cherrypicking"]

    results = []
    results.append(_run_mutation("EXPOSE_AVERITEC_GOLD_LABEL", lambda: _expect_exception(
        lambda: validate_averitec_model_input({**make_averitec_case(_av(1, "Supported")).model_input, "label": "Supported"})
    )))
    results.append(_run_mutation("EXPOSE_AVERITEC_GOLD_JUSTIFICATION", lambda: _expect_exception(
        lambda: validate_averitec_model_input({**make_averitec_case(_av(2, "Refuted")).model_input, "justification": "GOLD"})
    )))
    results.append(_run_mutation("FORCE_NEI_VERDICT", lambda: not evaluate_averitec(_av_rows(nei_forced=True)).passed))
    results.append(_run_mutation("CONFLICT_TO_PLAIN_ABSTAIN", lambda: not evaluate_averitec(_av_rows(conflict_abstain=True)).passed))

    h = _h(3)
    def leak_complement() -> bool:
        payload = h.stage0_input()
        payload["table"] = h.table_payload
        payload["linked_text"] = h.text_payload
        return _expect_exception(lambda: validate_hybridqa_stage0(payload, h.initial_modality))
    results.append(_run_mutation("EXPOSE_HYBRID_COMPLEMENT_PREQUERY", leak_complement))
    results.append(_run_mutation("COUNT_PREQUERY_ANSWER_AS_VALID", lambda: not evaluate_hybridqa(_hybrid_rows(premature=True)).passed))

    def order_dependence() -> bool:
        records = [_av(i, label) for label in labels for i in range(30)]
        return split_averitec(records).hashes() == split_averitec(list(reversed(records))).hashes()
    results.append(_run_mutation("FILE_ORDER_CHANGES_COHORT", order_dependence))

    def overlap() -> bool:
        c = split_hybridqa([_h(i) for i in range(576)])
        broken = type(c)(c.calibration, c.primary, c.primary)
        return _expect_exception(lambda: validate_cohorts(broken))
    results.append(_run_mutation("PRIMARY_REPLICATION_OVERLAP", overlap))

    results.append(_run_mutation("OMIT_REQUIRED_COMPARATOR", lambda: _expect_exception(
        lambda: validate_comparators(POLICIES[:-1])
    )))
    results.append(_run_mutation("HIGHER_COST_COUNTS_MATCHED", lambda: not evaluate_averitec(
        _av_rows(expensive_candidate=True)
    ).passed))
    results.append(_run_mutation("TUNE_ON_PRIMARY", lambda: _expect_exception(
        lambda: validate_calibration_binding({
            "threshold_fit_cohort": "PRIMARY", "observed_cohorts_before_freeze": ["PRIMARY"]
        })
    )))

    def frozen_quota_drop() -> bool:
        records = [_av(i, label) for label in labels for i in range(30)]
        records = [r for r in records if r["label"] != "Not Enough Evidence" or int(r["claim"].rsplit("-", 1)[1]) < 20]
        return _expect_exception(lambda: split_averitec(records))
    results.append(_run_mutation("SILENT_FROZEN_QUOTA_DROP", frozen_quota_drop))
    results.append(_run_mutation("PROMOTE_UNKNOWN_CONTAMINATION", lambda:
        authority_from_contamination("UNKNOWN", False) != "TRANSFER_OBSERVED_CONTAMINATION_AUDITED"
    ))
    return tuple(results)


def main() -> int:
    results = self_test()
    killed = sum(r.killed for r in results)
    for r in results:
        print(f"{r.mutation}: {'KILLED' if r.killed else 'SURVIVED'} ({r.detail})")
    print(f"REAL-TRANSFER-01 semantic self-test: {killed}/{len(results)} mutations killed")
    return 0 if killed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
