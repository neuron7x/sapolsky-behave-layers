from __future__ import annotations

import hashlib
import math
import random
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass

from cwc.epistemics.information_acquisition import (
    InformationAction,
    select_decision_relevant_information_action,
    select_maximin_information_action,
)
from cwc.replay.passive_identifiability import binary_kl

ALPHA = 0.01
TARGET_POWER = 0.95
REQUIRED_INFORMATION_NATS = binary_kl(TARGET_POWER, ALPHA)

ROBUST_STATE = "ROBUST_ACTION_CAUSAL_WORLD_UNRESOLVED"
QUERY_STATE = "QUERY_CAN_RESOLVE_ACTION"
ABSTAIN_STATE = "ACTION_UNIDENTIFIED_NO_INFORMATION_CHANNEL"
REJECT_STATE = "OBSERVABLE_MODEL_OR_ASSUMPTION_FALSIFIED"
INTERVENTION_STATE = "INTERVENTION_SUPPORTED_SCOPED_ACTION"

ROBUST_SCOPE = "ROBUST_DECISION_ONLY_CAUSAL_WORLD_UNRESOLVED"
INTERVENTION_SCOPE = "INTERVENTION_SUPPORTED_OPERATOR_SCOPED"


@dataclass(frozen=True, slots=True)
class CabQuery:
    query_id: str
    unit_cost: float
    information_rate_lower_bounds: Mapping[str, float]
    rate_certificate: str
    full_model_information_score: float
    predictive_uncertainty: float
    max_units: int

    def __post_init__(self) -> None:
        if len(self.query_id) != 4:
            raise ValueError("query_id must be fixed-width")
        if not math.isfinite(self.unit_cost) or self.unit_cost <= 0:
            raise ValueError("unit_cost must be finite and positive")
        if self.max_units < 1:
            raise ValueError("max_units must be positive")
        if not (0 <= self.predictive_uncertainty <= 1):
            raise ValueError("predictive_uncertainty must be in [0,1]")
        if not math.isfinite(self.full_model_information_score) or self.full_model_information_score < 0:
            raise ValueError("full_model_information_score must be finite and non-negative")
        if len(self.information_rate_lower_bounds) != 2:
            raise ValueError("CAB-01-Q1 requires exactly two alternative-world rates")

    def as_information_action(self) -> InformationAction:
        return InformationAction(
            action_id=self.query_id,
            unit_cost=self.unit_cost,
            information_rate_lower_bounds=self.information_rate_lower_bounds,
            rate_certificate=self.rate_certificate,
            max_units=self.max_units,
        )


@dataclass(frozen=True, slots=True)
class CabTask:
    opaque_id: str
    candidate_action: str
    alternative_decisions: Mapping[str, str]
    queries: tuple[CabQuery, CabQuery]
    available_budget: float
    decision_loss_value: float
    observed_falsification: bool
    rejection_target: str
    intervention_supported: bool
    intervention_action: str

    def __post_init__(self) -> None:
        if len(self.opaque_id) != 16:
            raise ValueError("opaque_id must be fixed-width")
        if tuple(sorted(self.alternative_decisions)) != ("M000", "M001"):
            raise ValueError("CAB-01-Q1 requires M000/M001 alternatives")
        if len(self.queries) != 2 or tuple(q.query_id for q in self.queries) != ("Q000", "Q001"):
            raise ValueError("CAB-01-Q1 requires Q000/Q001 in canonical order")
        for q in self.queries:
            if set(q.information_rate_lower_bounds) != set(self.alternative_decisions):
                raise ValueError("query rate vector must cover both admitted alternatives")
        if not math.isfinite(self.available_budget) or self.available_budget < 0:
            raise ValueError("available_budget must be finite and non-negative")
        if not math.isfinite(self.decision_loss_value) or self.decision_loss_value < 0:
            raise ValueError("decision_loss_value must be finite and non-negative")
        if len(self.rejection_target) != 4:
            raise ValueError("rejection_target must be fixed-width")


