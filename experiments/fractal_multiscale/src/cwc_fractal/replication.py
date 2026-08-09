from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass
from typing import Any, Sequence

from .robust import (
    _block_permutation,
    _circular_shift,
    _mean_abs_spearman,
    _valid_residual_pairs,
    _within_stratum_shuffle,
    robust_coherence_report,
)
from .types import CausalWindow, FeatureMapping


@dataclass(frozen=True, slots=True)
class ProgrammeNullResult:
    observed: float
    max_null_mean: float
    delta_vs_max_null_mean: float
    familywise_p_value: float
    family_means: dict[str, float]
    family_p_values: dict[str, float]
    iterations: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "observed": self.observed,
            "max_null_mean": self.max_null_mean,
            "delta_vs_max_null_mean": self.delta_vs_max_null_mean,
            "familywise_p_value": self.familywise_p_value,
            "family_means": dict(self.family_means),
            "family_p_values": dict(self.family_p_values),
            "iterations": self.iterations,
        }


def _transform_target(
    name: str,
    target: Sequence[float],
    strata: Sequence[tuple[str, ...]],
    rng: random.Random,
) -> tuple[float, ...]:
    if name == "within_stratum_shuffle_target":
        return _within_stratum_shuffle(target, strata, rng)
    if name == "circular_shift_target":
        return _circular_shift(target, rng)
    if name == "block_permutation_target":
        return _block_permutation(target, rng)
    raise ValueError(f"unsupported null family: {name}")


def evaluate_programme_nulls(
    windows: Sequence[CausalWindow],
    *,
    mappings: Sequence[FeatureMapping],
    confounder_strata: Sequence[str],
    null_models: Sequence[str],
    iterations: int,
    seed: int,
) -> ProgrammeNullResult:
    """Exploratory pooled null diagnostic across already-observed replicate seeds.

    Null transformations are independent across seeds and pairs. The result is diagnostic-only and
    MUST NOT be used to upgrade already-inspected data to confirmatory evidence.
    """
    if len(windows) < 2:
        raise ValueError("programme synthesis requires at least two replicate windows")
    if iterations < 500:
        raise ValueError("programme synthesis requires >=500 null iterations")
    per_seed_pairs = [
        _valid_residual_pairs(window, mappings=mappings, confounder_strata=confounder_strata)
        for window in windows
    ]
    if any(not pairs for pairs in per_seed_pairs):
        raise ValueError("every replicate must contain at least one valid residual pair")
    observed_seed = []
    for window in windows:
        report = robust_coherence_report(
            window, mappings=mappings, confounder_strata=confounder_strata
        )
        if report.residual_mean_abs_coherence is None:
            raise ValueError("replicate has no residual coherence statistic")
        observed_seed.append(float(report.residual_mean_abs_coherence))
    observed = statistics.fmean(observed_seed)

    rng = random.Random(seed)
    per_family: dict[str, list[float]] = {name: [] for name in null_models}
    maxima: list[float] = []
    for _ in range(iterations):
        family_values: list[float] = []
        for name in null_models:
            seed_stats: list[float] = []
            for pairs in per_seed_pairs:
                transformed = []
                for src, target, strata in pairs:
                    transformed.append((src, _transform_target(name, target, strata, rng)))
                seed_stats.append(_mean_abs_spearman(transformed))
            value = statistics.fmean(seed_stats)
            per_family[name].append(value)
            family_values.append(value)
        maxima.append(max(family_values))

    family_means = {name: statistics.fmean(values) for name, values in per_family.items()}
    family_p = {
        name: (1 + sum(value >= observed for value in values)) / (len(values) + 1)
        for name, values in per_family.items()
    }
    max_mean = statistics.fmean(maxima)
    familywise_p = (1 + sum(value >= observed for value in maxima)) / (len(maxima) + 1)
    return ProgrammeNullResult(
        observed=observed,
        max_null_mean=max_mean,
        delta_vs_max_null_mean=observed - max_mean,
        familywise_p_value=familywise_p,
        family_means=family_means,
        family_p_values=family_p,
        iterations=iterations,
    )


def fisher_z(r: float) -> float:
    if not math.isfinite(r):
        raise ValueError("r must be finite")
    clipped = min(1.0 - 1e-12, max(-1.0 + 1e-12, r))
    return math.atanh(clipped)


def cross_seed_pair_diagnostics(pair_reports_by_seed: dict[str, Sequence[dict[str, Any]]]) -> list[dict[str, Any]]:
    keys: set[tuple[str, str, str]] = set()
    indexed: dict[str, dict[tuple[str, str, str], dict[str, Any]]] = {}
    for seed, reports in pair_reports_by_seed.items():
        idx = {}
        for report in reports:
            key = (str(report["edge"]), str(report["source_feature"]), str(report["target_feature"]))
            idx[key] = report
            keys.add(key)
        indexed[seed] = idx

    output: list[dict[str, Any]] = []
    for key in sorted(keys):
        values: list[float] = []
        ns: list[int] = []
        by_seed: dict[str, float | None] = {}
        for seed in sorted(indexed):
            report = indexed[seed].get(key)
            r = None if report is None else report.get("residual_spearman")
            by_seed[seed] = None if r is None else float(r)
            if r is not None:
                values.append(float(r))
                ns.append(int(report.get("n", 0)))
        if not values:
            output.append({
                "edge": key[0], "source_feature": key[1], "target_feature": key[2],
                "by_seed": by_seed, "valid_seed_count": 0,
            })
            continue
        positive = sum(v > 0 for v in values)
        negative = sum(v < 0 for v in values)
        # Fisher-z mean is descriptive: seeds share the same experiment family and are not assumed
        # to be iid population samples.
        weights = [max(n - 3, 1) for n in ns]
        zbar = sum(w * fisher_z(v) for w, v in zip(weights, values, strict=True)) / sum(weights)
        output.append({
            "edge": key[0],
            "source_feature": key[1],
            "target_feature": key[2],
            "by_seed": by_seed,
            "valid_seed_count": len(values),
            "sign_consistency_fraction": max(positive, negative) / len(values),
            "descriptive_fisher_z_mean_r": math.tanh(zbar),
            "range": [min(values), max(values)],
        })
    return output
