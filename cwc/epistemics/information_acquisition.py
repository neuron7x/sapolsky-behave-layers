from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from cwc.replay.passive_identifiability import binary_kl


@dataclass(frozen=True, slots=True)
class InformationAction:
    """One admissible evidence-acquisition operation.

    `information_rate_lower_bounds` is indexed by unresolved alternative/model id and
    is measured in nats per acquisition unit.  Only certified lower bounds may approve
    additional compute.  Point estimates may be logged elsewhere but are deliberately
    not accepted by this fail-closed governor.
    """

    action_id: str
    unit_cost: float
    information_rate_lower_bounds: Mapping[str, float]
    rate_certificate: str
    max_units: int | None = None

    def __post_init__(self) -> None:
        if not self.action_id:
            raise ValueError("action_id required")
        if not math.isfinite(self.unit_cost) or self.unit_cost <= 0:
            raise ValueError("unit_cost must be finite and >0")
        if not self.information_rate_lower_bounds:
            raise ValueError("at least one alternative information rate required")
        for value in self.information_rate_lower_bounds.values():
            if not math.isfinite(value) or value < 0:
                raise ValueError("information rates must be finite and non-negative")
        if self.max_units is not None and self.max_units < 1:
            raise ValueError("max_units must be positive")


@dataclass(frozen=True, slots=True)
class InformationAcquisitionDecision:
    state: str
    action_id: str | None
    required_information_nats: float
    guaranteed_information_per_cost: float
    necessary_cost_lower_bound: float
    available_budget: float
    bottleneck_alternatives: tuple[str, ...]
    reason: str


def select_maximin_information_action(
    *,
    actions: Sequence[InformationAction],
    unresolved_alternatives: Sequence[str],
    alpha: float,
    target_power: float,
    available_budget: float,
) -> InformationAcquisitionDecision:
    """Choose the cheapest robust falsification channel by certified information/cost.

    For a level-alpha decision with target power p, data processing gives the
    necessary information requirement kl(p||alpha).  If action a has a certified
    lower bound R_{m,a} nats/unit against each unresolved alternative m and costs
    c_a/unit, its robust information-per-cost guarantee is

        q_a = min_m R_{m,a} / c_a.

    The governor chooses argmax q_a.  The resulting cost kl/q_a is only a necessary
    lower bound, not a sufficient sample-complexity guarantee.  A zero maximin rate
    means at least one alternative remains observationally equivalent under every
    admitted action, so more compute is rejected rather than treated as evidence.
    """
    if not (0 < alpha < target_power < 1):
        raise ValueError("require 0 < alpha < target_power < 1")
    if not math.isfinite(available_budget) or available_budget < 0:
        raise ValueError("available_budget must be finite and >=0")
    alternatives = tuple(dict.fromkeys(str(x) for x in unresolved_alternatives))
    if not alternatives:
        raise ValueError("at least one unresolved alternative required")
    required = binary_kl(target_power, alpha)

    eligible: list[tuple[float, InformationAction, tuple[str, ...], float]] = []
    uncertified = False
    for action in actions:
        if action.rate_certificate != "CERTIFIED_LOWER_BOUND":
            uncertified = True
            continue
        missing = [m for m in alternatives if m not in action.information_rate_lower_bounds]
        if missing:
            continue
        rates = {m: float(action.information_rate_lower_bounds[m]) for m in alternatives}
        min_rate = min(rates.values())
        bottlenecks = tuple(sorted(m for m, v in rates.items() if abs(v - min_rate) <= 1e-15))
        q = min_rate / action.unit_cost
        max_total_cost = math.inf if action.max_units is None else action.max_units * action.unit_cost
        eligible.append((q, action, bottlenecks, max_total_cost))

    if not eligible:
        return InformationAcquisitionDecision(
            "NO_CERTIFIED_INFORMATION_RATE",
            None,
            required,
            0.0,
            math.inf,
            available_budget,
            alternatives,
            "No action has a complete certified lower-bound rate vector for the unresolved equivalence class."
            if not uncertified
            else "Only uncertified/partial information-rate estimates are available.",
        )

    eligible.sort(key=lambda t: (-t[0], t[1].unit_cost, t[1].action_id))
    q, action, bottlenecks, action_capacity_cost = eligible[0]
    if q <= 0:
        return InformationAcquisitionDecision(
            "NO_IDENTIFYING_INFORMATION_CHANNEL",
            action.action_id,
            required,
            0.0,
            math.inf,
            available_budget,
            bottlenecks,
            "At least one unresolved alternative has zero certified information rate under every admissible action.",
        )

    necessary_cost = required / q
    if necessary_cost > action_capacity_cost:
        return InformationAcquisitionDecision(
            "ACTION_CAPACITY_BELOW_NECESSARY_INFORMATION_BOUND",
            action.action_id,
            required,
            q,
            necessary_cost,
            available_budget,
            bottlenecks,
            "The action cannot supply enough units even to satisfy the information-theoretic necessary condition.",
        )
    if available_budget < necessary_cost:
        return InformationAcquisitionDecision(
            "INSUFFICIENT_INFORMATION_BUDGET",
            action.action_id,
            required,
            q,
            necessary_cost,
            available_budget,
            bottlenecks,
            "Available compute/acquisition budget is below a necessary information bound; scaling is vetoed.",
        )
    return InformationAcquisitionDecision(
        "ACQUIRE_EVIDENCE_BUDGET_NOT_RULED_OUT_BY_CONVERSE",
        action.action_id,
        required,
        q,
        necessary_cost,
        available_budget,
        bottlenecks,
        "Chosen by maximin certified information-per-cost. This is a spend permission, not a correctness guarantee.",
    )