@dataclass(frozen=True, slots=True)
class CabDecision:
    kind: str
    action_id: str | None = None
    authority_scope: str | None = None
    query_id: str | None = None
    target_id: str | None = None
    reason: str = ""
    committed_before_terminal: bool = False

    def __post_init__(self) -> None:
        if self.kind not in {"ACT", "QUERY", "ABSTAIN", "REJECT_MODEL"}:
            raise ValueError(f"unsupported terminal kind: {self.kind}")
        if self.kind == "ACT" and (not self.action_id or not self.authority_scope):
            raise ValueError("ACT requires action_id and authority_scope")
        if self.kind == "QUERY" and not self.query_id:
            raise ValueError("QUERY requires query_id")
        if self.kind == "REJECT_MODEL" and not self.target_id:
            raise ValueError("REJECT_MODEL requires target_id")


@dataclass(frozen=True, slots=True)
class CabCase:
    family: str
    cohort: str
    seed: int
    mutation_group: str
    expected_state: str
    task: CabTask
    construction_label: CabDecision


def _opaque_id(seed: int, variant: str) -> str:
    return hashlib.sha256(f"CAB01Q1:{seed}:{variant}".encode()).hexdigest()[:16]


def _q(
    query_id: str,
    cost: float,
    r0: float,
    r1: float,
    *,
    model_info: float,
    uncertainty: float,
    max_units: int = 512,
    cert: str = "CERTIFIED_LOWER_BOUND",
) -> CabQuery:
    return CabQuery(
        query_id=query_id,
        unit_cost=cost,
        information_rate_lower_bounds={"M000": r0, "M001": r1},
        rate_certificate=cert,
        full_model_information_score=model_info,
        predictive_uncertainty=uncertainty,
        max_units=max_units,
    )


def _decision(
    kind: str,
    *,
    action: str | None = None,
    scope: str | None = None,
    query: str | None = None,
    target: str | None = None,
    reason: str,
) -> CabDecision:
    return CabDecision(
        kind=kind, action_id=action, authority_scope=scope, query_id=query, target_id=target, reason=reason
    )


def _base_task(
    seed: int,
    variant: str,
    *,
    decisions: tuple[str, str],
    queries: tuple[CabQuery, CabQuery],
    budget: float = 50.0,
    decision_loss: float = 50.0,
    falsified: bool = False,
    rejection_target: str = "T000",
    intervention: bool = False,
    intervention_action: str = "A000",
) -> CabTask:
    return CabTask(
        opaque_id=_opaque_id(seed, variant),
        candidate_action="A000",
        alternative_decisions={"M000": decisions[0], "M001": decisions[1]},
        queries=queries,
        available_budget=budget,
        decision_loss_value=decision_loss,
        observed_falsification=falsified,
        rejection_target=rejection_target,
        intervention_supported=intervention,
        intervention_action=intervention_action,
    )


