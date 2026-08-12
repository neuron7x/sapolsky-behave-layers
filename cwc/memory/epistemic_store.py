from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import Enum

from cwc.epistemics.lattice import EpistemicRecord, EpistemicState

_MEMORY_MINT_SEAL = object()


class MemoryError(RuntimeError):
    """Base class for epistemic-memory failures."""


class MemoryBindingError(MemoryError):
    """Raised when a memory cannot be bound to the supplied epistemic record."""


class DependencyError(MemoryError):
    """Raised for invalid or cyclic/nonexistent dependency requests."""


class MemoryStatus(str, Enum):
    ACTIVE = "ACTIVE"
    QUARANTINED = "QUARANTINED"
    RETRACTED = "RETRACTED"


class MemoryEventType(str, Enum):
    CONSOLIDATE = "CONSOLIDATE"
    RETRACT = "RETRACT"
    ASSUMPTION_INVALIDATE = "ASSUMPTION_INVALIDATE"


def _norm(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(v).strip() for v in values if str(v).strip()}))


def _sha(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True, slots=True, init=False)
class MemoryRecord:
    memory_id: str
    claim_id: str
    epistemic_record_digest: str
    epistemic_state: EpistemicState
    context_scope: tuple[str, ...]
    assumption_ids: tuple[str, ...]
    operator_id: str | None
    evidence_hashes: tuple[str, ...]
    countermodel_ids: tuple[str, ...]
    dependency_ids: tuple[str, ...]
    revision_of: str | None
    version: int
    previous_record_digest: str | None
    status: MemoryStatus
    causal_consolidated: bool
    reason: str
    memory_digest: str

    def __new__(cls, *args: object, **kwargs: object) -> MemoryRecord:
        raise TypeError("MemoryRecord can only be constructed by EpistemicMemoryLedger")

    @classmethod
    def _mint(
        cls,
        *,
        memory_id: str,
        claim_id: str,
        epistemic_record_digest: str,
        epistemic_state: EpistemicState,
        context_scope: Sequence[str],
        assumption_ids: Sequence[str],
        operator_id: str | None,
        evidence_hashes: Sequence[str],
        countermodel_ids: Sequence[str],
        dependency_ids: Sequence[str],
        revision_of: str | None,
        version: int,
        previous_record_digest: str | None,
        status: MemoryStatus,
        causal_consolidated: bool,
        reason: str,
        _seal: object,
    ) -> MemoryRecord:
        if _seal is not _MEMORY_MINT_SEAL:
            raise TypeError("invalid memory mint seal")
        if not memory_id.strip() or not claim_id.strip():
            raise ValueError("memory_id and claim_id must be non-empty")
        scope = _norm(context_scope)
        if not scope:
            raise ValueError("context_scope must be non-empty")
        assumptions = _norm(assumption_ids)
        evidence = _norm(evidence_hashes)
        counters = _norm(countermodel_ids)
        deps = _norm(dependency_ids)
        if version < 1:
            raise ValueError("memory version must be >=1")
        if causal_consolidated:
            if status is not MemoryStatus.ACTIVE:
                raise ValueError("causal-consolidated memory must be ACTIVE")
            if epistemic_state is not EpistemicState.INTERVENTION_SUPPORTED:
                raise ValueError("causal-consolidated memory requires INTERVENTION_SUPPORTED")
            if counters:
                raise ValueError("causal-consolidated memory cannot retain surviving countermodels")
        payload = {
            "memory_id": memory_id,
            "claim_id": claim_id,
            "epistemic_record_digest": epistemic_record_digest,
            "epistemic_state": epistemic_state.value,
            "context_scope": list(scope),
            "assumption_ids": list(assumptions),
            "operator_id": operator_id,
            "evidence_hashes": list(evidence),
            "countermodel_ids": list(counters),
            "dependency_ids": list(deps),
            "revision_of": revision_of,
            "version": version,
            "previous_record_digest": previous_record_digest,
            "status": status.value,
            "causal_consolidated": causal_consolidated,
            "reason": reason,
        }
        obj = object.__new__(cls)
        for key, value in {
            "memory_id": memory_id,
            "claim_id": claim_id,
            "epistemic_record_digest": epistemic_record_digest,
            "epistemic_state": epistemic_state,
            "context_scope": scope,
            "assumption_ids": assumptions,
            "operator_id": operator_id,
            "evidence_hashes": evidence,
            "countermodel_ids": counters,
            "dependency_ids": deps,
            "revision_of": revision_of,
            "version": version,
            "previous_record_digest": previous_record_digest,
            "status": status,
            "causal_consolidated": bool(causal_consolidated),
            "reason": reason,
            "memory_digest": _sha(payload),
        }.items():
            object.__setattr__(obj, key, value)
        return obj

    def as_dict(self) -> dict[str, object]:
        return {
            "memory_id": self.memory_id,
            "claim_id": self.claim_id,
            "epistemic_record_digest": self.epistemic_record_digest,
            "epistemic_state": self.epistemic_state.value,
            "context_scope": list(self.context_scope),
            "assumption_ids": list(self.assumption_ids),
            "operator_id": self.operator_id,
            "evidence_hashes": list(self.evidence_hashes),
            "countermodel_ids": list(self.countermodel_ids),
            "dependency_ids": list(self.dependency_ids),
            "revision_of": self.revision_of,
            "version": self.version,
            "previous_record_digest": self.previous_record_digest,
            "status": self.status.value,
            "causal_consolidated": self.causal_consolidated,
            "reason": self.reason,
            "memory_digest": self.memory_digest,
        }