@dataclass(frozen=True, slots=True)
class DecisionRelevantInformationDecision:
    """Fail-closed spend decision on the quotient induced by the current action.

    This object intentionally distinguishes *model* uncertainty from *decision*
    uncertainty. Same-decision alternatives remain epistemically unresolved and are
    recorded, but they cannot become a bottleneck for an information spend whose only
    declared purpose is resolving the immediate action choice.
    """

    state: str
    action_id: str | None
    candidate_decision: str
    required_information_nats: float
    guaranteed_information_per_cost: float
    necessary_cost_lower_bound: float
    available_budget: float
    cross_decision_alternatives: tuple[str, ...]
    ignored_same_decision_alternatives: tuple[str, ...]
    bottleneck_alternatives: tuple[str, ...]
    reason: str


def select_decision_relevant_information_action(
    *,
    actions: Sequence[InformationAction],
    candidate_decision: str,
    alternative_decisions: Mapping[str, str],
    alpha: float,
    target_power: float,
    available_budget: float,
) -> DecisionRelevantInformationDecision:
    """Choose evidence only for distinctions that can change the immediate decision.

    Let g(m) be the predeclared optimal-action/decision class under surviving model m.
    Alternatives with g(m)==g(candidate) remain unresolved causal countermodels, but
    identifying them has zero value for deciding *which immediate action* to take.

    This function therefore computes the maximin certified information-per-cost only
    over cross-decision alternatives.  It is a decision-identification governor, not a
    causal-model identification procedure.  The KL cost calculation remains a
    necessary converse only and can license spend, never causal truth.
    """
    if not candidate_decision or not str(candidate_decision).strip():
        raise ValueError("candidate_decision required")
    if not (0 < alpha < target_power < 1):
        raise ValueError("require 0 < alpha < target_power < 1")
    if not math.isfinite(available_budget) or available_budget < 0:
        raise ValueError("available_budget must be finite and >=0")

    normalized = {str(k): str(v) for k, v in alternative_decisions.items()}
    if any(not k or not v for k, v in normalized.items()):
        raise ValueError("alternative ids and decisions must be non-empty")

    cross = tuple(sorted(k for k, v in normalized.items() if v != candidate_decision))
    same = tuple(sorted(k for k, v in normalized.items() if v == candidate_decision))
    required = binary_kl(target_power, alpha)

    if not cross:
        return DecisionRelevantInformationDecision(
            state="DECISION_ALREADY_IDENTIFIED_NO_ACQUISITION",
            action_id=None,
            candidate_decision=candidate_decision,
            required_information_nats=required,
            guaranteed_information_per_cost=math.inf,
            necessary_cost_lower_bound=0.0,
            available_budget=available_budget,
            cross_decision_alternatives=(),
            ignored_same_decision_alternatives=same,
            bottleneck_alternatives=(),
            reason=(
                "Every admitted alternative is in the same decision-equivalence cell. "
                "Causal-model identity remains unresolved, but no evidence is required "
                "for the immediate action choice."
            ),
        )

    eligible: list[tuple[float, InformationAction, tuple[str, ...], float]] = []
    saw_uncertified = False
    for action in actions:
        if action.rate_certificate != "CERTIFIED_LOWER_BOUND":
            saw_uncertified = True
            continue
        if any(m not in action.information_rate_lower_bounds for m in cross):
            continue
        rates = {m: float(action.information_rate_lower_bounds[m]) for m in cross}
        min_rate = min(rates.values())
        bottlenecks = tuple(sorted(m for m, value in rates.items() if abs(value - min_rate) <= 1e-15))
        q = min_rate / action.unit_cost
        max_total_cost = math.inf if action.max_units is None else action.max_units * action.unit_cost
        eligible.append((q, action, bottlenecks, max_total_cost))

    if not eligible:
        return DecisionRelevantInformationDecision(
            state="NO_CERTIFIED_DECISION_INFORMATION_RATE",
            action_id=None,
            candidate_decision=candidate_decision,
            required_information_nats=required,
            guaranteed_information_per_cost=0.0,
            necessary_cost_lower_bound=math.inf,
            available_budget=available_budget,
            cross_decision_alternatives=cross,
            ignored_same_decision_alternatives=same,
            bottleneck_alternatives=cross,
            reason=(
                "No action has a complete certified lower-bound rate vector for every cross-decision alternative."
                if not saw_uncertified
                else "Only uncertified or incomplete rates cover the cross-decision alternatives."
            ),
        )

    eligible.sort(key=lambda item: (-item[0], item[1].unit_cost, item[1].action_id))
    q, action, bottlenecks, action_capacity_cost = eligible[0]
    if q <= 0:
        return DecisionRelevantInformationDecision(
            state="NO_DECISION_IDENTIFYING_INFORMATION_CHANNEL",
            action_id=action.action_id,
            candidate_decision=candidate_decision,
            required_information_nats=required,
            guaranteed_information_per_cost=0.0,
            necessary_cost_lower_bound=math.inf,
            available_budget=available_budget,
            cross_decision_alternatives=cross,
            ignored_same_decision_alternatives=same,
            bottleneck_alternatives=bottlenecks,
            reason=(
                "At least one cross-decision alternative has zero certified information "
                "rate under every admissible complete action. Extra compute cannot "
                "resolve the current decision through this channel set."
            ),
        )

    necessary_cost = required / q
    if necessary_cost > action_capacity_cost:
        return DecisionRelevantInformationDecision(
            state="DECISION_ACTION_CAPACITY_BELOW_NECESSARY_BOUND",
            action_id=action.action_id,
            candidate_decision=candidate_decision,
            required_information_nats=required,
            guaranteed_information_per_cost=q,
            necessary_cost_lower_bound=necessary_cost,
            available_budget=available_budget,
            cross_decision_alternatives=cross,
            ignored_same_decision_alternatives=same,
            bottleneck_alternatives=bottlenecks,
            reason=(
                "The selected action cannot supply enough acquisition units even to "
                "meet the necessary decision-information converse."
            ),
        )
    if available_budget < necessary_cost:
        return DecisionRelevantInformationDecision(
            state="INSUFFICIENT_DECISION_INFORMATION_BUDGET",
            action_id=action.action_id,
            candidate_decision=candidate_decision,
            required_information_nats=required,
            guaranteed_information_per_cost=q,
            necessary_cost_lower_bound=necessary_cost,
            available_budget=available_budget,
            cross_decision_alternatives=cross,
            ignored_same_decision_alternatives=same,
            bottleneck_alternatives=bottlenecks,
            reason=(
                "Available budget is below the information-theoretic necessary lower "
                "bound for resolving the current decision."
            ),
        )
    return DecisionRelevantInformationDecision(
        state="ACQUIRE_DECISION_RELEVANT_EVIDENCE_BUDGET_NOT_RULED_OUT_BY_CONVERSE",
        action_id=action.action_id,
        candidate_decision=candidate_decision,
        required_information_nats=required,
        guaranteed_information_per_cost=q,
        necessary_cost_lower_bound=necessary_cost,
        available_budget=available_budget,
        cross_decision_alternatives=cross,
        ignored_same_decision_alternatives=same,
        bottleneck_alternatives=bottlenecks,
        reason=(
            "Spend is selected by the maximin certified information-per-cost over only "
            "cross-decision alternatives. Same-decision causal ambiguity is preserved, "
            "not silently resolved. This is spend permission, not a sufficiency or truth certificate."
        ),
    )