def generate_case(family: str, cohort: str, seed: int, *, variant: str = "S") -> CabCase:
    """Generate one frozen CAB-01-Q1 case without exposing the hidden family to policies."""
    if family not in {f"F{i}" for i in range(12)}:
        raise KeyError(family)
    rng = random.Random(seed * 37 + sum(ord(c) for c in variant))

    def jitter(lo, hi):
        return rng.uniform(lo, hi)

    generic = (
        _q(
            "Q000",
            1.0,
            jitter(0.03, 0.08),
            jitter(0.03, 0.08),
            model_info=jitter(0.2, 0.4),
            uncertainty=jitter(0.2, 0.5),
        ),
        _q(
            "Q001",
            1.2,
            jitter(0.03, 0.08),
            jitter(0.03, 0.08),
            model_info=jitter(0.2, 0.4),
            uncertainty=jitter(0.2, 0.5),
        ),
    )
    group = _opaque_id(seed, "GROUP")[:12]

    if family == "F0":
        task = _base_task(seed, variant, decisions=("A000", "A000"), queries=generic)
        state = ROBUST_STATE
        label = _decision(
            "ACT", action="A000", scope=ROBUST_SCOPE, reason="all admitted worlds agree on immediate action"
        )
    elif family == "F1":
        qs = (
            _q("Q000", 1.0, 0.04, jitter(0.30, 0.40), model_info=0.25, uncertainty=0.55),
            _q("Q001", 1.0, 0.04, jitter(0.04, 0.07), model_info=0.60, uncertainty=0.62),
        )
        task = _base_task(seed, variant, decisions=("A000", "A001"), queries=qs)
        state = QUERY_STATE
        label = _decision("QUERY", query="Q000", reason="cheap certified query resolves action-flipping world")
    elif family == "F2":
        qs = (
            _q("Q000", 1.0, 0.30, 0.0, model_info=0.50, uncertainty=0.80),
            _q("Q001", 1.0, 0.40, 0.0, model_info=0.60, uncertainty=0.90),
        )
        task = _base_task(seed, variant, decisions=("A000", "A001"), queries=qs, budget=100.0)
        state = ABSTAIN_STATE
        label = _decision("ABSTAIN", reason="action-flipping alternative has zero admitted information")
    elif family == "F3":
        qs = (
            _q("Q000", 1.0, jitter(0.20, 0.40), 0.0, model_info=0.75, uncertainty=0.68),
            _q("Q001", 1.0, jitter(0.20, 0.40), 0.0, model_info=0.80, uncertainty=0.72),
        )
        task = _base_task(seed, variant, decisions=("A000", "A001"), queries=qs, budget=100.0)
        state = ABSTAIN_STATE
        label = _decision("ABSTAIN", reason="confounder/topology alternatives are equivalent under admitted channels")
    elif family == "F4":
        qs = (
            _q("Q000", 1.0, 0.08, 0.09, model_info=0.70, uncertainty=jitter(0.92, 0.99)),
            _q("Q001", 1.0, 0.06, 0.07, model_info=0.60, uncertainty=jitter(0.88, 0.96)),
        )
        task = _base_task(seed, variant, decisions=("A000", "A000"), queries=qs)
        state = ROBUST_STATE
        label = _decision(
            "ACT", action="A000", scope=ROBUST_SCOPE, reason="aleatoric uncertainty does not alter robust decision"
        )
    elif family == "F5":
        task = _base_task(
            seed, variant, decisions=("A000", "A001"), queries=generic, intervention=True, intervention_action="A001"
        )
        state = INTERVENTION_STATE
        label = _decision(
            "ACT", action="A001", scope=INTERVENTION_SCOPE, reason="direct intervention supports scoped action"
        )
    elif family == "F6":
        task = _base_task(
            seed, variant, decisions=("A000", "A001"), queries=generic, falsified=True, rejection_target="AASM"
        )
        state = REJECT_STATE
        label = _decision("REJECT_MODEL", target="AASM", reason="negative control falsifies identifying assumption")
    elif family == "F7":
        task = _base_task(
            seed, variant, decisions=("A000", "A000"), queries=generic, falsified=True, rejection_target="EVID"
        )
        state = REJECT_STATE
        label = _decision("REJECT_MODEL", target="EVID", reason="provenance corruption invalidates evidence authority")
    elif family == "F8":
        qs = (
            _q("Q000", 1.0, jitter(0.42, 0.55), jitter(0.09, 0.12), model_info=jitter(0.85, 0.95), uncertainty=0.70),
            _q("Q001", 1.0, jitter(0.008, 0.015), jitter(0.22, 0.28), model_info=jitter(0.30, 0.40), uncertainty=0.62),
        )
        task = _base_task(seed, variant, decisions=("A000", "A001"), queries=qs, budget=50.0, decision_loss=50.0)
        state = QUERY_STATE
        label = _decision(
            "QUERY", query="Q001", reason="decision-relevant query beats higher model-information distractor"
        )
    elif family == "F9":
        rate = jitter(0.19, 0.24)
        qs = (
            _q("Q000", 1.0, 0.03, rate, model_info=0.50, uncertainty=0.60),
            _q("Q001", 1.4, 0.04, rate * 0.95, model_info=0.55, uncertainty=0.65),
        )
        task = _base_task(seed, variant, decisions=("A000", "A001"), queries=qs, budget=30.0, decision_loss=30.0)
        state = QUERY_STATE
        label = _decision("QUERY", query="Q000", reason="necessary query cost is below budget and decision loss")
    elif family == "F10":
        qs = (
            _q("Q000", 2.5, 0.03, jitter(0.085, 0.105), model_info=0.65, uncertainty=0.75),
            _q("Q001", 3.0, 0.04, jitter(0.09, 0.11), model_info=0.70, uncertainty=0.80),
        )
        task = _base_task(seed, variant, decisions=("A000", "A001"), queries=qs, budget=20.0, decision_loss=20.0)
        state = ABSTAIN_STATE
        label = _decision("ABSTAIN", reason="necessary information cost exceeds admitted value/budget")
    else:  # F11 surface-preserving ACT / QUERY / ABSTAIN triad
        if variant == "A":
            decisions = ("A000", "A000")
            q1 = jitter(0.22, 0.28)
            state = ROBUST_STATE
            label = _decision("ACT", action="A000", scope=ROBUST_SCOPE, reason="paired mutation: same-decision cell")
        elif variant == "Q":
            decisions = ("A000", "A001")
            q1 = jitter(0.22, 0.28)
            state = QUERY_STATE
            label = _decision("QUERY", query="Q000", reason="paired mutation: affordable decisive channel")
        elif variant == "B":
            decisions = ("A000", "A001")
            q1 = 0.0
            state = ABSTAIN_STATE
            label = _decision("ABSTAIN", reason="paired mutation: no decision-identifying channel")
        else:
            raise ValueError("F11 variant must be A/Q/B")
        qs = (
            _q("Q000", 1.0, 0.05, q1, model_info=0.55, uncertainty=0.65),
            _q("Q001", 1.0, 0.05, 0.0 if variant == "B" else q1 * 0.50, model_info=0.58, uncertainty=0.66),
        )
        # opaque id differs, but surface leakage uses shape only; mutation_group binds the triad.
        task = _base_task(seed, variant, decisions=decisions, queries=qs, budget=30.0, decision_loss=30.0)

    return CabCase(
        family=family,
        cohort=cohort,
        seed=seed,
        mutation_group=group,
        expected_state=state,
        task=task,
        construction_label=label,
    )


