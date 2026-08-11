from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
from typing import Mapping, Sequence

from cwc.epistemics.information_acquisition import (
    InformationAction,
    select_decision_relevant_information_action,
)
from cwc.memory.epistemic_store import EpistemicMemoryLedger
from cwc.planning.proof_carrying import (
    PlanCertificate,
    PlanState,
    WorldBranch,
    verify_plan_certificate,
)


_DECISION_SEAL = object()


class SelfFalsificationError(RuntimeError):
    """Base error for fail-closed autonomous falsification operations."""


class FalsificationBindingError(SelfFalsificationError):
    """Raised when an attack decision/outcome is stale or targets unbound authority."""


class SelfFalsificationState(str, Enum):
    REJECT_INVALID_PLAN_CERTIFICATE = "REJECT_INVALID_PLAN_CERTIFICATE"
    REJECT_NONACTIONABLE_PLAN_STATE = "REJECT_NONACTIONABLE_PLAN_STATE"
    NO_WELL_DEFINED_CANDIDATE_DECISION = "NO_WELL_DEFINED_CANDIDATE_DECISION"
    NO_DECISION_RELEVANT_ATTACK = "NO_DECISION_RELEVANT_ATTACK"
    NO_LOAD_BEARING_CERTIFIED_ATTACK = "NO_LOAD_BEARING_CERTIFIED_ATTACK"
    NO_CERTIFIED_DECISION_ATTACK = "NO_CERTIFIED_DECISION_ATTACK"
    NO_DECISION_IDENTIFYING_ATTACK = "NO_DECISION_IDENTIFYING_ATTACK"
    ATTACK_CAPACITY_BELOW_NECESSARY_BOUND = "ATTACK_CAPACITY_BELOW_NECESSARY_BOUND"
    INSUFFICIENT_ATTACK_BUDGET = "INSUFFICIENT_ATTACK_BUDGET"
    PROPOSE_BOUNDED_FALSIFICATION = "PROPOSE_BOUNDED_FALSIFICATION"


class FalsificationOutcome(str, Enum):
    INCONCLUSIVE = "INCONCLUSIVE"
    SURVIVED = "SURVIVED"
    FALSIFIED_MEMORY = "FALSIFIED_MEMORY"
    INVALIDATED_ASSUMPTION = "INVALIDATED_ASSUMPTION"


def _norm(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted({str(v).strip() for v in values if str(v).strip()}))