@dataclass(frozen=True, slots=True)
class MemoryEvent:
    sequence: int
    event_type: MemoryEventType
    memory_id: str
    previous_event_hash: str | None
    record_digest: str
    reason: str
    event_hash: str

    @classmethod
    def create(
        cls,
        *,
        sequence: int,
        event_type: MemoryEventType,
        memory_id: str,
        previous_event_hash: str | None,
        record_digest: str,
        reason: str,
    ) -> MemoryEvent:
        payload = {
            "sequence": sequence,
            "event_type": event_type.value,
            "memory_id": memory_id,
            "previous_event_hash": previous_event_hash,
            "record_digest": record_digest,
            "reason": reason,
        }
        return cls(
            sequence=sequence,
            event_type=event_type,
            memory_id=memory_id,
            previous_event_hash=previous_event_hash,
            record_digest=record_digest,
            reason=reason,
            event_hash=_sha(payload),
        )


class EpistemicMemoryLedger:
    """Append-only-versioned memory store bound to typed epistemic authority.

    Retractions create new immutable record versions and hash-chained events.  The
    current view is mutable only by appending a new version; old versions remain in
    history and can be audited.
    """

    def __init__(self) -> None:
        self._current: dict[str, MemoryRecord] = {}
        self._history: dict[str, list[MemoryRecord]] = {}
        self._events: list[MemoryEvent] = []
        self._invalidated_assumptions: set[str] = set()

    @property
    def events(self) -> tuple[MemoryEvent, ...]:
        return tuple(self._events)

    @property
    def memory_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._current))

    @property
    def invalidated_assumptions(self) -> tuple[str, ...]:
        return tuple(sorted(self._invalidated_assumptions))

    def record(self, memory_id: str) -> MemoryRecord:
        try:
            return self._current[memory_id]
        except KeyError as exc:
            raise KeyError(f"unknown memory {memory_id!r}") from exc

    def history(self, memory_id: str) -> tuple[MemoryRecord, ...]:
        try:
            return tuple(self._history[memory_id])
        except KeyError as exc:
            raise KeyError(f"unknown memory {memory_id!r}") from exc

    def consolidate(
        self,
        *,
        memory_id: str,
        epistemic_record: EpistemicRecord,
        countermodel_ids: Sequence[str] = (),
        dependency_ids: Sequence[str] = (),
        revision_of: str | None = None,
        reason: str = "epistemic memory consolidation",
    ) -> MemoryRecord:
        if not isinstance(epistemic_record, EpistemicRecord):
            raise TypeError("epistemic_record must be a typed EpistemicRecord; legacy strings are forbidden")
        if memory_id in self._current:
            raise ValueError(f"duplicate memory_id {memory_id!r}; create a new memory id/version lineage")
        deps = _norm(dependency_ids)
        for dep in deps:
            if dep not in self._current:
                raise DependencyError(f"unknown dependency {dep!r}")
        if revision_of is not None and revision_of not in self._current:
            raise DependencyError(f"unknown revision_of memory {revision_of!r}")

        counters = _norm(countermodel_ids)
        assumptions = epistemic_record.assumption_ids
        invalid_assumption = any(a in self._invalidated_assumptions for a in assumptions)
        dependencies_active = all(self._current[d].status is MemoryStatus.ACTIVE for d in deps)

        state = epistemic_record.state
        causal = False
        if state in {EpistemicState.OBSERVED, EpistemicState.PREDICTIVE}:
            status = MemoryStatus.ACTIVE if dependencies_active else MemoryStatus.QUARANTINED
            local_reason = "active noncausal memory" if status is MemoryStatus.ACTIVE else "dependency not active"
        elif state is EpistemicState.ASSUMPTION_CONDITIONAL:
            status = MemoryStatus.QUARANTINED
            local_reason = "assumption-conditional authority cannot be causal-consolidated"
        elif state is EpistemicState.INTERVENTION_SUPPORTED:
            if not counters and dependencies_active and not invalid_assumption:
                status = MemoryStatus.ACTIVE
                causal = True
                local_reason = "operator-scoped intervention-supported causal memory"
            else:
                status = MemoryStatus.QUARANTINED
                local_reason = "countermodel/dependency/assumption debt blocks causal consolidation"
        else:
            status = MemoryStatus.RETRACTED
            local_reason = f"terminal epistemic state {state.value} cannot create active memory"

        evidence_hashes = tuple(sorted({e.sha256 for e in epistemic_record.evidence}))
        rec = MemoryRecord._mint(
            memory_id=memory_id,
            claim_id=epistemic_record.claim_id,
            epistemic_record_digest=epistemic_record.record_digest,
            epistemic_state=state,
            context_scope=epistemic_record.context_scope,
            assumption_ids=assumptions,
            operator_id=epistemic_record.operator_id,
            evidence_hashes=evidence_hashes,
            countermodel_ids=counters,
            dependency_ids=deps,
            revision_of=revision_of,
            version=1,
            previous_record_digest=None,
            status=status,
            causal_consolidated=causal,
            reason=f"{reason}: {local_reason}",
            _seal=_MEMORY_MINT_SEAL,
        )
        self._current[memory_id] = rec
        self._history[memory_id] = [rec]
        self._append_event(MemoryEventType.CONSOLIDATE, rec, rec.reason)
        return rec

    def verify_binding(self, memory_id: str, epistemic_record: EpistemicRecord) -> bool:
        if not isinstance(epistemic_record, EpistemicRecord):
            return False
        rec = self.record(memory_id)
        return (
            rec.claim_id == epistemic_record.claim_id
            and rec.epistemic_record_digest == epistemic_record.record_digest
            and rec.epistemic_state is epistemic_record.state
            and rec.context_scope == epistemic_record.context_scope
            and rec.assumption_ids == epistemic_record.assumption_ids
            and rec.operator_id == epistemic_record.operator_id
            and rec.evidence_hashes == tuple(sorted({e.sha256 for e in epistemic_record.evidence}))
        )

    def retract(self, memory_id: str, *, reason: str) -> tuple[str, ...]:
        if not reason.strip():
            raise ValueError("retraction reason must be non-empty")
        if memory_id not in self._current:
            raise KeyError(f"unknown memory {memory_id!r}")
        targets = self._dependency_closure({memory_id})
        # Parent-first deterministic ordering by dependency depth is not needed for
        # correctness because every target is forced terminal, but lexical ordering
        # makes the event ledger reproducible.
        changed: list[str] = []
        for mid in sorted(targets):
            if self._current[mid].status is MemoryStatus.RETRACTED:
                continue
            self._revise_status(mid, MemoryStatus.RETRACTED, False, f"retracted: {reason}")
            changed.append(mid)
        return tuple(changed)

    def invalidate_assumption(self, assumption_id: str, *, reason: str) -> tuple[str, ...]:
        assumption_id = assumption_id.strip()
        if not assumption_id:
            raise ValueError("assumption_id must be non-empty")
        self._invalidated_assumptions.add(assumption_id)
        roots = {mid for mid, rec in self._current.items() if assumption_id in rec.assumption_ids}
        targets = self._dependency_closure(roots)
        changed: list[str] = []
        for mid in sorted(targets):
            if self._current[mid].status is MemoryStatus.RETRACTED:
                continue
            self._revise_status(mid, MemoryStatus.RETRACTED, False, f"assumption {assumption_id} invalidated: {reason}")
            changed.append(mid)
        # Record an assumption-level event even if no memory currently depends on it.
        synthetic_digest = _sha({"assumption_id": assumption_id, "reason": reason, "targets": sorted(targets)})
        self._append_raw_event(
            MemoryEventType.ASSUMPTION_INVALIDATE, f"assumption:{assumption_id}", synthetic_digest, reason
        )
        return tuple(changed)

    def event_chain_valid(self) -> bool:
        prev: str | None = None
        for idx, event in enumerate(self._events, start=1):
            payload = {
                "sequence": idx,
                "event_type": event.event_type.value,
                "memory_id": event.memory_id,
                "previous_event_hash": prev,
                "record_digest": event.record_digest,
                "reason": event.reason,
            }
            if event.sequence != idx or event.previous_event_hash != prev or event.event_hash != _sha(payload):
                return False
            prev = event.event_hash
        return True

    def assert_invariants(self) -> None:
        if not self.event_chain_valid():
            raise MemoryBindingError("memory event hash chain invalid")
        for mid, rec in self._current.items():
            if rec.causal_consolidated:
                if rec.status is not MemoryStatus.ACTIVE:
                    raise MemoryBindingError(f"{mid}: causal memory not active")
                if rec.epistemic_state is not EpistemicState.INTERVENTION_SUPPORTED:
                    raise MemoryBindingError(f"{mid}: causal memory lacks intervention support")
                if rec.countermodel_ids:
                    raise MemoryBindingError(f"{mid}: causal memory retains countermodels")
                if any(a in self._invalidated_assumptions for a in rec.assumption_ids):
                    raise MemoryBindingError(f"{mid}: causal memory depends on invalidated assumption")
                if any(self._current[d].status is not MemoryStatus.ACTIVE for d in rec.dependency_ids):
                    raise MemoryBindingError(f"{mid}: causal memory depends on inactive memory")

    def _dependency_closure(self, roots: set[str]) -> set[str]:
        targets = set(roots)
        changed = True
        while changed:
            changed = False
            for mid, rec in self._current.items():
                if mid in targets:
                    continue
                if any(dep in targets for dep in rec.dependency_ids):
                    targets.add(mid)
                    changed = True
        return targets

    def _revise_status(self, memory_id: str, status: MemoryStatus, causal: bool, reason: str) -> MemoryRecord:
        old = self._current[memory_id]
        rec = MemoryRecord._mint(
            memory_id=old.memory_id,
            claim_id=old.claim_id,
            epistemic_record_digest=old.epistemic_record_digest,
            epistemic_state=old.epistemic_state,
            context_scope=old.context_scope,
            assumption_ids=old.assumption_ids,
            operator_id=old.operator_id,
            evidence_hashes=old.evidence_hashes,
            countermodel_ids=old.countermodel_ids,
            dependency_ids=old.dependency_ids,
            revision_of=old.revision_of,
            version=old.version + 1,
            previous_record_digest=old.memory_digest,
            status=status,
            causal_consolidated=causal,
            reason=reason,
            _seal=_MEMORY_MINT_SEAL,
        )
        self._current[memory_id] = rec
        self._history[memory_id].append(rec)
        self._append_event(MemoryEventType.RETRACT, rec, reason)
        return rec

    def _append_event(self, event_type: MemoryEventType, rec: MemoryRecord, reason: str) -> None:
        self._append_raw_event(event_type, rec.memory_id, rec.memory_digest, reason)

    def _append_raw_event(self, event_type: MemoryEventType, memory_id: str, record_digest: str, reason: str) -> None:
        prev = self._events[-1].event_hash if self._events else None
        event = MemoryEvent.create(
            sequence=len(self._events) + 1,
            event_type=event_type,
            memory_id=memory_id,
            previous_event_hash=prev,
            record_digest=record_digest,
            reason=reason,
        )
        self._events.append(event)