def generate_cohort(cohort: str, seed_base: int, n: int = 128) -> tuple[CabCase, ...]:
    cases: list[CabCase] = []
    for fi in range(11):
        family = f"F{fi}"
        for i in range(n):
            cases.append(generate_case(family, cohort, seed_base + fi * 1000 + i))
    for i in range(n):
        seed = seed_base + 11 * 1000 + i
        for variant in ("A", "Q", "B"):
            cases.append(generate_case("F11", cohort, seed, variant=variant))
    return tuple(cases)


def _analytic_best_query(task: CabTask) -> str | None:
    cross = tuple(m for m, decision in task.alternative_decisions.items() if decision != task.candidate_action)
    if not cross:
        return None
    best: tuple[float, float, str, float] | None = None
    for q in task.queries:
        if q.rate_certificate != "CERTIFIED_LOWER_BOUND":
            continue
        if any(m not in q.information_rate_lower_bounds for m in cross):
            continue
        min_rate = min(float(q.information_rate_lower_bounds[m]) for m in cross)
        ratio = min_rate / q.unit_cost
        capacity_cost = q.max_units * q.unit_cost
        candidate = (ratio, -q.unit_cost, q.query_id, capacity_cost)
        if best is None or candidate[:3] > best[:3]:
            best = candidate
    if best is None or best[0] <= 0:
        return None
    ratio, _, query_id, capacity_cost = best
    necessary_cost = REQUIRED_INFORMATION_NATS / ratio
    if necessary_cost > capacity_cost:
        return None
    if necessary_cost > task.available_budget or necessary_cost > task.decision_loss_value:
        return None
    return query_id


def analytic_oracle(task: CabTask) -> tuple[str, CabDecision]:
    """Independent closed-form label path; deliberately does not call CWC governors."""
    if task.observed_falsification:
        return REJECT_STATE, _decision("REJECT_MODEL", target=task.rejection_target, reason="observed falsifier")
    if task.intervention_supported:
        return INTERVENTION_STATE, _decision(
            "ACT", action=task.intervention_action, scope=INTERVENTION_SCOPE, reason="scoped intervention support"
        )
    decisions = tuple(task.alternative_decisions.values())
    if all(d == task.candidate_action for d in decisions):
        return ROBUST_STATE, _decision(
            "ACT", action=task.candidate_action, scope=ROBUST_SCOPE, reason="decision invariant across admitted worlds"
        )
    query = _analytic_best_query(task)
    if query is not None:
        return QUERY_STATE, _decision(
            "QUERY", query=query, reason="analytic decision-information converse permits query"
        )
    return ABSTAIN_STATE, _decision("ABSTAIN", reason="action unresolved under admitted information/cost constraints")


