from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence

from cwc.governance.contracts import Perturbation


class InterventionType(str, Enum):
    PARAMETER_SHIFT = "PARAMETER_SHIFT"
    MISSING_EVIDENCE = "MISSING_EVIDENCE"
    ASSUMPTION_REMOVAL = "ASSUMPTION_REMOVAL"
    COUNTERMODEL = "COUNTERMODEL"
    SENSOR_ERROR = "SENSOR_ERROR"
    DELAY = "DELAY"
    CORRELATED_FAILURE = "CORRELATED_FAILURE"
    CAUSAL_INTERVENTION = "CAUSAL_INTERVENTION"
    MODEL_MISSPECIFICATION = "MODEL_MISSPECIFICATION"


@dataclass(frozen=True, slots=True)
class PerturbationTemplate:
    target_variable: str
    candidate_values: tuple[str, ...]
    intervention_type: InterventionType
    provenance: str
    plausibility_weight: float
    causal_dependencies: tuple[str, ...] = ()
    estimated_cost: float = 0.0
    structural_model_digest: str | None = None

    def __post_init__(self) -> None:
        target = self.target_variable.strip()
        provenance = self.provenance.strip()
        values = tuple(dict.fromkeys(str(v) for v in self.candidate_values))
        if not target or not provenance or not values:
            raise ValueError("target_variable, provenance and candidate_values are required")
        if not math.isfinite(self.plausibility_weight) or self.plausibility_weight < 0:
            raise ValueError("plausibility_weight must be finite and >= 0")
        if not math.isfinite(self.estimated_cost) or self.estimated_cost < 0:
            raise ValueError("estimated_cost must be finite and >= 0")
        deps = tuple(sorted({x.strip() for x in self.causal_dependencies if x.strip()}))
        structural = self.structural_model_digest.strip() if self.structural_model_digest else None
        if self.intervention_type is InterventionType.CAUSAL_INTERVENTION and (not structural or not deps):
            raise ValueError("causal intervention requires structural_model_digest and causal_dependencies")
        object.__setattr__(self, "target_variable", target)
        object.__setattr__(self, "provenance", provenance)
        object.__setattr__(self, "candidate_values", values)
        object.__setattr__(self, "causal_dependencies", deps)
        object.__setattr__(self, "structural_model_digest", structural)


@dataclass(frozen=True, slots=True)
class PerturbationBatch:
    perturbations: tuple[Perturbation, ...]
    raw_candidates: int
    dropped_same_value: int
    dropped_by_budget: int
    compiler_digest: str


def _pid(payload: Mapping[str, object]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return "DGC-P-" + hashlib.sha256(raw).hexdigest()[:20]


def compile_local_perturbations(
    baseline_state: Mapping[str, str],
    templates: Sequence[PerturbationTemplate],
    *,
    max_raw: int = 32,
) -> PerturbationBatch:
    """Compile a deterministic provenance-bound perturbation set without an LLM."""
    if max_raw <= 0:
        raise ValueError("max_raw must be positive")
    canonical_state = {str(k): str(v) for k, v in baseline_state.items()}
    candidates: list[tuple[tuple[str, str, str], Perturbation]] = []
    dropped_same = 0
    raw_candidates = 0

    for template in templates:
        if template.target_variable not in canonical_state:
            raise KeyError(f"unknown target variable: {template.target_variable}")
        baseline = canonical_state[template.target_variable]
        for value in template.candidate_values:
            raw_candidates += 1
            if value == baseline:
                dropped_same += 1
                continue
            payload = {
                "target_variable": template.target_variable,
                "baseline_value": baseline,
                "perturbed_value": value,
                "intervention_type": template.intervention_type.value,
                "provenance": template.provenance,
                "plausibility_weight": template.plausibility_weight,
                "causal_dependencies": template.causal_dependencies,
                "estimated_cost": template.estimated_cost,
                "structural_model_digest": template.structural_model_digest,
            }
            perturbation = Perturbation(
                perturbation_id=_pid(payload),
                target_variable=template.target_variable,
                baseline_value=baseline,
                perturbed_value=value,
                intervention_type=template.intervention_type.value,
                provenance=template.provenance,
                plausibility_weight=template.plausibility_weight,
                causal_dependencies=template.causal_dependencies,
                estimated_cost=template.estimated_cost,
                structural_model_digest=template.structural_model_digest,
            )
            order = (template.target_variable, template.intervention_type.value, value)
            candidates.append((order, perturbation))

    candidates.sort(key=lambda item: item[0])
    kept = tuple(item[1] for item in candidates[:max_raw])
    dropped_by_budget = max(0, len(candidates) - len(kept))
    compiler_payload = {
        "baseline_state": canonical_state,
        "perturbation_digests": [p.digest for p in kept],
        "raw_candidates": raw_candidates,
        "dropped_same_value": dropped_same,
        "dropped_by_budget": dropped_by_budget,
        "max_raw": max_raw,
    }
    compiler_digest = hashlib.sha256(
        json.dumps(compiler_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return PerturbationBatch(
        perturbations=kept,
        raw_candidates=raw_candidates,
        dropped_same_value=dropped_same,
        dropped_by_budget=dropped_by_budget,
        compiler_digest=compiler_digest,
    )
