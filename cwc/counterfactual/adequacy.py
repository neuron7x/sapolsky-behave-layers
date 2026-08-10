from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np

from .model import CANDIDATES, FittedCounterfactualModel


@dataclass(frozen=True, slots=True)
class InterventionProbe:
    candidate: str
    base: Mapping[str, float]
    observed_half_effect: float


@dataclass(frozen=True, slots=True)
class InterventionSupport:
    probes: tuple[InterventionProbe, ...]

    def counts(self) -> dict[str, int]:
        return {name: sum(1 for probe in self.probes if probe.candidate == name) for name in CANDIDATES}

    def observed_effect_magnitudes(self) -> dict[str, float]:
        return {
            name: float(np.mean([abs(p.observed_half_effect) for p in self.probes if p.candidate == name]))
            for name in CANDIDATES
        }


@dataclass(frozen=True, slots=True)
class AdequacyMetrics:
    per_model_nrmse: tuple[float, ...]
    median_nrmse: float
    max_nrmse: float
    support_counts: dict[str, int]
    observed_effect_magnitudes: dict[str, float]


def evaluate_intervention_adequacy(
    models: Sequence[FittedCounterfactualModel],
    support: InterventionSupport,
) -> AdequacyMetrics:
    if not models:
        raise ValueError("counterfactual model ensemble is empty")
    if not support.probes:
        return AdequacyMetrics((), float("inf"), float("inf"), {n: 0 for n in CANDIDATES}, {n: 0.0 for n in CANDIDATES})
    observed = np.asarray([p.observed_half_effect for p in support.probes], dtype=float)
    scale = max(float(np.sqrt(np.mean(observed**2))), 0.25)
    errors: list[float] = []
    for model in models:
        predicted = np.asarray([model.intervention_effect(p.base, p.candidate) for p in support.probes], dtype=float)
        rmse = float(np.sqrt(np.mean((predicted - observed) ** 2)))
        errors.append(rmse / scale)
    return AdequacyMetrics(
        per_model_nrmse=tuple(errors),
        median_nrmse=float(np.median(errors)),
        max_nrmse=max(errors),
        support_counts=support.counts(),
        observed_effect_magnitudes=support.observed_effect_magnitudes(),
    )