def runtime_oracle(task: CabTask) -> tuple[str, CabDecision]:
    """Runtime label path using the supported CWC decision-information governor."""
    if task.observed_falsification:
        return REJECT_STATE, _decision("REJECT_MODEL", target=task.rejection_target, reason="observed falsifier")
    if task.intervention_supported:
        return INTERVENTION_STATE, _decision(
            "ACT", action=task.intervention_action, scope=INTERVENTION_SCOPE, reason="scoped intervention support"
        )
    result = select_decision_relevant_information_action(
        actions=[q.as_information_action() for q in task.queries],
        candidate_decision=task.candidate_action,
        alternative_decisions=task.alternative_decisions,
        alpha=ALPHA,
        target_power=TARGET_POWER,
        available_budget=min(task.available_budget, task.decision_loss_value),
    )
    if result.state == "DECISION_ALREADY_IDENTIFIED_NO_ACQUISITION":
        return ROBUST_STATE, _decision(
            "ACT", action=task.candidate_action, scope=ROBUST_SCOPE, reason="runtime decision invariant"
        )
    if result.state == "ACQUIRE_DECISION_RELEVANT_EVIDENCE_BUDGET_NOT_RULED_OUT_BY_CONVERSE":
        return QUERY_STATE, _decision("QUERY", query=result.action_id, reason="runtime decision-information query")
    return ABSTAIN_STATE, _decision("ABSTAIN", reason=f"runtime veto: {result.state}")


def _predecision_guard(task: CabTask) -> CabDecision | None:
    if task.observed_falsification:
        return _decision("REJECT_MODEL", target=task.rejection_target, reason="guarded observed falsifier")
    if task.intervention_supported:
        return _decision(
            "ACT",
            action=task.intervention_action,
            scope=INTERVENTION_SCOPE,
            reason="guarded scoped intervention support",
        )
    return None


def policy_always_act(task: CabTask, _: int = 0) -> CabDecision:
    return _decision("ACT", action=task.candidate_action, scope=ROBUST_SCOPE, reason="constant act")


def policy_always_abstain(task: CabTask, _: int = 0) -> CabDecision:
    return _decision("ABSTAIN", reason="constant abstain")


def policy_random_valid(task: CabTask, seed: int = 0) -> CabDecision:
    digest = hashlib.sha256(f"{task.opaque_id}:{seed}".encode()).digest()[0] % 4
    if digest == 0:
        return _decision("ACT", action=task.candidate_action, scope=ROBUST_SCOPE, reason="deterministic random")
    if digest == 1:
        return _decision("ABSTAIN", reason="deterministic random")
    if digest == 2:
        q = task.queries[hashlib.sha256(task.opaque_id.encode()).digest()[1] % 2]
        return _decision("QUERY", query=q.query_id, reason="deterministic random")
    return _decision("REJECT_MODEL", target=task.rejection_target, reason="deterministic random")


def policy_generic_uncertainty(task: CabTask, _: int = 0) -> CabDecision:
    guard = _predecision_guard(task)
    if guard is not None:
        return guard
    q = max(task.queries, key=lambda x: (x.predictive_uncertainty, -x.unit_cost, x.query_id))
    if q.predictive_uncertainty >= 0.75 and q.unit_cost <= task.available_budget:
        return _decision("QUERY", query=q.query_id, reason="generic predictive uncertainty")
    return _decision(
        "ACT", action=task.candidate_action, scope=ROBUST_SCOPE, reason="generic uncertainty below threshold"
    )


def policy_full_model_maximin(task: CabTask, _: int = 0) -> CabDecision:
    guard = _predecision_guard(task)
    if guard is not None:
        return guard
    if len(set(task.alternative_decisions.values())) == 1:
        return _decision("ACT", action=task.candidate_action, scope=ROBUST_SCOPE, reason="all worlds agree")
    result = select_maximin_information_action(
        actions=[q.as_information_action() for q in task.queries],
        unresolved_alternatives=tuple(task.alternative_decisions),
        alpha=ALPHA,
        target_power=TARGET_POWER,
        available_budget=min(task.available_budget, task.decision_loss_value),
    )
    if result.state == "ACQUIRE_EVIDENCE_BUDGET_NOT_RULED_OUT_BY_CONVERSE":
        return _decision("QUERY", query=result.action_id, reason="full-model maximin information")
    return _decision("ABSTAIN", reason=f"full-model veto: {result.state}")


