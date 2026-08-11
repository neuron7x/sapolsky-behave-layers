from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import math
from typing import Mapping, Sequence

from cwc.epistemics.information_acquisition import (
    InformationAction,
    select_maximin_information_action,
)
from cwc.epistemics.lattice import EpistemicState
from cwc.memory.epistemic_store import EpistemicMemoryLedger, MemoryRecord, MemoryStatus


_PLAN_SEAL = object()


class PlanState(str, Enum):
    ROBUST_ACTION = "ROBUST_ACTION"
    ASSUMPTION_CONDITIONAL_PLAN = "ASSUMPTION_CONDITIONAL_PLAN"
    ACQUIRE_INFORMATION = "ACQUIRE_INFORMATION"
    ABSTAIN_WORLD_DISAGREEMENT = "ABSTAIN_WORLD_DISAGREEMENT"
    ABSTAIN_NO_UNIQUE_ROBUST_ACTION = "ABSTAIN_NO_UNIQUE_ROBUST_ACTION"
    BLOCKED_MEMORY_AUTHORITY = "BLOCKED_MEMORY_AUTHORITY"


def _norm(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted({str(v).strip() for v in values if str(v).strip()}))


def _sha(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True)
class WorldBranch:
    world_id: str
    utilities: Mapping[str, float]
    provenance: str

    def __post_init__(self) -> None:
        if not self.world_id.strip():
            raise ValueError("world_id required")
        if not self.provenance.strip():
            raise ValueError("world provenance required")
        if len(self.utilities) < 2:
            raise ValueError("at least two actions required")
        clean: dict[str, float] = {}
        for action, value in self.utilities.items():
            action = str(action).strip()
            value = float(value)
            if not action or not math.isfinite(value):
                raise ValueError("finite utility and nonempty action required")
            clean[action] = value
        object.__setattr__(self, "utilities", clean)

    @property
    def digest(self) -> str:
        return _sha({
            "world_id": self.world_id,
            "utilities": {k: self.utilities[k] for k in sorted(self.utilities)},
            "provenance": self.provenance,
        })


