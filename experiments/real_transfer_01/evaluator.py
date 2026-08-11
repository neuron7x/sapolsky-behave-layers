from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Sequence

from experiments.real_transfer_01.contract import Action, ContractError, hybridqa_exact_match

REQUIRED_POLICIES = (
    "ALWAYS_ACT",
    "ALWAYS_QUERY",
    "ALWAYS_ABSTAIN",
    "MAX_SCORE_MARGIN",
    "MODEL_ID_MAXIMIN",
    "DECISION_RELEVANT",
)


@dataclass(frozen=True, slots=True)
class ResourceUsage:
    external_query_units: int = 0
    model_forward_calls: int = 0
    input_tokens: int = 0
    generated_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.generated_tokens

    def __add__(self, other: "ResourceUsage") -> "ResourceUsage":
        return ResourceUsage(
            self.external_query_units + other.external_query_units,
            self.model_forward_calls + other.model_forward_calls,
            self.input_tokens + other.input_tokens,
            self.generated_tokens + other.generated_tokens,
        )


@dataclass(frozen=True, slots=True)
class AVeriTeCDecision:
    policy: str
    case_id: str
    gold_action: Action
    predicted_action: Action
    usage: ResourceUsage


@dataclass(frozen=True, slots=True)
class HybridQADecision:
    policy: str
    case_id: str
    gold_answer: str
    stage0_action: Action
    post_query_answer: str | None
    usage: ResourceUsage


@dataclass(frozen=True, slots=True)
class GateResult:
    passed: bool
    endpoints: Mapping[str, bool]
    metrics: Mapping[str, float | int | str | bool | None]
    reasons: tuple[str, ...]


def _group_by_policy(rows: Iterable[object]) -> dict[str, list[object]]:
    out: dict[str, list[object]] = {p: [] for p in REQUIRED_POLICIES}
    unknown: set[str] = set()
    for row in rows:
        policy = getattr(row, "policy")
        if policy not in out:
            unknown.add(policy)
            continue
        out[policy].append(row)
    if unknown:
        raise ContractError(f"unknown policies: {sorted(unknown)}")
    missing = [p for p, rs in out.items() if not rs]
    if missing:
        raise ContractError(f"missing required comparators: {missing}")
    return out


def _validate_case_alignment(grouped: Mapping[str, Sequence[object]]) -> tuple[str, ...]:
    expected: tuple[str, ...] | None = None
    for policy in REQUIRED_POLICIES:
        ids = tuple(sorted(getattr(row, "case_id") for row in grouped[policy]))
        if len(set(ids)) != len(ids):
            raise ContractError(f"duplicate case id within {policy}")
        if expected is None:
            expected = ids
        elif ids != expected:
            raise ContractError(f"case set mismatch for {policy}")
    return expected or ()


def _usage(rows: Sequence[object]) -> ResourceUsage:
    total = ResourceUsage()
    for row in rows:
        total = total + getattr(row, "usage")
    return total


def _rate(num: int, den: int) -> float:
    if den <= 0:
        raise ContractError("metric denominator is zero")
    return num / den


def evaluate_averitec(rows: Iterable[AVeriTeCDecision]) -> GateResult:
    grouped = _group_by_policy(rows)
    _validate_case_alignment(grouped)
    candidate = grouped["DECISION_RELEVANT"]
    maxmargin = grouped["MAX_SCORE_MARGIN"]

    by_case = {row.case_id: row for row in candidate}
    mm_case = {row.case_id: row for row in maxmargin}
    unsafe_gold = {Action.ABSTAIN, Action.REJECT_SINGLE_VERDICT_MODEL}
    forced_actions = {Action.ACT_SUPPORTED, Action.ACT_REFUTED}
    act_gold = {Action.ACT_SUPPORTED, Action.ACT_REFUTED}

    unsafe = [r for r in candidate if r.gold_action in unsafe_gold]
    forced_error = _rate(sum(r.predicted_action in forced_actions for r in unsafe), len(unsafe))

    forced_comparators: dict[str, float] = {}
    for policy in ("ALWAYS_ACT", "MODEL_ID_MAXIMIN"):
        rs = [r for r in grouped[policy] if r.gold_action in unsafe_gold]
        forced_comparators[policy] = _rate(sum(r.predicted_action in forced_actions for r in rs), len(rs))

    def balanced_acc(policy_rows: Sequence[AVeriTeCDecision]) -> float:
        recalls = []
        for gold in (Action.ACT_SUPPORTED, Action.ACT_REFUTED):
            subset = [r for r in policy_rows if r.gold_action is gold]
            recalls.append(_rate(sum(r.predicted_action is gold for r in subset), len(subset)))
        return sum(recalls) / 2.0

    cand_ba = balanced_acc(candidate)
    mm_ba = balanced_acc(maxmargin)
    nei = [r for r in candidate if r.gold_action is Action.ABSTAIN]
    conflict = [r for r in candidate if r.gold_action is Action.REJECT_SINGLE_VERDICT_MODEL]
    act_cases = [r for r in candidate if r.gold_action in act_gold]
    nei_recall = _rate(sum(r.predicted_action is Action.ABSTAIN for r in nei), len(nei))
    conflict_recall = _rate(
        sum(r.predicted_action is Action.REJECT_SINGLE_VERDICT_MODEL for r in conflict), len(conflict)
    )
    non_action_rate = _rate(
        sum(r.predicted_action in unsafe_gold for r in act_cases), len(act_cases)
    )

    cand_usage = _usage(candidate)
    matched = {}
    for policy in ("MAX_SCORE_MARGIN", "MODEL_ID_MAXIMIN"):
        u = _usage(grouped[policy])
        matched[policy] = (
            cand_usage.model_forward_calls <= u.model_forward_calls
            and cand_usage.total_tokens <= u.total_tokens
        )

    endpoints = {
        "forced_error_lt_always_act": forced_error < forced_comparators["ALWAYS_ACT"],
        "forced_error_lt_model_id": forced_error < forced_comparators["MODEL_ID_MAXIMIN"],
        "supported_refuted_ba_noninferior": cand_ba >= mm_ba - 0.02,
        "nei_recall": nei_recall >= 0.60,
        "conflict_recall": conflict_recall >= 0.60,
        "collapse_guard": non_action_rate <= 0.25,
        "matched_max_score_margin": matched["MAX_SCORE_MARGIN"],
        "matched_model_id_maximin": matched["MODEL_ID_MAXIMIN"],
    }
    metrics = {
        "forced_verdict_error": forced_error,
        "always_act_forced_error": forced_comparators["ALWAYS_ACT"],
        "model_id_forced_error": forced_comparators["MODEL_ID_MAXIMIN"],
        "supported_refuted_balanced_accuracy": cand_ba,
        "max_score_margin_balanced_accuracy": mm_ba,
        "nei_recall": nei_recall,
        "conflict_recall": conflict_recall,
        "supported_refuted_non_action_rate": non_action_rate,
    }
    failed = tuple(k for k, ok in endpoints.items() if not ok)
    return GateResult(not failed, endpoints, metrics, failed)


