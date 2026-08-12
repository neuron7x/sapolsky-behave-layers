from __future__ import annotations

import itertools
import math
import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

Coalition = frozenset[str]
CoalitionEvaluator = Callable[[Coalition], float]


@dataclass(frozen=True, slots=True)
class AblationShapleyEstimate:
    credits: dict[str, float]
    estimator_variance: dict[str, float]
    logical_evaluations: int
    unique_forward_evaluations: int
    sampling_units: int
    method: str

    @property
    def variance_estimable(self) -> bool:
        return self.method == "EXACT_ABLATION_SHAPLEY" or self.sampling_units >= 2


def _variance_of_mean(values: Sequence[float]) -> float:
    n = len(values)
    if n <= 1:
        return 0.0
    mean = sum(values) / n
    sample_var = sum((x - mean) ** 2 for x in values) / (n - 1)
    return sample_var / n


class CachedCoalitionEvaluator:
    """Cache coalition evaluations while preserving an explicit physical-forward count."""

    def __init__(self, evaluator: CoalitionEvaluator):
        self._evaluator = evaluator
        self._cache: dict[Coalition, float] = {}
        self.logical_calls = 0
        self.unique_calls = 0

    def __call__(self, coalition: Coalition) -> float:
        key = frozenset(coalition)
        self.logical_calls += 1
        if key not in self._cache:
            self._cache[key] = float(self._evaluator(key))
            self.unique_calls += 1
        return self._cache[key]


def exact_ablation_shapley(players: Sequence[str], evaluator: CoalitionEvaluator) -> AblationShapleyEstimate:
    names = tuple(players)
    if not names:
        raise ValueError("players required")
    n = len(names)
    cached = CachedCoalitionEvaluator(evaluator)
    values: dict[Coalition, float] = {}
    for r in range(n + 1):
        for subset in itertools.combinations(names, r):
            key = frozenset(subset)
            values[key] = cached(key)

    denom = math.factorial(n)
    credits: dict[str, float] = {}
    for player in names:
        acc = 0.0
        others = tuple(p for p in names if p != player)
        for r in range(len(others) + 1):
            weight = math.factorial(r) * math.factorial(n - r - 1) / denom
            for subset in itertools.combinations(others, r):
                s = frozenset(subset)
                acc += weight * (values[s | {player}] - values[s])
        credits[player] = float(acc)
    return AblationShapleyEstimate(
        credits=credits,
        estimator_variance=dict.fromkeys(names, 0.0),
        logical_evaluations=cached.logical_calls,
        unique_forward_evaluations=cached.unique_calls,
        sampling_units=0,
        method="EXACT_ABLATION_SHAPLEY",
    )


def _path_contrib(order: Sequence[str], evaluator: CachedCoalitionEvaluator) -> dict[str, float]:
    coalition: set[str] = set()
    previous = evaluator(frozenset())
    out: dict[str, float] = {}
    for player in order:
        coalition.add(player)
        current = evaluator(frozenset(coalition))
        out[player] = float(current - previous)
        previous = current
    return out


def antithetic_permutation_ablation_shapley(
    players: Sequence[str],
    evaluator: CoalitionEvaluator,
    *,
    pairs: int,
    rng: random.Random,
) -> AblationShapleyEstimate:
    names = tuple(players)
    if not names:
        raise ValueError("players required")
    if pairs < 1:
        raise ValueError("pairs must be >=1")
    cached = CachedCoalitionEvaluator(evaluator)
    samples = {p: [] for p in names}
    base_order = list(names)
    for _ in range(pairs):
        rng.shuffle(base_order)
        order = tuple(base_order)
        reverse = tuple(reversed(order))
        forward = _path_contrib(order, cached)
        backward = _path_contrib(reverse, cached)
        for player in names:
            samples[player].append(0.5 * (forward[player] + backward[player]))
    credits = {p: float(sum(v) / len(v)) for p, v in samples.items()}
    return AblationShapleyEstimate(
        credits=credits,
        estimator_variance={p: _variance_of_mean(v) for p, v in samples.items()},
        logical_evaluations=cached.logical_calls,
        unique_forward_evaluations=cached.unique_calls,
        sampling_units=pairs,
        method="ANTITHETIC_PERMUTATION_ABLATION_SHAPLEY",
    )


def ranked_by_absolute_credit(credits: Mapping[str, float]) -> list[str]:
    return sorted(credits, key=lambda p: (-abs(float(credits[p])), p))
