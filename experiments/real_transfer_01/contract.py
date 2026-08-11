from __future__ import annotations

import hashlib
import json
import math
import re
import string
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, Mapping, Sequence


class ContractError(ValueError):
    """REAL-TRANSFER-01 source/contract violation."""


class FrozenQuotaError(ContractError):
    """Frozen external cohort construction cannot be satisfied."""


class Action(str, Enum):
    ACT_SUPPORTED = "ACT_SUPPORTED"
    ACT_REFUTED = "ACT_REFUTED"
    ACT_ANSWER = "ACT_ANSWER"
    QUERY_COMPLEMENT = "QUERY_COMPLEMENT"
    ABSTAIN = "ABSTAIN"
    REJECT_SINGLE_VERDICT_MODEL = "REJECT_SINGLE_VERDICT_MODEL"


class AVeriTeCLabel(str, Enum):
    SUPPORTED = "SUPPORTED"
    REFUTED = "REFUTED"
    NOT_ENOUGH_EVIDENCE = "NOT_ENOUGH_EVIDENCE"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"


_LABEL_ALIASES = {
    "Supported": AVeriTeCLabel.SUPPORTED,
    "Refuted": AVeriTeCLabel.REFUTED,
    "Not Enough Evidence": AVeriTeCLabel.NOT_ENOUGH_EVIDENCE,
    "Conflicting Evidence/Cherrypicking": AVeriTeCLabel.CONFLICTING_EVIDENCE,
    "Conflicting Evidence/Cherry-picking": AVeriTeCLabel.CONFLICTING_EVIDENCE,
}

_LABEL_ACTION = {
    AVeriTeCLabel.SUPPORTED: Action.ACT_SUPPORTED,
    AVeriTeCLabel.REFUTED: Action.ACT_REFUTED,
    AVeriTeCLabel.NOT_ENOUGH_EVIDENCE: Action.ABSTAIN,
    AVeriTeCLabel.CONFLICTING_EVIDENCE: Action.REJECT_SINGLE_VERDICT_MODEL,
}


@dataclass(frozen=True, slots=True)
class AVeriTeCCase:
    record_hash: str
    gold_label: AVeriTeCLabel
    gold_action: Action
    model_input: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class HybridQACase:
    record_hash: str
    question_id: str
    question: str
    table_id: str
    gold_answer: str
    initial_modality: str
    table_payload: Any
    text_payload: Any

    def stage0_input(self) -> dict[str, Any]:
        if self.initial_modality == "TABLE_ONLY":
            return {"question": self.question, "table": self.table_payload}
        if self.initial_modality == "TEXT_ONLY":
            return {"question": self.question, "linked_text": self.text_payload}
        raise ContractError(f"invalid initial modality: {self.initial_modality}")

    def post_query_input(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "table": self.table_payload,
            "linked_text": self.text_payload,
        }


@dataclass(frozen=True, slots=True)
class Cohorts:
    calibration: tuple[Any, ...]
    primary: tuple[Any, ...]
    replication: tuple[Any, ...]

    def hashes(self) -> dict[str, tuple[str, ...]]:
        return {
            "CALIBRATION": tuple(x.record_hash for x in self.calibration),
            "PRIMARY": tuple(x.record_hash for x in self.primary),
            "REPLICATION": tuple(x.record_hash for x in self.replication),
        }


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _require_text(record: Mapping[str, Any], key: str) -> str:
    value = record.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{key} must be a non-empty string")
    return value


def canonical_averitec_label(raw: Any) -> AVeriTeCLabel:
    if not isinstance(raw, str) or raw not in _LABEL_ALIASES:
        raise ContractError(f"unrecognized AVeriTeC label literal: {raw!r}")
    return _LABEL_ALIASES[raw]


def _canonical_questions_answers(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list) or not raw:
        raise ContractError("questions must be a non-empty list")
    out: list[dict[str, Any]] = []
    for q in raw:
        if not isinstance(q, Mapping):
            raise ContractError("question item must be an object")
        question = _require_text(q, "question")
        answers_raw = q.get("answers")
        if not isinstance(answers_raw, list) or not answers_raw:
            raise ContractError("answers must be a non-empty list")
        answers: list[dict[str, Any]] = []
        for a in answers_raw:
            if not isinstance(a, Mapping):
                raise ContractError("answer item must be an object")
            answer = a.get("answer")
            if not isinstance(answer, str):
                raise ContractError("answer must be a string")
            answer_type = a.get("answer_type")
            if answer_type is not None and not isinstance(answer_type, str):
                raise ContractError("answer_type must be string/null")
            source_medium = a.get("source_medium")
            if source_medium is not None and not isinstance(source_medium, str):
                raise ContractError("source_medium must be string/null")
            # Candidate input deliberately excludes source/cached URLs and gold-only fields.
            answers.append(
                {
                    "answer": answer,
                    "answer_type": answer_type,
                    "source_medium": source_medium,
                }
            )
        out.append({"question": question, "answers": answers})
    return out