def policy_decision_relevant(task: CabTask, _: int = 0) -> CabDecision:
    return runtime_oracle(task)[1]


def policy_robust_no_query(task: CabTask, _: int = 0) -> CabDecision:
    guard = _predecision_guard(task)
    if guard is not None:
        return guard
    if all(d == task.candidate_action for d in task.alternative_decisions.values()):
        return _decision(
            "ACT", action=task.candidate_action, scope=ROBUST_SCOPE, reason="worst-case decision invariant"
        )
    return _decision("ABSTAIN", reason="worst-case policy refuses unresolved action")


def policy_oracle(case: CabCase, _: int = 0) -> CabDecision:
    return case.construction_label


POLICIES = {
    "always_act": policy_always_act,
    "always_abstain": policy_always_abstain,
    "random_valid": policy_random_valid,
    "generic_predictive_uncertainty": policy_generic_uncertainty,
    "full_model_maximin": policy_full_model_maximin,
    "decision_relevant_information": policy_decision_relevant,
    "robust_worst_case_no_query": policy_robust_no_query,
}


def decisions_equal(a: CabDecision, b: CabDecision) -> bool:
    if a.kind != b.kind:
        return False
    if a.kind == "ACT":
        return a.action_id == b.action_id and a.authority_scope == b.authority_scope
    if a.kind == "QUERY":
        return a.query_id == b.query_id
    if a.kind == "REJECT_MODEL":
        return a.target_id == b.target_id
    return True


def surface_signature(task: CabTask) -> tuple[object, ...]:
    """Serialization-shape-only leakage feature vector; values are intentionally hidden."""
    return (
        "CabTask",
        9,
        len(task.opaque_id),
        len(task.candidate_action),
        len(task.alternative_decisions),
        tuple(sorted((len(k), len(v)) for k, v in task.alternative_decisions.items())),
        len(task.queries),
        tuple(
            (
                "CabQuery",
                len(q.query_id),
                len(q.information_rate_lower_bounds),
                tuple(sorted(len(k) for k in q.information_rate_lower_bounds)),
                type(q.unit_cost).__name__,
                type(q.full_model_information_score).__name__,
                type(q.predictive_uncertainty).__name__,
                type(q.max_units).__name__,
                type(q.rate_certificate).__name__,
            )
            for q in task.queries
        ),
        type(task.available_budget).__name__,
        type(task.decision_loss_value).__name__,
        type(task.observed_falsification).__name__,
        len(task.rejection_target),
        type(task.intervention_supported).__name__,
        len(task.intervention_action),
    )


def query_cost(task: CabTask, decision: CabDecision) -> float:
    if decision.kind != "QUERY" or decision.query_id is None:
        return 0.0
    for q in task.queries:
        if q.query_id == decision.query_id:
            return q.unit_cost
    return math.inf