@dataclass(frozen=True, slots=True, init=False)
class PlanCertificate:
    plan_id: str
    context_scope: tuple[str, ...]
    decision_state: PlanState
    selected_action: str | None
    memory_bindings: tuple[tuple[str, str], ...]
    world_bindings: tuple[tuple[str, str], ...]
    robust_margin: float
    information_state: str | None
    information_action_id: str | None
    necessary_information_cost: float | None
    reason: str
    certificate_digest: str

    def __new__(cls, *args: object, **kwargs: object) -> "PlanCertificate":
        raise TypeError("PlanCertificate can only be minted by plan_counterfactual")

    @classmethod
    def _mint(
        cls,
        *,
        plan_id: str,
        context_scope: Sequence[str],
        decision_state: PlanState,
        selected_action: str | None,
        memory_bindings: Sequence[tuple[str, str]],
        world_bindings: Sequence[tuple[str, str]],
        robust_margin: float,
        information_state: str | None,
        information_action_id: str | None,
        necessary_information_cost: float | None,
        reason: str,
        _seal: object,
    ) -> "PlanCertificate":
        if _seal is not _PLAN_SEAL:
            raise TypeError("invalid plan mint seal")
        scope = _norm(tuple(context_scope))
        if not plan_id.strip() or not scope:
            raise ValueError("plan_id/context required")
        memories = tuple(sorted((str(a), str(b)) for a, b in memory_bindings))
        worlds = tuple(sorted((str(a), str(b)) for a, b in world_bindings))
        payload = {
            "plan_id": plan_id,
            "context_scope": list(scope),
            "decision_state": decision_state.value,
            "selected_action": selected_action,
            "memory_bindings": [list(x) for x in memories],
            "world_bindings": [list(x) for x in worlds],
            "robust_margin": float(robust_margin),
            "information_state": information_state,
            "information_action_id": information_action_id,
            "necessary_information_cost": necessary_information_cost,
            "reason": reason,
        }
        obj = object.__new__(cls)
        for key, value in {
            "plan_id": plan_id,
            "context_scope": scope,
            "decision_state": decision_state,
            "selected_action": selected_action,
            "memory_bindings": memories,
            "world_bindings": worlds,
            "robust_margin": float(robust_margin),
            "information_state": information_state,
            "information_action_id": information_action_id,
            "necessary_information_cost": necessary_information_cost,
            "reason": reason,
            "certificate_digest": _sha(payload),
        }.items():
            object.__setattr__(obj, key, value)
        return obj

    def payload(self) -> dict[str, object]:
        return {
            "plan_id": self.plan_id,
            "context_scope": list(self.context_scope),
            "decision_state": self.decision_state.value,
            "selected_action": self.selected_action,
            "memory_bindings": [list(x) for x in self.memory_bindings],
            "world_bindings": [list(x) for x in self.world_bindings],
            "robust_margin": self.robust_margin,
            "information_state": self.information_state,
            "information_action_id": self.information_action_id,
            "necessary_information_cost": self.necessary_information_cost,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class PlanResult:
    state: PlanState
    selected_action: str | None
    certificate: PlanCertificate


def _validate_worlds(worlds: Sequence[WorldBranch]) -> tuple[tuple[WorldBranch, ...], tuple[str, ...]]:
    ww = tuple(worlds)
    if not ww:
        raise ValueError("at least one admitted world required")
    ids = [w.world_id for w in ww]
    if len(ids) != len(set(ids)):
        raise ValueError("world ids must be unique")
    action_set = tuple(sorted(ww[0].utilities))
    if len(action_set) < 2:
        raise ValueError("at least two actions required")
    for w in ww[1:]:
        if tuple(sorted(w.utilities)) != action_set:
            raise ValueError("all worlds must define the same action set")
    return ww, action_set


def _robust_winner(worlds: Sequence[WorldBranch], actions: Sequence[str], margin: float) -> tuple[str | None, bool, bool]:
    tops: list[str] = []
    all_margin = True
    for w in worlds:
        ranked = sorted(actions, key=lambda a: (-w.utilities[a], a))
        top, second = ranked[0], ranked[1]
        tops.append(top)
        if w.utilities[top] - w.utilities[second] < margin:
            all_margin = False
    same_top = len(set(tops)) == 1
    return (tops[0] if same_top and all_margin else None), same_top, all_margin


def _mint_result(
    *,
    plan_id: str,
    context_scope: Sequence[str],
    state: PlanState,
    selected_action: str | None,
    memories: Sequence[MemoryRecord],
    worlds: Sequence[WorldBranch],
    robust_margin: float,
    information_state: str | None,
    information_action_id: str | None,
    necessary_information_cost: float | None,
    reason: str,
) -> PlanResult:
    cert = PlanCertificate._mint(
        plan_id=plan_id,
        context_scope=context_scope,
        decision_state=state,
        selected_action=selected_action,
        memory_bindings=[(m.memory_id, m.memory_digest) for m in memories],
        world_bindings=[(w.world_id, w.digest) for w in worlds],
        robust_margin=robust_margin,
        information_state=information_state,
        information_action_id=information_action_id,
        necessary_information_cost=necessary_information_cost,
        reason=reason,
        _seal=_PLAN_SEAL,
    )
    return PlanResult(state=state, selected_action=selected_action, certificate=cert)


def plan_counterfactual(
    *,
    ledger: EpistemicMemoryLedger,
    plan_id: str,
    context_scope: Sequence[str],
    required_memories: Sequence[object],
    worlds: Sequence[WorldBranch],
    robust_margin: float = 0.05,
    information_actions: Sequence[InformationAction] = (),
    available_information_budget: float = 0.0,
    alpha: float = 0.01,
    target_power: float = 0.95,
) -> PlanResult:
    """Select only decisions that survive every admitted world.

    This function deliberately has no world-prior argument. Probability-weighted
    averaging across incompatible causal worlds therefore cannot create ROBUST_ACTION.
    """
    if not math.isfinite(robust_margin) or robust_margin <= 0:
        raise ValueError("robust_margin must be finite and >0")
    ww, actions = _validate_worlds(worlds)
    scope = _norm(tuple(context_scope))
    if not scope:
        raise ValueError("context_scope required")

    memories: list[MemoryRecord] = []
    invalid_memory = False
    assumption_conditional = False
    world_ids = {w.world_id for w in ww}
    for obj in required_memories:
        if not isinstance(obj, MemoryRecord):
            invalid_memory = True
            continue
        memories.append(obj)
        try:
            current = ledger.record(obj.memory_id)
        except KeyError:
            invalid_memory = True
            continue
        if current.memory_digest != obj.memory_digest or current.status is MemoryStatus.RETRACTED:
            invalid_memory = True
            continue
        if current.context_scope != scope:
            invalid_memory = True
            continue
        if current.status is MemoryStatus.QUARANTINED:
            if current.epistemic_state is EpistemicState.ASSUMPTION_CONDITIONAL:
                assumption_conditional = True
            elif current.epistemic_state is EpistemicState.INTERVENTION_SUPPORTED and current.countermodel_ids:
                # Decision robustness may still be tested only if every surviving
                # countermodel is explicitly represented as an admitted world.
                if not set(current.countermodel_ids).issubset(world_ids):
                    invalid_memory = True
            else:
                invalid_memory = True

    if invalid_memory:
        return _mint_result(
            plan_id=plan_id, context_scope=scope, state=PlanState.BLOCKED_MEMORY_AUTHORITY,
            selected_action=None, memories=memories, worlds=ww, robust_margin=robust_margin,
            information_state=None, information_action_id=None, necessary_information_cost=None,
            reason="required memory is legacy, stale, retracted, context-mismatched, or has unrepresented authority debt",
        )

    winner, same_top, all_margin = _robust_winner(ww, actions, robust_margin)

    if assumption_conditional:
        return _mint_result(
            plan_id=plan_id, context_scope=scope, state=PlanState.ASSUMPTION_CONDITIONAL_PLAN,
            selected_action=winner, memories=memories, worlds=ww, robust_margin=robust_margin,
            information_state=None, information_action_id=None, necessary_information_cost=None,
            reason="plan depends on quarantined identifying assumptions and cannot be emitted as unconditional action authority",
        )

    if winner is not None:
        return _mint_result(
            plan_id=plan_id, context_scope=scope, state=PlanState.ROBUST_ACTION,
            selected_action=winner, memories=memories, worlds=ww, robust_margin=robust_margin,
            information_state=None, information_action_id=None, necessary_information_cost=None,
            reason="same action uniquely dominates by the frozen margin in every admitted world; no world averaging used",
        )

    if same_top and not all_margin:
        return _mint_result(
            plan_id=plan_id, context_scope=scope, state=PlanState.ABSTAIN_NO_UNIQUE_ROBUST_ACTION,
            selected_action=None, memories=memories, worlds=ww, robust_margin=robust_margin,
            information_state=None, information_action_id=None, necessary_information_cost=None,
            reason="nominal top action is shared but at least one world fails the frozen robust-margin requirement",
        )

    if information_actions:
        info = select_maximin_information_action(
            actions=information_actions,
            unresolved_alternatives=tuple(sorted(world_ids)),
            alpha=alpha,
            target_power=target_power,
            available_budget=available_information_budget,
        )
        if info.state == "ACQUIRE_EVIDENCE_BUDGET_NOT_RULED_OUT_BY_CONVERSE":
            return _mint_result(
                plan_id=plan_id, context_scope=scope, state=PlanState.ACQUIRE_INFORMATION,
                selected_action=None, memories=memories, worlds=ww, robust_margin=robust_margin,
                information_state=info.state, information_action_id=info.action_id,
                necessary_information_cost=info.necessary_cost_lower_bound,
                reason="admitted worlds disagree; certified maximin information channel is not ruled out by the necessary budget converse",
            )
        return _mint_result(
            plan_id=plan_id, context_scope=scope, state=PlanState.ABSTAIN_WORLD_DISAGREEMENT,
            selected_action=None, memories=memories, worlds=ww, robust_margin=robust_margin,
            information_state=info.state, information_action_id=info.action_id,
            necessary_information_cost=info.necessary_cost_lower_bound,
            reason="admitted worlds disagree and information acquisition is not licensed by the certified converse/budget gate",
        )

    return _mint_result(
        plan_id=plan_id, context_scope=scope, state=PlanState.ABSTAIN_WORLD_DISAGREEMENT,
        selected_action=None, memories=memories, worlds=ww, robust_margin=robust_margin,
        information_state=None, information_action_id=None, necessary_information_cost=None,
        reason="admitted worlds disagree and no certified identifying information action is available",
    )


def verify_plan_certificate(
    certificate: PlanCertificate,
    *,
    ledger: EpistemicMemoryLedger,
    context_scope: Sequence[str],
    worlds: Sequence[WorldBranch],
) -> bool:
    if not isinstance(certificate, PlanCertificate):
        return False
    scope = _norm(tuple(context_scope))
    if certificate.context_scope != scope:
        return False
    if certificate.certificate_digest != _sha(certificate.payload()):
        return False

    current_memories: list[tuple[str, str]] = []
    for mid, _ in certificate.memory_bindings:
        try:
            rec = ledger.record(mid)
        except KeyError:
            return False
        current_memories.append((mid, rec.memory_digest))
    if tuple(sorted(current_memories)) != certificate.memory_bindings:
        return False

    try:
        ww, _ = _validate_worlds(worlds)
    except Exception:
        return False
    bindings = tuple(sorted((w.world_id, w.digest) for w in ww))
    if bindings != certificate.world_bindings:
        return False
    return True
