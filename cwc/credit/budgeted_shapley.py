from __future__ import annotations

import itertools
import math
import random
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass

Assignment = Mapping[str, int]
Evaluator = Callable[[Mapping[str, int]], float]


@dataclass(frozen=True, slots=True)
class ShapleyEstimate:
    credits: dict[str, float]
    estimator_variance: dict[str, float]
    structural_evaluations: int
    sampling_units: int
    method: str

    @property
    def variance_estimable(self) -> bool:
        """Whether sampling variance is statistically estimable from >=2 units.

        Exact teachers are deterministic. Monte-Carlo estimates with one sampling
        unit retain the historical numeric 0.0 sentinel for compatibility, but that
        sentinel is not authority-bearing variance evidence.
        """
        return self.method == "EXACT_TEACHER" or self.sampling_units >= 2


def _sample_binary(rng: random.Random) -> int:
    return -1 if rng.random() < 0.5 else 1


def _variance_of_mean(values: Sequence[float]) -> float:
    n = len(values)
    if n <= 1:
        return 0.0
    mean = sum(values) / n
    sample_var = sum((x - mean) ** 2 for x in values) / (n - 1)
    return sample_var / n


def _finish(samples: dict[str, list[float]], evaluations: int, method: str) -> ShapleyEstimate:
    credits = {name: (sum(vals) / len(vals) if vals else 0.0) for name, vals in samples.items()}
    variances = {name: _variance_of_mean(vals) for name, vals in samples.items()}
    units = min((len(vals) for vals in samples.values()), default=0)
    return ShapleyEstimate(credits, variances, evaluations, units, method)


def exact_resampling_shapley(
    factual: Mapping[str, int],
    players: Sequence[str],
    evaluator: Evaluator,
) -> ShapleyEstimate:
    """Exact Shapley value for a symmetric {-1,+1} intervention baseline."""
    names = tuple(players)
    n = len(names)
    factual_value = float(evaluator(factual))
    evaluations = 1
    values: dict[frozenset[str], float] = {frozenset(): 0.0}
    for r in range(1, n + 1):
        for subset in itertools.combinations(names, r):
            key = frozenset(subset)
            total = 0.0
            count = 0
            ordered = tuple(sorted(key))
            for draws in itertools.product((-1, 1), repeat=len(ordered)):
                assignment = dict(factual)
                assignment.update(dict(zip(ordered, draws, strict=True)))
                total += float(evaluator(assignment))
                evaluations += 1
                count += 1
            values[key] = factual_value - total / count

    credits: dict[str, float] = {}
    denom = math.factorial(n)
    for player in names:
        acc = 0.0
        others = tuple(p for p in names if p != player)
        for r in range(len(others) + 1):
            weight = math.factorial(r) * math.factorial(n - r - 1) / denom
            for subset in itertools.combinations(others, r):
                s = frozenset(subset)
                acc += weight * (values[s | {player}] - values[s])
        credits[player] = acc
    return ShapleyEstimate(credits, dict.fromkeys(names, 0.0), evaluations, 0, "EXACT_TEACHER")


def legacy_independent_mc(
    factual: Mapping[str, int],
    players: Sequence[str],
    evaluator: Evaluator,
    *,
    permutations: int,
    rng: random.Random,
) -> ShapleyEstimate:
    """Historical approximation: predecessor values are re-randomized at each step."""
    names = tuple(players)
    if permutations < 1:
        raise ValueError("permutations must be >=1")
    samples = {p: [] for p in names}
    factual_value = float(evaluator(factual))
    evaluations = 1
    order = list(names)
    for _ in range(permutations):
        rng.shuffle(order)
        previous_output = factual_value
        coalition: set[str] = set()
        for player in order:
            coalition.add(player)
            assignment = dict(factual)
            for member in sorted(coalition):
                assignment[member] = _sample_binary(rng)
            current_output = float(evaluator(assignment))
            evaluations += 1
            samples[player].append(previous_output - current_output)
            previous_output = current_output
    return _finish(samples, evaluations, "LEGACY_INDEPENDENT_MC")


