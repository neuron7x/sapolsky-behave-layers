from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import Enum


def _digest(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


class MonitoringCategory(str, Enum):
    FUNCTIONALITY = "FUNCTIONALITY"
    OPERATIONAL = "OPERATIONAL"
    HUMAN_FACTORS = "HUMAN_FACTORS"
    SECURITY = "SECURITY"
    COMPLIANCE = "COMPLIANCE"
    LARGE_SCALE_IMPACTS = "LARGE_SCALE_IMPACTS"


class ObservationStatus(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class AssuranceDecision(str, Enum):
    CONTINUE = "CONTINUE"
    HOLD = "HOLD"
    ROLLBACK = "ROLLBACK"


@dataclass(frozen=True, slots=True)
class MonitoringSpec:
    deployment_digest: str
    required_categories: tuple[MonitoringCategory, ...]
    max_age_ticks: tuple[tuple[MonitoringCategory, int], ...]
    human_validation_required: tuple[MonitoringCategory, ...]
    max_warn_risk_sum: float

    def __post_init__(self):
        if len(self.deployment_digest.strip()) < 16:
            raise ValueError("deployment_digest must be non-trivial")
        categories = tuple(sorted(set(self.required_categories), key=lambda x: x.value))
        if not categories:
            raise ValueError("required_categories must be non-empty")
        if len(categories) != len(self.required_categories):
            raise ValueError("required_categories must be unique")
        object.__setattr__(self, "required_categories", categories)
        ages = dict(self.max_age_ticks)
        if set(ages) != set(categories):
            raise ValueError("max_age_ticks must specify every and only required category")
        if any(int(v) <= 0 for v in ages.values()):
            raise ValueError("max_age_ticks values must be > 0")
        human = tuple(sorted(set(self.human_validation_required), key=lambda x: x.value))
        if not set(human).issubset(set(categories)):
            raise ValueError("human validation categories must be required categories")
        object.__setattr__(self, "human_validation_required", human)
        risk = float(self.max_warn_risk_sum)
        if not math.isfinite(risk) or risk < 0:
            raise ValueError("max_warn_risk_sum must be finite and >=0")
        object.__setattr__(self, "max_warn_risk_sum", risk)

    @property
    def age_map(self) -> dict[MonitoringCategory, int]:
        return dict(self.max_age_ticks)

    @property
    def digest(self) -> str:
        return _digest({
            "deployment_digest": self.deployment_digest,
            "required_categories": [x.value for x in self.required_categories],
            "max_age_ticks": [(k.value, v) for k, v in sorted(self.max_age_ticks, key=lambda x: x[0].value)],
            "human_validation_required": [x.value for x in self.human_validation_required],
            "max_warn_risk_sum": self.max_warn_risk_sum,
        })


@dataclass(frozen=True, slots=True)
class MonitoringObservation:
    category: MonitoringCategory
    metric_id: str
    tick: int
    status: ObservationStatus
    risk_score: float
    deployment_digest: str
    evidence_digest: str
    source_id: str
    human_validated: bool = False

    def __post_init__(self):
        if not self.metric_id.strip() or not self.source_id.strip():
            raise ValueError("metric_id and source_id required")
        if self.tick < 0:
            raise ValueError("tick must be >=0")
        risk = float(self.risk_score)
        if not math.isfinite(risk) or not 0 <= risk <= 1:
            raise ValueError("risk_score must be in [0,1]")
        object.__setattr__(self, "risk_score", risk)
        if len(self.deployment_digest.strip()) < 16 or len(self.evidence_digest.strip()) < 16:
            raise ValueError("deployment/evidence digests must be non-trivial")

    @property
    def key(self):
        return (self.category, self.metric_id, self.tick, self.source_id)


@dataclass(frozen=True, slots=True)
class AssuranceCertificate:
    deployment_digest: str
    spec_digest: str
    as_of_tick: int
    decision: AssuranceDecision
    reasons: tuple[str, ...]
    category_status: tuple[tuple[str, str], ...]
    observation_population_digest: str


class ContinuousAssuranceMonitor:
    def __init__(self, spec: MonitoringSpec):
        self.spec = spec
        self._observations: dict[tuple, MonitoringObservation] = {}

    def ingest(self, observation: MonitoringObservation) -> None:
        if observation.deployment_digest != self.spec.deployment_digest:
            raise ValueError("observation deployment digest mismatch")
        if observation.category not in self.spec.required_categories:
            raise ValueError("observation category outside frozen monitoring scope")
        existing = self._observations.get(observation.key)
        if existing is not None:
            if existing == observation:
                return
            raise ValueError("conflicting duplicate monitoring observation")
        self._observations[observation.key] = observation

    def evaluate(self, *, as_of_tick: int) -> AssuranceCertificate:
        if as_of_tick < 0:
            raise ValueError("as_of_tick must be >=0")
        reasons = []
        category_status = []
        rollback = False
        hold = False
        warn_risk = 0.0
        age_map = self.spec.age_map

        for category in self.spec.required_categories:
            rows = [o for o in self._observations.values() if o.category is category and o.tick <= as_of_tick]
            if not rows:
                reasons.append(f"MISSING:{category.value}")
                category_status.append((category.value, "MISSING"))
                hold = True
                continue
            latest_tick = max(o.tick for o in rows)
            latest = [o for o in rows if o.tick == latest_tick]
            age = as_of_tick - latest_tick
            if age > age_map[category]:
                reasons.append(f"STALE:{category.value}:age={age}")
                category_status.append((category.value, "STALE"))
                hold = True
                continue
            if category in self.spec.human_validation_required and not any(o.human_validated for o in latest):
                reasons.append(f"HUMAN_VALIDATION_MISSING:{category.value}")
                category_status.append((category.value, "UNVALIDATED"))
                hold = True
                continue
            statuses = {o.status for o in latest}
            if ObservationStatus.FAIL in statuses:
                reasons.append(f"FAIL:{category.value}")
                category_status.append((category.value, "FAIL"))
                rollback = True
                continue
            if ObservationStatus.WARN in statuses:
                category_status.append((category.value, "WARN"))
                warn_risk += sum(o.risk_score for o in latest if o.status is ObservationStatus.WARN)
            else:
                category_status.append((category.value, "PASS"))

        if warn_risk > self.spec.max_warn_risk_sum + 1e-12:
            reasons.append(f"WARN_RISK_SUM_EXCEEDED:{warn_risk:.6f}")
            hold = True

        decision = AssuranceDecision.ROLLBACK if rollback else AssuranceDecision.HOLD if hold else AssuranceDecision.CONTINUE
        rows = sorted((o.category.value, o.metric_id, o.tick, o.status.value, o.risk_score, o.evidence_digest, o.source_id, o.human_validated) for o in self._observations.values() if o.tick <= as_of_tick)
        return AssuranceCertificate(
            deployment_digest=self.spec.deployment_digest,
            spec_digest=self.spec.digest,
            as_of_tick=as_of_tick,
            decision=decision,
            reasons=tuple(reasons),
            category_status=tuple(category_status),
            observation_population_digest=_digest(rows),
        )