def make_averitec_case(record: Mapping[str, Any]) -> AVeriTeCCase:
    claim = _require_text(record, "claim")
    label = canonical_averitec_label(record.get("label"))
    evidence = _canonical_questions_answers(record.get("questions"))
    digest_material = f"{label.value}\n{claim}\n{_canonical_json(evidence)}"
    model_input = {"claim": claim, "evidence_qa": evidence}
    forbidden = {"label", "justification", "fact_checking_article", "record_hash"}
    if forbidden.intersection(model_input):
        raise ContractError("gold/leakage field entered model input")
    return AVeriTeCCase(
        record_hash=_sha256_text(digest_material),
        gold_label=label,
        gold_action=_LABEL_ACTION[label],
        model_input=model_input,
    )


def split_averitec(records: Iterable[Mapping[str, Any]]) -> Cohorts:
    by_label: dict[AVeriTeCLabel, list[AVeriTeCCase]] = {label: [] for label in AVeriTeCLabel}
    seen: set[str] = set()
    for raw in records:
        case = make_averitec_case(raw)
        if case.record_hash in seen:
            raise ContractError(f"duplicate AVeriTeC canonical record hash: {case.record_hash}")
        seen.add(case.record_hash)
        by_label[case.gold_label].append(case)

    calibration: list[AVeriTeCCase] = []
    primary: list[AVeriTeCCase] = []
    replication: list[AVeriTeCCase] = []
    for label, cases in by_label.items():
        cases.sort(key=lambda x: x.record_hash)
        n = len(cases)
        n_cal = math.floor(0.20 * n)
        n_primary = math.floor(0.40 * n)
        n_rep = n - n_cal - n_primary
        if n_cal < 5 or n_primary < 10 or n_rep < 10:
            raise FrozenQuotaError(
                f"{label.value}: N={n}, cal={n_cal}, primary={n_primary}, replication={n_rep}"
            )
        calibration.extend(cases[:n_cal])
        primary.extend(cases[n_cal:n_cal + n_primary])
        replication.extend(cases[n_cal + n_primary:])

    calibration.sort(key=lambda x: x.record_hash)
    primary.sort(key=lambda x: x.record_hash)
    replication.sort(key=lambda x: x.record_hash)
    _assert_disjoint(calibration, primary, replication)
    return Cohorts(tuple(calibration), tuple(primary), tuple(replication))


def make_hybridqa_case(
    record: Mapping[str, Any], *, table_payload: Any, text_payload: Any
) -> HybridQACase:
    question_id = _require_text(record, "question_id")
    question = _require_text(record, "question")
    table_id = _require_text(record, "table_id")
    gold_answer = _require_text(record, "answer-text")
    if table_payload is None or text_payload is None:
        raise ContractError("both HybridQA modalities must resolve before case admission")
    digest_material = f"{question_id}\n{question}\n{table_id}\n{gold_answer}"
    record_hash = _sha256_text(digest_material)
    first_byte = bytes.fromhex(record_hash[:2])[0]
    initial_modality = "TABLE_ONLY" if first_byte % 2 == 0 else "TEXT_ONLY"
    return HybridQACase(
        record_hash=record_hash,
        question_id=question_id,
        question=question,
        table_id=table_id,
        gold_answer=gold_answer,
        initial_modality=initial_modality,
        table_payload=table_payload,
        text_payload=text_payload,
    )


def split_hybridqa(cases: Sequence[HybridQACase]) -> Cohorts:
    ordered = sorted(cases, key=lambda x: x.record_hash)
    hashes = [x.record_hash for x in ordered]
    if len(set(hashes)) != len(hashes):
        raise ContractError("duplicate HybridQA canonical record hash")
    if len(ordered) < 576:
        raise FrozenQuotaError(f"HybridQA admissible N={len(ordered)} < frozen 576")
    cohorts = Cohorts(
        calibration=tuple(ordered[:64]),
        primary=tuple(ordered[64:320]),
        replication=tuple(ordered[320:576]),
    )
    _assert_disjoint(*cohorts.__dict__.values()) if hasattr(cohorts, "__dict__") else _assert_disjoint(
        cohorts.calibration, cohorts.primary, cohorts.replication
    )
    return cohorts


def _assert_disjoint(*groups: Sequence[Any]) -> None:
    seen: set[str] = set()
    for group in groups:
        for case in group:
            h = case.record_hash
            if h in seen:
                raise ContractError(f"cohort overlap for {h}")
            seen.add(h)


def normalize_hybridqa_answer(text: str) -> str:
    if not isinstance(text, str):
        raise ContractError("answer must be a string")
    lowered = text.lower()
    no_punc = "".join(ch for ch in lowered if ch not in set(string.punctuation))
    no_articles = re.sub(r"\b(a|an|the)\b", " ", no_punc)
    return " ".join(no_articles.split())


def hybridqa_exact_match(prediction: str, gold: str) -> int:
    return int(normalize_hybridqa_answer(prediction) == normalize_hybridqa_answer(gold))


def cohort_digest(cases: Sequence[Any]) -> str:
    return _sha256_text("\n".join(case.record_hash for case in cases))
