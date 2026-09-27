from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType


def _digest(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _finite_nonnegative(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and >= 0")
    return value


class RiskClass(str, Enum):
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    CATASTROPHIC = "CATASTROPHIC"


class ComputeDirective(str, Enum):
    STOP = "STOP"
    LOCAL_PROBE = "LOCAL_PROBE"
    COUNTERMODEL = "COUNTERMODEL"
    RETRIEVE = "RETRIEVE"
    CRITIC = "CRITIC"
    EXTERNAL_MODEL = "EXTERNAL_MODEL"
    TOOL_CALL = "TOOL_CALL"
    HUMAN_ESCALATE = "HUMAN_ESCALATE"
    ABSTAIN = "ABSTAIN"


@dataclass(frozen=True, slots=True)
class Perturbation:
    perturbation_id: str
    target_variable: str
    baseline_value: str
    perturbed_value: str
    intervention_type: str
    provenance: str
    plausibility_weight: float
    causal_dependencies: tuple[str, ...] = ()
    estimated_cost: float = 0.0
    structural_model_digest: str | None = None

    def __post_init__(self) -> None:
        if not self.perturbation_id.strip():
            raise ValueError("perturbation_id required")
        if not self.target_variable.strip():
            raise ValueError("target_variable required")
        if not self.intervention_type.strip():
            raise ValueError("intervention_type required")
        if not self.provenance.strip():
            raise ValueError("provenance required")
        object.__setattr__(self, "plausibility_weight", _finite_nonnegative("plausibility_weight", self.plausibility_weight))
        object.__setattr__(self, "estimated_cost", _finite_nonnegative("estimated_cost", self.estimated_cost))
        object.__setattr__(self, "causal_dependencies", tuple(sorted({x.strip() for x in self.causal_dependencies if x.strip()})))
        structural = self.structural_model_digest.strip() if self.structural_model_digest else None
        if self.intervention_type == "CAUSAL_INTERVENTION" and (not structural or not self.causal_dependencies):
            raise ValueError("causal intervention requires structural_model_digest and causal_dependencies")
        object.__setattr__(self, "structural_model_digest", structural)

    @property
    def digest(self) -> str:
        return _digest(
            {
                "perturbation_id": self.perturbation_id,
                "target_variable": self.target_variable,
                "baseline_value": self.baseline_value,
                "perturbed_value": self.perturbed_value,
                "intervention_type": self.intervention_type,
                "provenance": self.provenance,
                "plausibility_weight": self.plausibility_weight,
                "causal_dependencies": list(self.causal_dependencies),
                "estimated_cost": self.estimated_cost,
                "structural_model_digest": self.structural_model_digest,
            }
        )


@dataclass(frozen=True, slots=True)
class CandidateOperation:
    operation_id: str
    directive: ComputeDirective
    estimated_cost: float
    token_cost: float = 0.0
    money_cost: float = 0.0
    time_cost: float = 0.0
    gpu_cost: float = 0.0
    metadata: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.operation_id.strip():
            raise ValueError("operation_id required")
        for name in ("estimated_cost", "token_cost", "money_cost", "time_cost", "gpu_cost"):
            object.__setattr__(self, name, _finite_nonnegative(name, getattr(self, name)))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class DecisionGradientCertificate:
    baseline_action: str
    perturbations_examined: tuple[str, ...]
    decision_flip_count: int
    expected_regret: float
    worst_case_regret: float
    weighted_regret: float
    effective_weight: float
    regret_by_perturbation: Mapping[str, float]
    decision_digest: str

    def __post_init__(self) -> None:
        if not self.baseline_action.strip():
            raise ValueError("baseline_action required")
        if self.decision_flip_count < 0:
            raise ValueError("decision_flip_count must be >= 0")
        for name in ("expected_regret", "worst_case_regret", "weighted_regret", "effective_weight"):
            object.__setattr__(self, name, _finite_nonnegative(name, getattr(self, name)))
        object.__setattr__(self, "regret_by_perturbation", MappingProxyType(dict(self.regret_by_perturbation)))


@dataclass(frozen=True, slots=True)
class ComputeDecision:
    directive: ComputeDirective
    operation_id: str | None
    reason_code: str
    predicted_voc: float | None
    predicted_voc_lower: float | None
    predicted_voc_upper: float | None
    budget_digest: str
    decision_digest: str


def bind_decision_digest(
    *,
    baseline_action: str,
    source_state_digest: str,
    utility_digest: str,
    perturbations: Sequence[Perturbation],
    regrets: Mapping[str, float],
) -> str:
    return _digest(
        {
            "baseline_action": baseline_action,
            "source_state_digest": source_state_digest,
            "utility_digest": utility_digest,
            "perturbations": [(p.perturbation_id, p.digest) for p in perturbations],
            "regrets": {k: regrets[k] for k in sorted(regrets)},
        }
    )
