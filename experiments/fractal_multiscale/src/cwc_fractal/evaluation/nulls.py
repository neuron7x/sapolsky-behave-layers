from __future__ import annotations

import random
import statistics
from dataclasses import dataclass
from typing import Any

from cwc_fractal.analyzer import FractalMultiscaleAnalyzer
from cwc_fractal.types import CausalWindow, FeatureMapping, ScaleObservation


@dataclass(frozen=True)
class NullEvaluation:
    observed_mean_coherence: float
    null_mean_coherence: float
    delta: float
    empirical_p_value: float
    bootstrap_ci95: tuple[float, float]
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "observed_mean_coherence": self.observed_mean_coherence,
            "null_mean_coherence": self.null_mean_coherence,
            "delta": self.delta,
            "empirical_p_value": self.empirical_p_value,
            "bootstrap_ci95": list(self.bootstrap_ci95),
            "passed": self.passed,
        }


def evaluate_against_nulls(
    window: CausalWindow,
    *,
    mappings: tuple[FeatureMapping, ...],
    iterations: int = 200,
    seed: int = 17,
    min_delta: float = 0.05,
    max_p_value: float = 0.05,
) -> NullEvaluation:
    if iterations < 10:
        raise ValueError("iterations must be >= 10")
    rng = random.Random(seed)
    observed = _mean_coherence(window, mappings)
    null_values = [
        _mean_coherence(_shuffled_window(window, rng), mappings) for _ in range(iterations)
    ]
    null_mean = statistics.fmean(null_values)
    delta = observed - null_mean
    p_value = (1 + sum(value >= observed for value in null_values)) / (iterations + 1)
    ci = _bootstrap_ci(null_values, rng)
    return NullEvaluation(
        observed_mean_coherence=observed,
        null_mean_coherence=null_mean,
        delta=delta,
        empirical_p_value=p_value,
        bootstrap_ci95=ci,
        passed=delta >= min_delta and p_value <= max_p_value,
    )


def _mean_coherence(window: CausalWindow, mappings: tuple[FeatureMapping, ...]) -> float:
    report = FractalMultiscaleAnalyzer(mappings=mappings).analyze(window)
    values = [abs(item.coherence) for item in report.cross_scale_reports]
    return statistics.fmean(values) if values else 0.0


def _shuffled_window(window: CausalWindow, rng: random.Random) -> CausalWindow:
    by_scale: dict[str, list[ScaleObservation]] = {}
    for observation in window.observations:
        by_scale.setdefault(observation.scale.value, []).append(observation)
    shuffled: list[ScaleObservation] = []
    for scale_items in by_scale.values():
        feature_names = sorted({name for item in scale_items for name in item.features})
        shuffled_values: dict[str, list[float]] = {}
        for feature_name in feature_names:
            values = [item.features.get(feature_name, 0.0) for item in scale_items]
            rng.shuffle(values)
            shuffled_values[feature_name] = values
        for index, item in enumerate(scale_items):
            shuffled.append(
                ScaleObservation(
                    timestamp=item.timestamp,
                    scale=item.scale,
                    source=f"{item.source}:time_shuffle_null",
                    features={
                        feature_name: shuffled_values[feature_name][index]
                        for feature_name in feature_names
                    },
                    metadata=item.metadata,
                )
            )
    return CausalWindow(end_timestamp=window.end_timestamp, observations=tuple(shuffled))


def _bootstrap_ci(values: list[float], rng: random.Random) -> tuple[float, float]:
    if not values:
        return (0.0, 0.0)
    means: list[float] = []
    for _ in range(200):
        sample = [values[rng.randrange(len(values))] for _ in values]
        means.append(statistics.fmean(sample))
    means.sort()
    lower = means[int(0.025 * (len(means) - 1))]
    upper = means[int(0.975 * (len(means) - 1))]
    return lower, upper
