"""Portable, memory-free CWC plan admission with a separate finite-world critic.

No side effects are performed by verification. No completeness of the supplied
world set, causal truth, or general production authority is asserted.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from typing import Any, TypeVar

from cwc.governance.verifier_qualification import Action, VerificationDecision, canonical_bytes, digest
from cwc.memory.epistemic_store import EpistemicMemoryLedger
from cwc.planning.proof_carrying import PlanState, WorldBranch, plan_counterfactual

SCHEMA = "CWC_MEMORY_FREE_PLAN_ADMISSION_V1"
MAX_INPUT_BYTES = 1 << 20
MAX_WORLDS = 256
MAX_ACTIONS = 64
_T = TypeVar("_T")
_REJECT = VerificationDecision("FAIL", "STOP")
_UNKNOWN = VerificationDecision("UNKNOWN", "UNRESOLVED")
_CERTIFICATE_FIELDS = frozenset(
    {
        "plan_id",
        "context_scope",
        "decision_state",
        "selected_action",
        "memory_bindings",
        "world_bindings",
        "robust_margin",
        "information_state",
        "information_action_id",
        "necessary_information_cost",
        "reason",
        "certificate_digest",
    }
)


class AdmissionBlocked(RuntimeError):
    """The executor was not invoked."""


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _bad_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


def _number(value: object) -> bool:
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and value == value.strip()


def _document(raw: bytes) -> dict[str, Any]:
    if type(raw) is not bytes or not raw or len(raw) > MAX_INPUT_BYTES:
        raise ValueError("invalid input byte size")
    doc = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_pairs, parse_constant=_bad_constant)
    if not isinstance(doc, dict) or set(doc) != {"schema", "context_scope", "worlds", "certificate"}:
        raise ValueError("invalid top-level fields")
    if not isinstance(doc["schema"], str):
        raise ValueError("schema must be text")
    scope, worlds, cert = doc["context_scope"], doc["worlds"], doc["certificate"]
    if not isinstance(scope, list) or not scope or not all(_text(x) for x in scope):
        raise ValueError("context scope required")
    if len(scope) != len(set(scope)):
        raise ValueError("duplicate context scope")
    if not isinstance(worlds, list) or not 1 <= len(worlds) <= MAX_WORLDS or not isinstance(cert, dict):
        raise ValueError("bounded worlds and certificate required")
    if set(cert) != _CERTIFICATE_FIELDS:
        raise ValueError("missing or extra certificate fields")
    ids: set[str] = set()
    action_set: set[str] | None = None
    for world in worlds:
        if not isinstance(world, dict) or set(world) != {"world_id", "utilities", "provenance"}:
            raise ValueError("invalid world fields")
        if not _text(world["world_id"]) or not _text(world["provenance"]) or world["world_id"] in ids:
            raise ValueError("invalid/duplicate world identity")
        ids.add(world["world_id"])
        utilities = world["utilities"]
        if not isinstance(utilities, dict) or not 2 <= len(utilities) <= MAX_ACTIONS:
            raise ValueError("bounded action set required")
        if not all(_text(k) and _number(v) for k, v in utilities.items()):
            raise ValueError("finite numeric utilities and canonical action names required")
        if action_set is not None and set(utilities) != action_set:
            raise ValueError("all worlds must share an action set")
        action_set = set(utilities)
    if not _text(cert.get("plan_id")) or not _number(cert.get("robust_margin")) or cert["robust_margin"] <= 0:
        raise ValueError("plan ID and finite positive margin required")
    return doc


def _in_scope(doc: dict[str, Any]) -> bool:
    cert = doc["certificate"]
    return (
        doc["schema"] == SCHEMA
        and cert.get("memory_bindings") == []
        and all(
            cert.get(key) is None
            for key in ("information_state", "information_action_id", "necessary_information_cost")
        )
    )


def verify_planner_document(raw: bytes) -> VerificationDecision:
    """Verify against a fresh native planner result, not a self-reported hash."""
    try:
        doc = _document(raw)
        if not _in_scope(doc):
            return _UNKNOWN
        cert = doc["certificate"]
        worlds = [WorldBranch(w["world_id"], w["utilities"], w["provenance"]) for w in doc["worlds"]]
        result = plan_counterfactual(
            ledger=EpistemicMemoryLedger(),
            plan_id=cert["plan_id"],
            context_scope=doc["context_scope"],
            required_memories=(),
            worlds=worlds,
            robust_margin=cert["robust_margin"],
        )
        expected = {**result.certificate.payload(), "certificate_digest": result.certificate.certificate_digest}
        # Byte-normalized comparison keeps True distinct from 1 and preserves the
        # native certificate's explicit numeric representation.
        if canonical_bytes(cert) != canonical_bytes(expected):
            return _REJECT
        if result.state is PlanState.ROBUST_ACTION:
            return VerificationDecision("PASS", "SUBMIT", result.selected_action)
        if result.state is PlanState.ABSTAIN_WORLD_DISAGREEMENT:
            return VerificationDecision("PASS", "ESCALATE")
        return VerificationDecision("PASS", "STOP")
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError, UnicodeError):
        return _REJECT


def critic_planner_document(raw: bytes) -> VerificationDecision:
    """Independent pairwise oracle; never calls the planner or verifier above.

    Shares only strict input validation and canonical encoding. This is algorithmic
    diversity, not social independence or a proof of oracle completeness.
    """
    try:
        doc = _document(raw)
        if not _in_scope(doc):
            return _UNKNOWN
        cert = dict(doc["certificate"])
        claimed_digest = cert.pop("certificate_digest", None)
        if digest(canonical_bytes(cert)) != claimed_digest:
            return _REJECT
        bindings = []
        normalized_worlds = []
        for world in doc["worlds"]:
            normalized = {**world, "utilities": {k: float(v) for k, v in world["utilities"].items()}}
            normalized_worlds.append(normalized)
            bindings.append([world["world_id"], digest(canonical_bytes(normalized))])
        if cert.get("world_bindings") != sorted(bindings) or cert.get("context_scope") != sorted(doc["context_scope"]):
            return _REJECT
        margin = cert["robust_margin"]
        if type(margin) is not float:
            return _REJECT
        # Pairwise inequalities, rather than the native planner's ranking routine.
        actions = tuple(normalized_worlds[0]["utilities"])
        robust = [
            a
            for a in actions
            if all(
                world["utilities"][a] - world["utilities"][b] >= margin
                for world in normalized_worlds
                for b in actions
                if b != a
            )
        ]
        shared_tops = [
            a
            for a in actions
            if all(
                world["utilities"][a] > world["utilities"][b]
                or (world["utilities"][a] == world["utilities"][b] and a <= b)
                for world in normalized_worlds
                for b in actions
            )
        ]
        action: Action
        selected: str | None
        if len(robust) == 1:
            state, selected, action = "ROBUST_ACTION", robust[0], "SUBMIT"
            reason = (
                "same action uniquely dominates by the frozen margin in every admitted world; no world averaging used"
            )
        elif shared_tops:
            state, selected, action = "ABSTAIN_NO_UNIQUE_ROBUST_ACTION", None, "STOP"
            reason = "nominal top action is shared but at least one world fails the frozen robust-margin requirement"
        else:
            state, selected, action = "ABSTAIN_WORLD_DISAGREEMENT", None, "ESCALATE"
            reason = "admitted worlds disagree and no certified identifying information action is available"
        expected = {
            "plan_id": cert["plan_id"],
            "context_scope": sorted(doc["context_scope"]),
            "decision_state": state,
            "selected_action": selected,
            "memory_bindings": [],
            "world_bindings": sorted(bindings),
            "robust_margin": margin,
            "information_state": None,
            "information_action_id": None,
            "necessary_information_cost": None,
            "reason": reason,
        }
        if canonical_bytes(cert) != canonical_bytes(expected):
            return _REJECT
        return VerificationDecision("PASS", action, selected)
    except (ValueError, TypeError, KeyError, OverflowError, RecursionError, UnicodeError):
        return _REJECT


def execute_verified_plan(
    raw: bytes,
    *,
    expected_input_sha256: str,
    executor: Callable[[str], _T],
) -> _T:
    """Invoke the effectful callback once, only after both implementations agree.

    The expected digest belongs to the caller's frozen request. A hash is a
    binding, not authorization, authenticity, or proof of external-world truth.
    Non-SUBMIT outcomes never invoke the callback; escalation is machine-routable.
    """
    if type(raw) is not bytes or digest(raw) != expected_input_sha256:
        raise AdmissionBlocked("STOP: request bytes differ from the frozen input digest")
    verdict = verify_planner_document(raw)
    critic = critic_planner_document(raw)
    if verdict != critic or verdict.action != "SUBMIT" or verdict.selected_action is None:
        raise AdmissionBlocked(f"{verdict.action}: no agreed executable action")
    return executor(verdict.selected_action)
