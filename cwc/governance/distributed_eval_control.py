from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import Enum


def _digest(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def _positive_int(name: str, value: int) -> int:
    value = int(value)
    if value <= 0:
        raise ValueError(f"{name} must be > 0")
    return value


def _nonnegative_finite(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and >= 0")
    return value


class UnitState(str, Enum):
    PENDING = "PENDING"
    LEASED = "LEASED"
    COMMITTED = "COMMITTED"
    QUARANTINED = "QUARANTINED"


@dataclass(frozen=True, slots=True, order=True)
class WorkUnitId:
    task_id: str
    policy_id: str
    replicate: int

    def __post_init__(self) -> None:
        if not self.task_id.strip() or not self.policy_id.strip():
            raise ValueError("task_id and policy_id are required")
        if self.replicate < 0:
            raise ValueError("replicate must be >= 0")

    @property
    def stable_id(self) -> str:
        return f"{self.task_id}::{self.policy_id}::{self.replicate}"


@dataclass(frozen=True, slots=True)
class DistributedEvalSpec:
    experiment_id: str
    task_ids: tuple[str, ...]
    policy_ids: tuple[str, ...]
    replicates: int
    max_attempts_per_unit: int
    lease_ttl_ticks: int
    max_cost_per_unit_usd: float
    global_budget_usd: float
    harness_digest: str
    statistical_plan_digest: str

    def __post_init__(self) -> None:
        if not self.experiment_id.strip():
            raise ValueError("experiment_id required")
        tasks = tuple(sorted(set(x.strip() for x in self.task_ids if x.strip())))
        policies = tuple(sorted(set(x.strip() for x in self.policy_ids if x.strip())))
        if len(tasks) != len(self.task_ids) or not tasks:
            raise ValueError("task_ids must be non-empty and unique")
        if len(policies) != len(self.policy_ids) or not policies:
            raise ValueError("policy_ids must be non-empty and unique")
        object.__setattr__(self, "task_ids", tasks)
        object.__setattr__(self, "policy_ids", policies)
        object.__setattr__(self, "replicates", _positive_int("replicates", self.replicates))
        object.__setattr__(self, "max_attempts_per_unit", _positive_int("max_attempts_per_unit", self.max_attempts_per_unit))
        object.__setattr__(self, "lease_ttl_ticks", _positive_int("lease_ttl_ticks", self.lease_ttl_ticks))
        object.__setattr__(self, "max_cost_per_unit_usd", _nonnegative_finite("max_cost_per_unit_usd", self.max_cost_per_unit_usd))
        object.__setattr__(self, "global_budget_usd", _nonnegative_finite("global_budget_usd", self.global_budget_usd))
        if self.max_cost_per_unit_usd <= 0:
            raise ValueError("max_cost_per_unit_usd must be > 0")
        floor = len(tasks) * len(policies) * self.replicates * self.max_cost_per_unit_usd
        if self.global_budget_usd + 1e-12 < floor:
            raise ValueError("global_budget_usd must cover the preregistered worst-case one-attempt population")
        for name, value in (("harness_digest", self.harness_digest), ("statistical_plan_digest", self.statistical_plan_digest)):
            if len(value.strip()) < 16:
                raise ValueError(f"{name} must be a non-trivial frozen digest")

    @property
    def digest(self) -> str:
        return _digest({
            "experiment_id": self.experiment_id, "task_ids": self.task_ids,
            "policy_ids": self.policy_ids, "replicates": self.replicates,
            "max_attempts_per_unit": self.max_attempts_per_unit,
            "lease_ttl_ticks": self.lease_ttl_ticks,
            "max_cost_per_unit_usd": self.max_cost_per_unit_usd,
            "global_budget_usd": self.global_budget_usd,
            "harness_digest": self.harness_digest,
            "statistical_plan_digest": self.statistical_plan_digest,
        })

    def units(self) -> tuple[WorkUnitId, ...]:
        return tuple(WorkUnitId(t, p, r) for t in self.task_ids for p in self.policy_ids for r in range(self.replicates))


@dataclass(frozen=True, slots=True)
class Lease:
    unit: WorkUnitId
    worker_id: str
    attempt: int
    issued_tick: int
    expires_tick: int
    reserved_cost_usd: float
    token: str


@dataclass(frozen=True, slots=True)
class ResultRecord:
    unit: WorkUnitId
    attempt: int
    worker_id: str
    result_digest: str
    evidence_digest: str
    actual_cost_usd: float
    committed_tick: int


@dataclass(frozen=True, slots=True)
class AuditEvent:
    sequence: int
    kind: str
    unit_id: str | None
    payload_digest: str
    previous_digest: str
    event_digest: str


@dataclass(frozen=True, slots=True)
class CompletionCertificate:
    experiment_id: str
    spec_digest: str
    expected_units: int
    committed_units: int
    total_cost_usd: float
    audit_root_digest: str
    result_population_digest: str
    complete: bool


@dataclass
class _MutableUnit:
    state: UnitState = UnitState.PENDING
    attempts: int = 0
    lease: Lease | None = None
    result: ResultRecord | None = None
    quarantine_reason: str | None = None


class DistributedEvalCoordinator:
    """Fail-closed orchestration primitive; not evidence of frontier-scale operation."""

    def __init__(self, spec: DistributedEvalSpec):
        self.spec = spec
        self._units = {u: _MutableUnit() for u in spec.units()}
        self._spent_usd = 0.0
        self._reserved_usd = 0.0
        self._audit: list[AuditEvent] = []

    @property
    def spent_usd(self) -> float:
        return self._spent_usd

    @property
    def reserved_usd(self) -> float:
        return self._reserved_usd

    @property
    def remaining_unreserved_budget_usd(self) -> float:
        return self.spec.global_budget_usd - self._spent_usd - self._reserved_usd

    def _append_event(self, kind: str, unit: WorkUnitId | None, payload: object) -> AuditEvent:
        seq = len(self._audit)
        prev = self._audit[-1].event_digest if self._audit else "GENESIS"
        payload_digest = _digest(payload)
        event_digest = _digest({"sequence": seq, "kind": kind, "unit_id": unit.stable_id if unit else None, "payload_digest": payload_digest, "previous_digest": prev})
        event = AuditEvent(seq, kind, unit.stable_id if unit else None, payload_digest, prev, event_digest)
        self._audit.append(event)
        return event

    def _expire_due(self, tick: int) -> None:
        for unit in sorted(self._units):
            state = self._units[unit]
            lease = state.lease
            if state.state is UnitState.LEASED and lease is not None and tick >= lease.expires_tick:
                self._reserved_usd -= lease.reserved_cost_usd
                state.lease = None
                if state.attempts >= self.spec.max_attempts_per_unit:
                    state.state = UnitState.QUARANTINED
                    state.quarantine_reason = "LEASE_EXPIRED_MAX_ATTEMPTS"
                    self._append_event("QUARANTINE", unit, {"reason": state.quarantine_reason, "attempts": state.attempts, "tick": tick})
                else:
                    state.state = UnitState.PENDING
                    self._append_event("LEASE_EXPIRED", unit, {"attempts": state.attempts, "tick": tick})

    def claim(self, worker_id: str, *, tick: int) -> Lease | None:
        worker = worker_id.strip()
        if not worker:
            raise ValueError("worker_id required")
        if tick < 0:
            raise ValueError("tick must be >= 0")
        self._expire_due(tick)
        reserve = self.spec.max_cost_per_unit_usd
        if self.remaining_unreserved_budget_usd + 1e-12 < reserve:
            self._append_event("BUDGET_BLOCK", None, {"worker_id": worker, "tick": tick, "remaining": self.remaining_unreserved_budget_usd})
            return None
        for unit in sorted(self._units):
            state = self._units[unit]
            if state.state is not UnitState.PENDING:
                continue
            if state.attempts >= self.spec.max_attempts_per_unit:
                state.state = UnitState.QUARANTINED
                state.quarantine_reason = "MAX_ATTEMPTS_EXHAUSTED"
                self._append_event("QUARANTINE", unit, {"reason": state.quarantine_reason})
                continue
            attempt = state.attempts + 1
            token = _digest({"spec_digest": self.spec.digest, "unit": unit.stable_id, "worker_id": worker, "attempt": attempt, "issued_tick": tick})
            lease = Lease(unit, worker, attempt, tick, tick + self.spec.lease_ttl_ticks, reserve, token)
            state.attempts = attempt
            state.state = UnitState.LEASED
            state.lease = lease
            self._reserved_usd += reserve
            self._append_event("LEASE_GRANTED", unit, {"worker_id": worker, "attempt": attempt, "issued_tick": tick, "expires_tick": lease.expires_tick, "reserved_cost_usd": reserve, "token": token})
            return lease
        return None

    def commit(self, lease: Lease, *, tick: int, result_payload: object, evidence_digest: str, actual_cost_usd: float) -> ResultRecord:
        if tick < 0:
            raise ValueError("tick must be >= 0")
        cost = _nonnegative_finite("actual_cost_usd", actual_cost_usd)
        if cost > self.spec.max_cost_per_unit_usd + 1e-12:
            raise ValueError("actual cost exceeds frozen per-unit cap")
        if len(evidence_digest.strip()) < 16:
            raise ValueError("evidence_digest must be a non-trivial digest")
        state = self._units.get(lease.unit)
        if state is None:
            raise ValueError("unit not in frozen experiment population")
        result_digest = _digest(result_payload)
        if state.state is UnitState.COMMITTED and state.result is not None:
            existing = state.result
            if existing.result_digest == result_digest and existing.evidence_digest == evidence_digest:
                return existing
            state.state = UnitState.QUARANTINED
            state.quarantine_reason = "CONFLICTING_DUPLICATE_RESULT"
            self._append_event("QUARANTINE", lease.unit, {"reason": state.quarantine_reason, "existing_result_digest": existing.result_digest, "new_result_digest": result_digest})
            raise ValueError("conflicting duplicate result; unit quarantined")
        if state.state is not UnitState.LEASED or state.lease is None:
            raise ValueError("unit does not hold an active lease")
        active = state.lease
        if lease != active:
            raise ValueError("stale or forged lease")
        if tick >= active.expires_tick:
            self._expire_due(tick)
            raise ValueError("lease expired before commit")
        self._reserved_usd -= active.reserved_cost_usd
        projected = self._spent_usd + cost
        if projected > self.spec.global_budget_usd + 1e-12:
            state.state = UnitState.QUARANTINED
            state.lease = None
            state.quarantine_reason = "GLOBAL_BUDGET_BREACH"
            self._append_event("QUARANTINE", lease.unit, {"reason": state.quarantine_reason, "cost": cost})
            raise ValueError("global budget breach")
        record = ResultRecord(lease.unit, lease.attempt, lease.worker_id, result_digest, evidence_digest.strip(), cost, tick)
        self._spent_usd = projected
        state.state = UnitState.COMMITTED
        state.lease = None
        state.result = record
        self._append_event("RESULT_COMMITTED", lease.unit, {"attempt": record.attempt, "worker_id": record.worker_id, "result_digest": record.result_digest, "evidence_digest": record.evidence_digest, "actual_cost_usd": record.actual_cost_usd, "committed_tick": tick})
        return record

    def snapshot(self, *, tick: int) -> dict[str, object]:
        self._expire_due(tick)
        counts = {s.value: 0 for s in UnitState}
        for item in self._units.values():
            counts[item.state.value] += 1
        return {"experiment_id": self.spec.experiment_id, "spec_digest": self.spec.digest, "counts": counts, "spent_usd": self._spent_usd, "reserved_usd": self._reserved_usd, "remaining_unreserved_budget_usd": self.remaining_unreserved_budget_usd, "audit_root_digest": self._audit[-1].event_digest if self._audit else "GENESIS"}

    def completion_certificate(self, *, tick: int) -> CompletionCertificate:
        self._expire_due(tick)
        quarantined = [u for u, s in self._units.items() if s.state is UnitState.QUARANTINED]
        incomplete = [u for u, s in self._units.items() if s.state is not UnitState.COMMITTED]
        if quarantined:
            raise ValueError(f"experiment has quarantined units: {[u.stable_id for u in quarantined]}")
        if incomplete:
            raise ValueError(f"full preregistered coverage required; incomplete units={len(incomplete)}")
        records = [self._units[u].result for u in sorted(self._units)]
        rows = [(r.unit.stable_id, r.attempt, r.worker_id, r.result_digest, r.evidence_digest, r.actual_cost_usd) for r in records if r is not None]
        return CompletionCertificate(self.spec.experiment_id, self.spec.digest, len(self._units), len(rows), self._spent_usd, self._audit[-1].event_digest if self._audit else "GENESIS", _digest(rows), True)

    def audit_events(self) -> tuple[AuditEvent, ...]:
        return tuple(self._audit)

    def verify_audit_chain(self) -> bool:
        previous = "GENESIS"
        for seq, event in enumerate(self._audit):
            if event.sequence != seq or event.previous_digest != previous:
                return False
            expected = _digest({"sequence": event.sequence, "kind": event.kind, "unit_id": event.unit_id, "payload_digest": event.payload_digest, "previous_digest": event.previous_digest})
            if expected != event.event_digest:
                return False
            previous = event.event_digest
        return True