def crn_chain_mc(
    factual: Mapping[str, int],
    players: Sequence[str],
    evaluator: Evaluator,
    *,
    permutations: int,
    rng: random.Random,
) -> ShapleyEstimate:
    """Permutation Shapley with common random numbers on nested coalitions."""
    names = tuple(players)
    if permutations < 1:
        raise ValueError("permutations must be >=1")
    samples = {p: [] for p in names}
    factual_value = float(evaluator(factual))
    evaluations = 1
    order = list(names)
    for _ in range(permutations):
        rng.shuffle(order)
        assignment = dict(factual)
        previous_output = factual_value
        for player in order:
            assignment[player] = _sample_binary(rng)
            current_output = float(evaluator(assignment))
            evaluations += 1
            samples[player].append(previous_output - current_output)
            previous_output = current_output
    return _finish(samples, evaluations, "CRN_CHAIN_MC")


def _path_contributions(
    factual: Mapping[str, int],
    order: Sequence[str],
    replacements: Mapping[str, int],
    evaluator: Evaluator,
    factual_value: float,
) -> tuple[dict[str, float], int]:
    assignment = dict(factual)
    previous_output = factual_value
    contributions: dict[str, float] = {}
    evaluations = 0
    for player in order:
        assignment[player] = int(replacements[player])
        current_output = float(evaluator(assignment))
        evaluations += 1
        contributions[player] = previous_output - current_output
        previous_output = current_output
    return contributions, evaluations


def antithetic_crn_mc(
    factual: Mapping[str, int],
    players: Sequence[str],
    evaluator: Evaluator,
    *,
    pairs: int,
    rng: random.Random,
) -> ShapleyEstimate:
    """CRN permutation estimator with complementary intervention assignments."""
    names = tuple(players)
    if pairs < 1:
        raise ValueError("pairs must be >=1")
    samples = {p: [] for p in names}
    factual_value = float(evaluator(factual))
    evaluations = 1
    order = list(names)
    for _ in range(pairs):
        rng.shuffle(order)
        replacements = {p: _sample_binary(rng) for p in names}
        complement = {p: -v for p, v in replacements.items()}
        first, used = _path_contributions(factual, order, replacements, evaluator, factual_value)
        second, used2 = _path_contributions(factual, order, complement, evaluator, factual_value)
        evaluations += used + used2
        for p in names:
            samples[p].append(0.5 * (first[p] + second[p]))
    return _finish(samples, evaluations, "ANTITHETIC_CRN_MC")


def double_antithetic_crn_mc(
    factual: Mapping[str, int],
    players: Sequence[str],
    evaluator: Evaluator,
    *,
    quartets: int,
    rng: random.Random,
) -> ShapleyEstimate:
    """Exploratory assignment-complement + reverse-permutation antithetic estimator."""
    names = tuple(players)
    if quartets < 1:
        raise ValueError("quartets must be >=1")
    samples = {p: [] for p in names}
    factual_value = float(evaluator(factual))
    evaluations = 1
    order = list(names)
    for _ in range(quartets):
        rng.shuffle(order)
        reverse = list(reversed(order))
        replacements = {p: _sample_binary(rng) for p in names}
        complement = {p: -v for p, v in replacements.items()}
        configs = (
            (order, replacements),
            (order, complement),
            (reverse, replacements),
            (reverse, complement),
        )
        acc = dict.fromkeys(names, 0.0)
        for candidate_order, candidate_replacements in configs:
            contrib, used = _path_contributions(
                factual, candidate_order, candidate_replacements, evaluator, factual_value
            )
            evaluations += used
            for p in names:
                acc[p] += contrib[p] / 4.0
        for p in names:
            samples[p].append(acc[p])
    return _finish(samples, evaluations, "DOUBLE_ANTITHETIC_CRN_MC")