def _sha(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class FalsificationAttack:
    attack_id: str
    unit_cost: float
    information_rate_lower_bounds: Mapping[str, float]
    rate_certificate: str
    target_world_ids: tuple[str, ...]
    target_memory_ids: tuple[str, ...] = ()
    target_assumption_ids: tuple[str, ...] = ()
    max_units: int | None = None

    def __post_init__(self) -> None:
        attack_id = self.attack_id.strip()
        if not attack_id:
            raise ValueError("attack_id required")
        if not math.isfinite(self.unit_cost) or self.unit_cost <= 0:
            raise ValueError("unit_cost must be finite and >0")
        rates: dict[str, float] = {}
        for key, value in self.information_rate_lower_bounds.items():
            key = str(key).strip()
            value = float(value)
            if not key or not math.isfinite(value) or value < 0:
                raise ValueError("information-rate map must contain nonempty ids and finite non-negative values")
            rates[key] = value
        if not rates:
            raise ValueError("at least one information-rate lower bound required")
        worlds = _norm(self.target_world_ids)
        memories = _norm(self.target_memory_ids)
        assumptions = _norm(self.target_assumption_ids)
        if not worlds:
            raise ValueError("at least one target world required")
        if not memories and not assumptions:
            raise ValueError("attack must target at least one load-bearing memory or assumption")
        if self.max_units is not None and self.max_units < 1:
            raise ValueError("max_units must be positive")
        object.__setattr__(self, "attack_id", attack_id)
        object.__setattr__(self, "information_rate_lower_bounds", rates)
        object.__setattr__(self, "target_world_ids", worlds)
        object.__setattr__(self, "target_memory_ids", memories)
        object.__setattr__(self, "target_assumption_ids", assumptions)

    def as_information_action(self) -> InformationAction:
        return InformationAction(
            action_id=self.attack_id,
            unit_cost=self.unit_cost,
            information_rate_lower_bounds=self.information_rate_lower_bounds,
            rate_certificate=self.rate_certificate,
            max_units=self.max_units,
        )


@dataclass(frozen=True, slots=True, init=False)
class SelfFalsificationDecision:
    state: SelfFalsificationState
    attack_id: str | None
    candidate_world_id: str
    candidate_decision: str | None
    cross_decision_world_ids: tuple[str, ...]
    ignored_same_decision_world_ids: tuple[str, ...]
    load_bearing_memory_bindings: tuple[tuple[str, str], ...]
    load_bearing_assumption_ids: tuple[str, ...]
    selected_target_world_ids: tuple[str, ...]
    selected_target_memory_ids: tuple[str, ...]
    selected_target_assumption_ids: tuple[str, ...]
    necessary_cost_lower_bound: float | None
    information_state: str | None
    plan_certificate_digest: str
    world_bindings: tuple[tuple[str, str], ...]
    reason: str
    decision_digest: str

    def __new__(cls, *args: object, **kwargs: object) -> "SelfFalsificationDecision":
        raise TypeError("SelfFalsificationDecision can only be minted by select_self_falsification_attack")

    @classmethod
    def _mint(
        cls,
        *,
        state: SelfFalsificationState,
        attack_id: str | None,
        candidate_world_id: str,
        candidate_decision: str | None,
        cross_decision_world_ids: Sequence[str],
        ignored_same_decision_world_ids: Sequence[str],
        load_bearing_memory_bindings: Sequence[tuple[str, str]],
        load_bearing_assumption_ids: Sequence[str],
        selected_target_world_ids: Sequence[str],
        selected_target_memory_ids: Sequence[str],
        selected_target_assumption_ids: Sequence[str],
        necessary_cost_lower_bound: float | None,
        information_state: str | None,
        plan_certificate_digest: str,
        world_bindings: Sequence[tuple[str, str]],
        reason: str,
        _seal: object,
    ) -> "SelfFalsificationDecision":
        if _seal is not _DECISION_SEAL:
            raise TypeError("invalid self-falsification mint seal")
        memories = tuple(sorted((str(a), str(b)) for a, b in load_bearing_memory_bindings))
        worlds = tuple(sorted((str(a), str(b)) for a, b in world_bindings))
        payload = {
            "state": state.value,
            "attack_id": attack_id,
            "candidate_world_id": candidate_world_id,
            "candidate_decision": candidate_decision,
            "cross_decision_world_ids": list(_norm(tuple(cross_decision_world_ids))),
            "ignored_same_decision_world_ids": list(_norm(tuple(ignored_same_decision_world_ids))),
            "load_bearing_memory_bindings": [list(x) for x in memories],
            "load_bearing_assumption_ids": list(_norm(tuple(load_bearing_assumption_ids))),
            "selected_target_world_ids": list(_norm(tuple(selected_target_world_ids))),
            "selected_target_memory_ids": list(_norm(tuple(selected_target_memory_ids))),
            "selected_target_assumption_ids": list(_norm(tuple(selected_target_assumption_ids))),
            "necessary_cost_lower_bound": necessary_cost_lower_bound,
            "information_state": information_state,
            "plan_certificate_digest": plan_certificate_digest,
            "world_bindings": [list(x) for x in worlds],
            "reason": reason,
        }
        obj = object.__new__(cls)
        values = {
            "state": state,
            "attack_id": attack_id,
            "candidate_world_id": candidate_world_id,
            "candidate_decision": candidate_decision,
            "cross_decision_world_ids": tuple(payload["cross_decision_world_ids"]),
            "ignored_same_decision_world_ids": tuple(payload["ignored_same_decision_world_ids"]),
            "load_bearing_memory_bindings": memories,
            "load_bearing_assumption_ids": tuple(payload["load_bearing_assumption_ids"]),
            "selected_target_world_ids": tuple(payload["selected_target_world_ids"]),
            "selected_target_memory_ids": tuple(payload["selected_target_memory_ids"]),
            "selected_target_assumption_ids": tuple(payload["selected_target_assumption_ids"]),
            "necessary_cost_lower_bound": necessary_cost_lower_bound,
            "information_state": information_state,
            "plan_certificate_digest": plan_certificate_digest,
            "world_bindings": worlds,
            "reason": reason,
            "decision_digest": _sha(payload),
        }
        for key, value in values.items():
            object.__setattr__(obj, key, value)
        return obj

    def payload(self) -> dict[str, object]:
        return {
            "state": self.state.value,
            "attack_id": self.attack_id,
            "candidate_world_id": self.candidate_world_id,
            "candidate_decision": self.candidate_decision,
            "cross_decision_world_ids": list(self.cross_decision_world_ids),
            "ignored_same_decision_world_ids": list(self.ignored_same_decision_world_ids),
            "load_bearing_memory_bindings": [list(x) for x in self.load_bearing_memory_bindings],
            "load_bearing_assumption_ids": list(self.load_bearing_assumption_ids),
            "selected_target_world_ids": list(self.selected_target_world_ids),
            "selected_target_memory_ids": list(self.selected_target_memory_ids),
            "selected_target_assumption_ids": list(self.selected_target_assumption_ids),
            "necessary_cost_lower_bound": self.necessary_cost_lower_bound,
            "information_state": self.information_state,
            "plan_certificate_digest": self.plan_certificate_digest,
            "world_bindings": [list(x) for x in self.world_bindings],
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class FalsificationUpdate:
    outcome: FalsificationOutcome
    target_id: str | None
    changed_memory_ids: tuple[str, ...]
    invalidated_assumption_ids: tuple[str, ...]
    authority_promoted: bool
    reason: str


def _load_bearing_closure(
    ledger: EpistemicMemoryLedger, certificate: PlanCertificate
) -> tuple[tuple[tuple[str, str], ...], tuple[str, ...]]:
    pending = [mid for mid, _ in certificate.memory_bindings]
    seen: set[str] = set()
    bindings: list[tuple[str, str]] = []
    assumptions: set[str] = set()
    while pending:
        mid = pending.pop()
        if mid in seen:
            continue
        rec = ledger.record(mid)
        seen.add(mid)
        bindings.append((mid, rec.memory_digest))
        assumptions.update(rec.assumption_ids)
        pending.extend(rec.dependency_ids)
    return tuple(sorted(bindings)), tuple(sorted(assumptions))


def _world_decisions(worlds: Sequence[WorldBranch], margin: float) -> dict[str, str] | None:
    out: dict[str, str] = {}
    for world in worlds:
        ranked = sorted(world.utilities, key=lambda a: (-world.utilities[a], a))
        if len(ranked) < 2:
            return None
        top, second = ranked[0], ranked[1]
        if world.utilities[top] - world.utilities[second] < margin:
            return None
        out[world.world_id] = top
    return out


def _mint_decision(
    *,
    state: SelfFalsificationState,
    attack: FalsificationAttack | None,
    candidate_world_id: str,
    candidate_decision: str | None,
    cross: Sequence[str],
    same: Sequence[str],
    memory_bindings: Sequence[tuple[str, str]],
    assumption_ids: Sequence[str],
    necessary_cost: float | None,
    information_state: str | None,
    certificate: PlanCertificate,
    worlds: Sequence[WorldBranch],
    reason: str,
) -> SelfFalsificationDecision:
    return SelfFalsificationDecision._mint(
        state=state,
        attack_id=None if attack is None else attack.attack_id,
        candidate_world_id=candidate_world_id,
        candidate_decision=candidate_decision,
        cross_decision_world_ids=cross,
        ignored_same_decision_world_ids=same,
        load_bearing_memory_bindings=memory_bindings,
        load_bearing_assumption_ids=assumption_ids,
        selected_target_world_ids=() if attack is None else attack.target_world_ids,
        selected_target_memory_ids=() if attack is None else attack.target_memory_ids,
        selected_target_assumption_ids=() if attack is None else attack.target_assumption_ids,
        necessary_cost_lower_bound=necessary_cost,
        information_state=information_state,
        plan_certificate_digest=certificate.certificate_digest,
        world_bindings=[(w.world_id, w.digest) for w in worlds],
        reason=reason,
        _seal=_DECISION_SEAL,
    )


def select_self_falsification_attack(
    *,
    ledger: EpistemicMemoryLedger,
    plan_certificate: PlanCertificate,
    context_scope: Sequence[str],
    worlds: Sequence[WorldBranch],
    candidate_world_id: str,
    attacks: Sequence[FalsificationAttack],
    available_budget: float,
    alpha: float = 0.01,
    target_power: float = 0.95,
) -> SelfFalsificationDecision:
    """Select a bounded attack only when it can alter the live decision.

    The function composes the proof-carrying planner with COG-INFO-02. It does not
    execute arbitrary code, infer causal truth, or promote epistemic state. Selection
    is bound to the current ledger and world set; negative outcomes are applied by the
    separate monotone update function below.
    """
    if not isinstance(plan_certificate, PlanCertificate):
        raise TypeError("plan_certificate must be a typed PlanCertificate")
    if not math.isfinite(available_budget) or available_budget < 0:
        raise ValueError("available_budget must be finite and >=0")
    candidate_world_id = str(candidate_world_id).strip()
    if not candidate_world_id:
        raise ValueError("candidate_world_id required")
    attack_ids = [a.attack_id for a in attacks]
    if len(attack_ids) != len(set(attack_ids)):
        raise ValueError("attack ids must be unique")

    valid_plan = verify_plan_certificate(
        plan_certificate, ledger=ledger, context_scope=context_scope, worlds=worlds
    )
    if not valid_plan:
        return _mint_decision(
            state=SelfFalsificationState.REJECT_INVALID_PLAN_CERTIFICATE,
            attack=None,
            candidate_world_id=candidate_world_id,
            candidate_decision=None,
            cross=(), same=(), memory_bindings=(), assumption_ids=(),
            necessary_cost=None, information_state=None, certificate=plan_certificate,
            worlds=worlds,
            reason="plan certificate is stale, malformed, context-mismatched, or bound to a different world/ledger state",
        )

    memory_bindings, assumption_ids = _load_bearing_closure(ledger, plan_certificate)

    if plan_certificate.decision_state is PlanState.BLOCKED_MEMORY_AUTHORITY:
        return _mint_decision(
            state=SelfFalsificationState.REJECT_NONACTIONABLE_PLAN_STATE,
            attack=None, candidate_world_id=candidate_world_id, candidate_decision=None,
            cross=(), same=(), memory_bindings=memory_bindings, assumption_ids=assumption_ids,
            necessary_cost=None, information_state=None, certificate=plan_certificate, worlds=worlds,
            reason="blocked-memory plan state cannot authorize autonomous falsification spend",
        )

    decisions = _world_decisions(worlds, plan_certificate.robust_margin)
    world_ids = {w.world_id for w in worlds}
    if candidate_world_id not in world_ids or decisions is None:
        return _mint_decision(
            state=SelfFalsificationState.NO_WELL_DEFINED_CANDIDATE_DECISION,
            attack=None, candidate_world_id=candidate_world_id, candidate_decision=None,
            cross=(), same=(), memory_bindings=memory_bindings, assumption_ids=assumption_ids,
            necessary_cost=None, information_state=None, certificate=plan_certificate, worlds=worlds,
            reason="candidate world is absent or at least one admitted world lacks a unique margin-separated decision",
        )

    candidate_decision = decisions[candidate_world_id]
    alternatives = {wid: decision for wid, decision in decisions.items() if wid != candidate_world_id}
    cross = tuple(sorted(wid for wid, decision in alternatives.items() if decision != candidate_decision))
    same = tuple(sorted(wid for wid, decision in alternatives.items() if decision == candidate_decision))
    if not cross:
        return _mint_decision(
            state=SelfFalsificationState.NO_DECISION_RELEVANT_ATTACK,
            attack=None, candidate_world_id=candidate_world_id, candidate_decision=candidate_decision,
            cross=(), same=same, memory_bindings=memory_bindings, assumption_ids=assumption_ids,
            necessary_cost=0.0, information_state="DECISION_ALREADY_IDENTIFIED_NO_ACQUISITION",
            certificate=plan_certificate, worlds=worlds,
            reason="all admitted worlds are in the same immediate decision-equivalence cell; causal ambiguity is preserved without spend",
        )

    load_memories = {mid for mid, _ in memory_bindings}
    load_assumptions = set(assumption_ids)
    cross_set = set(cross)
    eligible: list[FalsificationAttack] = []
    for attack in attacks:
        if not cross_set.issubset(set(attack.target_world_ids)):
            continue
        if not set(attack.target_memory_ids).issubset(load_memories):
            continue
        if not set(attack.target_assumption_ids).issubset(load_assumptions):
            continue
        eligible.append(attack)

    if not eligible:
        return _mint_decision(
            state=SelfFalsificationState.NO_LOAD_BEARING_CERTIFIED_ATTACK,
            attack=None, candidate_world_id=candidate_world_id, candidate_decision=candidate_decision,
            cross=cross, same=same, memory_bindings=memory_bindings, assumption_ids=assumption_ids,
            necessary_cost=None, information_state=None, certificate=plan_certificate, worlds=worlds,
            reason="no admitted attack is both decision-covering and bound only to the current plan's load-bearing memory/assumption graph",
        )

    info = select_decision_relevant_information_action(
        actions=[a.as_information_action() for a in eligible],
        candidate_decision=candidate_decision,
        alternative_decisions=alternatives,
        alpha=alpha,
        target_power=target_power,
        available_budget=available_budget,
    )
    by_id = {a.attack_id: a for a in eligible}
    selected = by_id.get(info.action_id) if info.action_id is not None else None
    mapping = {
        "NO_CERTIFIED_DECISION_INFORMATION_RATE": SelfFalsificationState.NO_CERTIFIED_DECISION_ATTACK,
        "NO_DECISION_IDENTIFYING_INFORMATION_CHANNEL": SelfFalsificationState.NO_DECISION_IDENTIFYING_ATTACK,
        "DECISION_ACTION_CAPACITY_BELOW_NECESSARY_BOUND": SelfFalsificationState.ATTACK_CAPACITY_BELOW_NECESSARY_BOUND,
        "INSUFFICIENT_DECISION_INFORMATION_BUDGET": SelfFalsificationState.INSUFFICIENT_ATTACK_BUDGET,
        "ACQUIRE_DECISION_RELEVANT_EVIDENCE_BUDGET_NOT_RULED_OUT_BY_CONVERSE": SelfFalsificationState.PROPOSE_BOUNDED_FALSIFICATION,
        "DECISION_ALREADY_IDENTIFIED_NO_ACQUISITION": SelfFalsificationState.NO_DECISION_RELEVANT_ATTACK,
    }
    state = mapping.get(info.state)
    if state is None:
        raise SelfFalsificationError(f"unsupported information governor state: {info.state}")
    return _mint_decision(
        state=state,
        attack=selected,
        candidate_world_id=candidate_world_id,
        candidate_decision=candidate_decision,
        cross=cross,
        same=same,
        memory_bindings=memory_bindings,
        assumption_ids=assumption_ids,
        necessary_cost=info.necessary_cost_lower_bound,
        information_state=info.state,
        certificate=plan_certificate,
        worlds=worlds,
        reason=info.reason,
    )


def verify_self_falsification_decision(
    decision: SelfFalsificationDecision,
    *,
    ledger: EpistemicMemoryLedger,
    plan_certificate: PlanCertificate,
    context_scope: Sequence[str],
    worlds: Sequence[WorldBranch],
) -> bool:
    if not isinstance(decision, SelfFalsificationDecision):
        return False
    if decision.decision_digest != _sha(decision.payload()):
        return False
    if decision.plan_certificate_digest != plan_certificate.certificate_digest:
        return False
    if not verify_plan_certificate(plan_certificate, ledger=ledger, context_scope=context_scope, worlds=worlds):
        return False
    try:
        bindings, assumptions = _load_bearing_closure(ledger, plan_certificate)
    except Exception:
        return False
    if bindings != decision.load_bearing_memory_bindings:
        return False
    if assumptions != decision.load_bearing_assumption_ids:
        return False
    current_worlds = tuple(sorted((w.world_id, w.digest) for w in worlds))
    if current_worlds != decision.world_bindings:
        return False
    return True


def apply_self_falsification_outcome(
    *,
    decision: SelfFalsificationDecision,
    ledger: EpistemicMemoryLedger,
    plan_certificate: PlanCertificate,
    context_scope: Sequence[str],
    worlds: Sequence[WorldBranch],
    outcome: FalsificationOutcome,
    target_id: str | None = None,
    reason: str = "bounded self-falsification outcome",
) -> FalsificationUpdate:
    """Apply only monotone-negative authority updates from a bound selected attack."""
    if decision.state is not SelfFalsificationState.PROPOSE_BOUNDED_FALSIFICATION:
        raise FalsificationBindingError("only a proposed bounded falsification attack can produce an update")
    if not verify_self_falsification_decision(
        decision, ledger=ledger, plan_certificate=plan_certificate,
        context_scope=context_scope, worlds=worlds,
    ):
        raise FalsificationBindingError("self-falsification decision is stale or unbound")
    if not reason.strip():
        raise ValueError("reason must be non-empty")

    if outcome in {FalsificationOutcome.INCONCLUSIVE, FalsificationOutcome.SURVIVED}:
        if target_id is not None:
            raise FalsificationBindingError("non-negative outcome must not mutate a target")
        ledger.assert_invariants()
        return FalsificationUpdate(
            outcome=outcome,
            target_id=None,
            changed_memory_ids=(),
            invalidated_assumption_ids=(),
            authority_promoted=False,
            reason="test did not falsify bound authority; no positive promotion is permitted",
        )

    target_id = "" if target_id is None else str(target_id).strip()
    if not target_id:
        raise FalsificationBindingError("negative outcome requires an explicitly bound target")

    if outcome is FalsificationOutcome.FALSIFIED_MEMORY:
        if target_id not in decision.selected_target_memory_ids:
            raise FalsificationBindingError("memory target was not bound to the selected attack")
        changed = ledger.retract(target_id, reason=reason)
        ledger.assert_invariants()
        return FalsificationUpdate(
            outcome=outcome, target_id=target_id, changed_memory_ids=changed,
            invalidated_assumption_ids=(), authority_promoted=False, reason=reason,
        )

    if outcome is FalsificationOutcome.INVALIDATED_ASSUMPTION:
        if target_id not in decision.selected_target_assumption_ids:
            raise FalsificationBindingError("assumption target was not bound to the selected attack")
        changed = ledger.invalidate_assumption(target_id, reason=reason)
        ledger.assert_invariants()
        return FalsificationUpdate(
            outcome=outcome, target_id=target_id, changed_memory_ids=changed,
            invalidated_assumption_ids=(target_id,), authority_promoted=False, reason=reason,
        )

    raise SelfFalsificationError(f"unsupported falsification outcome: {outcome}")