def evaluate_hybridqa(rows: Iterable[HybridQADecision]) -> GateResult:
    grouped = _group_by_policy(rows)
    _validate_case_alignment(grouped)

    def metrics(policy: str) -> dict[str, float | int]:
        rs = grouped[policy]
        q = sum(r.stage0_action is Action.QUERY_COMPLEMENT for r in rs)
        premature = sum(r.stage0_action is Action.ACT_ANSWER for r in rs)
        em = sum(
            hybridqa_exact_match(r.post_query_answer or "", r.gold_answer)
            if r.stage0_action is Action.QUERY_COMPLEMENT else 0
            for r in rs
        )
        u = _usage(rs)
        return {
            "necessary_query_recall": _rate(q, len(rs)),
            "premature_answer_rate": _rate(premature, len(rs)),
            "post_query_em": _rate(em, len(rs)),
            "query_units": u.external_query_units,
            "model_forward_calls": u.model_forward_calls,
            "total_tokens": u.total_tokens,
        }

    all_metrics = {p: metrics(p) for p in REQUIRED_POLICIES}
    cand = all_metrics["DECISION_RELEVANT"]
    always_q = all_metrics["ALWAYS_QUERY"]
    mm = all_metrics["MAX_SCORE_MARGIN"]

    cand_pair = (float(cand["premature_answer_rate"]), int(cand["query_units"]))
    mm_pair = (float(mm["premature_answer_rate"]), int(mm["query_units"]))

    direct_eligible: dict[str, bool] = {}
    direct_matched: dict[str, bool] = {}
    for policy in ("MAX_SCORE_MARGIN", "MODEL_ID_MAXIMIN"):
        comp = all_metrics[policy]
        eligible = float(comp["necessary_query_recall"]) >= 0.90
        direct_eligible[policy] = eligible
        direct_matched[policy] = eligible and (
            int(cand["query_units"]) <= int(comp["query_units"])
            and int(cand["model_forward_calls"]) <= int(comp["model_forward_calls"])
            and int(cand["total_tokens"]) <= int(comp["total_tokens"])
        )

    endpoints = {
        "necessary_query_recall": float(cand["necessary_query_recall"]) >= 0.90,
        "premature_answer_rate": float(cand["premature_answer_rate"]) <= 0.05,
        "post_query_em_noninferior": float(cand["post_query_em"]) >= float(always_q["post_query_em"]) - 0.02,
        "query_units_le_always_query": int(cand["query_units"]) <= int(always_q["query_units"]),
        "beats_max_margin_ordered_pair": cand_pair < mm_pair,
        "max_margin_em_noninferior": float(cand["post_query_em"]) >= float(mm["post_query_em"]) - 0.02,
        "direct_comparator_eligible_max_margin": direct_eligible["MAX_SCORE_MARGIN"],
        "direct_comparator_eligible_model_id": direct_eligible["MODEL_ID_MAXIMIN"],
        "matched_max_score_margin": direct_matched["MAX_SCORE_MARGIN"],
        "matched_model_id_maximin": direct_matched["MODEL_ID_MAXIMIN"],
    }
    failed = tuple(k for k, ok in endpoints.items() if not ok)
    flattened: dict[str, float | int | str | bool | None] = {}
    for policy, vals in all_metrics.items():
        for name, value in vals.items():
            flattened[f"{policy}.{name}"] = value
    return GateResult(not failed, endpoints, flattened, failed)
