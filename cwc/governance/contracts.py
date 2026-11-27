from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, fields
from enum import Enum
from fractions import Fraction
from types import MappingProxyType


def _digest(payload: object) -> str:
    raw = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _finite_nonnegative(name: str, value: float) -> float:
    value = float(value)
    if not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be finite and >= 0")
    return value


def _action_identifier(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("action identifier must be a non-empty string")
    return value.strip()


def _certificate_number(name: str, value: float) -> float:
    if type(value) not in (int, float):
        raise ValueError(f"{name} must be numeric")
    try:
        return _finite_nonnegative(name, value)
    except OverflowError as exc:
        raise ValueError(f"{name} is outside the finite float range") from exc


def _empirical_mean(regrets: Sequence[float]) -> float:
    return float(sum((Fraction(value) for value in regrets), Fraction()) / len(regrets))


_DECISION_GRADIENT_CERTIFICATE_SCHEMA = "DGC_DECISION_GRADIENT_CERTIFICATE_V1"


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate certificate JSON key {key!r}")
        result[key] = value
    return result


def _reject_nonfinite_json(token: str) -> None:
    raise ValueError(f"non-finite certificate JSON number {token}")


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
    """Structurally validated data. Authority requires replay against trusted inputs."""

    baseline_action: str
    perturbations_examined: tuple[str, ...]
    decision_flip_count: int
    expected_regret: float
    worst_case_regret: float
    weighted_regret: float
    effective_weight: float
    regret_by_perturbation: Mapping[str, float]
    decision_digest: str
    digest_version: int = 1

    def __post_init__(self) -> None:
        if self.baseline_action != _action_identifier(self.baseline_action):
            raise ValueError("certificate baseline action must be canonical")
        if type(self.digest_version) is not int or self.digest_version not in (1, 2):
            raise ValueError("unsupported decision digest version")
        if not isinstance(self.perturbations_examined, (list, tuple)):
            raise ValueError("perturbation roster must be a sequence")
        ids = tuple(self.perturbations_examined)
        if not ids or any(not isinstance(key, str) or not key.strip() for key in ids):
            raise ValueError("perturbation roster must contain non-empty identifiers")
        if len(set(ids)) != len(ids):
            raise ValueError("perturbation identifiers must be unique")
        if not isinstance(self.regret_by_perturbation, Mapping):
            raise ValueError("regret map must be an object")
        regrets = {
            key: _certificate_number("perturbation regret", value)
            for key, value in self.regret_by_perturbation.items()
        }
        if set(regrets) != set(ids):
            raise ValueError("regret identifiers must match the perturbation roster")
        if type(self.decision_flip_count) is not int or self.decision_flip_count != sum(
            regret > 0 for regret in regrets.values()
        ):
            raise ValueError("decision flip count must equal the number of positive regrets")
        for name in ("expected_regret", "worst_case_regret", "weighted_regret", "effective_weight"):
            object.__setattr__(self, name, _certificate_number(name, getattr(self, name)))
        ordered_regrets = tuple(regrets[key] for key in ids)
        mean = (
            sum(ordered_regrets) / len(ordered_regrets)
            if self.digest_version == 1 else _empirical_mean(ordered_regrets)
        )
        if self.expected_regret != mean or self.worst_case_regret != max(ordered_regrets):
            raise ValueError("regret aggregates do not match the perturbation regrets")
        if self.effective_weight <= 0:
            raise ValueError("effective weight must be positive")
        if not min(ordered_regrets) <= self.weighted_regret <= self.worst_case_regret:
            raise ValueError("weighted regret must lie within the observed range")
        if (
            not isinstance(self.decision_digest, str)
            or len(self.decision_digest) != 64
            or any(char not in "0123456789abcdef" for char in self.decision_digest)
        ):
            raise ValueError("decision digest must be lowercase SHA-256")
        object.__setattr__(self, "perturbations_examined", ids)
        object.__setattr__(self, "regret_by_perturbation", MappingProxyType(regrets))

    def to_json(self) -> str:
        return json.dumps(
            {
                "schema": _DECISION_GRADIENT_CERTIFICATE_SCHEMA,
                "baseline_action": self.baseline_action,
                "perturbations_examined": self.perturbations_examined,
                "decision_flip_count": self.decision_flip_count,
                "expected_regret": self.expected_regret,
                "worst_case_regret": self.worst_case_regret,
                "weighted_regret": self.weighted_regret,
                "effective_weight": self.effective_weight,
                "regret_by_perturbation": dict(self.regret_by_perturbation),
                "decision_digest": self.decision_digest,
                "digest_version": self.digest_version,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )

    @classmethod
    def from_json(cls, serialized: str) -> DecisionGradientCertificate:
        """Decode the versioned representation and validate its internal consistency."""
        data = json.loads(
            serialized, object_pairs_hook=_unique_json_object, parse_constant=_reject_nonfinite_json
        )
        if not isinstance(data, dict) or data.pop("schema", None) != _DECISION_GRADIENT_CERTIFICATE_SCHEMA:
            raise ValueError("unsupported decision-gradient certificate schema")
        if data.keys() != {item.name for item in fields(cls)}:
            raise ValueError("invalid decision-gradient certificate field roster")
        return cls(**data)


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
    """Compute the historical V1 digest over identifiers and the regret map."""
    return _digest(
        {
            "baseline_action": baseline_action,
            "source_state_digest": source_state_digest,
            "utility_digest": utility_digest,
            "perturbations": [(p.perturbation_id, p.digest) for p in perturbations],
            "regrets": {k: regrets[k] for k in sorted(regrets)},
        }
    )


def _bind_decision_digest_v2(
    *,
    baseline_action: str,
    source_state_digest: str,
    utility_digest: str,
    perturbations: Sequence[Perturbation],
    utilities: Mapping[str, Mapping[str, float]],
) -> str:
    return _digest(
        {
            "schema": "DGC_DECISION_GRADIENT_DIGEST_V2",
            "baseline_action": baseline_action,
            "source_state_digest": source_state_digest,
            "utility_digest": utility_digest,
            "perturbations": [
                (p.perturbation_id, p.digest, dict(utilities[p.perturbation_id])) for p in perturbations
            ],
        }
    )