def score_policy(cases: Sequence[CabCase], outputs: Sequence[CabDecision]) -> dict[str, float | int]:
    if len(cases) != len(outputs):
        raise ValueError("cases/outputs length mismatch")
    n = len(cases)
    robust_cases = [i for i, c in enumerate(cases) if c.expected_state == ROBUST_STATE]
    query_cases = [i for i, c in enumerate(cases) if c.expected_state == QUERY_STATE]
    abstain_cases = [i for i, c in enumerate(cases) if c.expected_state == ABSTAIN_STATE]
    reject_cases = [i for i, c in enumerate(cases) if c.expected_state == REJECT_STATE]
    intervention_cases = [i for i, c in enumerate(cases) if c.expected_state == INTERVENTION_STATE]

    false_authority = 0
    wrong_act = 0
    posthoc = 0
    total_query_cost = 0.0
    unnecessary_query_cost = 0.0
    emitted_rejects = 0
    correct_rejects = 0
    terminal_correct = 0
    for _i, (case, out) in enumerate(zip(cases, outputs, strict=False)):
        exp = case.construction_label
        exact = decisions_equal(out, exp)
        terminal_correct += int(exact)
        if out.kind == "ACT" and not exact:
            false_authority += 1
            wrong_act += 1
        if out.committed_before_terminal and out.kind == "ABSTAIN":
            posthoc += 1
        qc = query_cost(case.task, out)
        total_query_cost += qc
        if out.kind == "QUERY" and exp.kind != "QUERY":
            unnecessary_query_cost += qc
        if out.kind == "REJECT_MODEL":
            emitted_rejects += 1
            correct_rejects += int(exact)

    def rate(indices: Sequence[int], predicate) -> float:
        if not indices:
            return 1.0
        return sum(1 for i in indices if predicate(i)) / len(indices)

    metrics: dict[str, float | int] = {
        "n": n,
        "false_causal_authority_rate": false_authority / n if n else 0.0,
        "wrong_irreversible_action_rate": wrong_act / n if n else 0.0,
        "correct_robust_action_rate": rate(
            robust_cases, lambda i: decisions_equal(outputs[i], cases[i].construction_label)
        ),
        "necessary_query_recall": rate(query_cases, lambda i: decisions_equal(outputs[i], cases[i].construction_label)),
        "unnecessary_query_cost": unnecessary_query_cost / n if n else 0.0,
        "no_information_abstention_accuracy": rate(abstain_cases, lambda i: outputs[i].kind == "ABSTAIN"),
        "model_assumption_rejection_precision": correct_rejects / emitted_rejects if emitted_rejects else 1.0,
        "post_hoc_abstention_rate": posthoc / n if n else 0.0,
        "total_query_cost": total_query_cost / n if n else 0.0,
        "coverage": 1.0 if n else 0.0,
        "terminal_accuracy": terminal_correct / n if n else 0.0,
        "rejection_recall": rate(reject_cases, lambda i: decisions_equal(outputs[i], cases[i].construction_label)),
        "intervention_scoped_action_accuracy": rate(
            intervention_cases, lambda i: decisions_equal(outputs[i], cases[i].construction_label)
        ),
    }
    return metrics


ERROR_COST_METRICS = {
    "false_causal_authority_rate",
    "wrong_irreversible_action_rate",
    "unnecessary_query_cost",
    "post_hoc_abstention_rate",
    "total_query_cost",
}
SUCCESS_METRICS = {
    "correct_robust_action_rate",
    "necessary_query_recall",
    "no_information_abstention_accuracy",
    "model_assumption_rejection_precision",
    "coverage",
}
PRIMARY_METRICS = tuple(sorted(ERROR_COST_METRICS | SUCCESS_METRICS))


def pareto_dominates(a: Mapping[str, float | int], b: Mapping[str, float | int], *, eps: float = 1e-12) -> bool:
    no_worse = True
    strict = False
    for key in PRIMARY_METRICS:
        av = float(a[key])
        bv = float(b[key])
        if key in ERROR_COST_METRICS:
            if av > bv + eps:
                no_worse = False
            if av < bv - eps:
                strict = True
        else:
            if av < bv - eps:
                no_worse = False
            if av > bv + eps:
                strict = True
    return no_worse and strict


def serialize_case(case: CabCase) -> dict[str, object]:
    return {
        "family": case.family,
        "cohort": case.cohort,
        "seed": case.seed,
        "mutation_group": case.mutation_group,
        "expected_state": case.expected_state,
        "task": asdict(case.task),
        "construction_label": asdict(case.construction_label),
        "surface_signature": surface_signature(case.task),
    }


def validate_f11_triads(cases: Iterable[CabCase]) -> tuple[bool, list[str]]:
    groups: dict[tuple[str, str], list[CabCase]] = {}
    for case in cases:
        if case.family == "F11":
            groups.setdefault((case.cohort, case.mutation_group), []).append(case)
    errors: list[str] = []
    for key, group in sorted(groups.items()):
        if len(group) != 3:
            errors.append(f"{key}: expected 3 variants, got {len(group)}")
            continue
        kinds = sorted(c.construction_label.kind for c in group)
        if kinds != ["ABSTAIN", "ACT", "QUERY"]:
            errors.append(f"{key}: wrong terminal triad {kinds}")
        signatures = {surface_signature(c.task) for c in group}
        if len(signatures) != 1:
            errors.append(f"{key}: surface signature changed")
    return not errors, errors
