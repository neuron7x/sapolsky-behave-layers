from __future__ import annotations

import math
import random
import statistics
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

from .types import CausalWindow, FeatureMapping, FractalValidationError, Scale, ScaleObservation


_EPS = 1e-12


def _finite(values: Iterable[float]) -> list[float]:
    output = [float(value) for value in values]
    if not output:
        raise FractalValidationError("trajectory cannot be empty")
    if any(not math.isfinite(value) for value in output):
        raise FractalValidationError("trajectory contains non-finite value")
    return output


def _average_ranks(values: Sequence[float]) -> list[float]:
    """Average ranks with deterministic tie handling; ranks start at 1."""
    indexed = sorted(enumerate(float(v) for v in values), key=lambda item: (item[1], item[0]))
    ranks = [0.0] * len(indexed)
    i = 0
    while i < len(indexed):
        j = i + 1
        value = indexed[i][1]
        while j < len(indexed) and indexed[j][1] == value:
            j += 1
        average = ((i + 1) + j) / 2.0
        for k in range(i, j):
            ranks[indexed[k][0]] = average
        i = j
    return ranks


def pearson(left: Sequence[float], right: Sequence[float]) -> float:
    x = _finite(left)
    y = _finite(right)
    if len(x) != len(y) or len(x) < 3:
        raise FractalValidationError("association requires equal trajectories of length >= 3")
    mx = statistics.fmean(x)
    my = statistics.fmean(y)
    dx = [v - mx for v in x]
    dy = [v - my for v in y]
    vx = sum(v * v for v in dx)
    vy = sum(v * v for v in dy)
    if vx <= _EPS or vy <= _EPS:
        raise FractalValidationError("association undefined for degenerate trajectory")
    return sum(a * b for a, b in zip(dx, dy, strict=True)) / math.sqrt(vx * vy)


def spearman(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise FractalValidationError("association requires equal trajectory length")
    return pearson(_average_ranks(left), _average_ranks(right))


def normalized_entropy(probabilities: Sequence[float]) -> float:
    values = [max(float(value), 0.0) for value in probabilities]
    total = sum(values)
    if total <= 0.0 or len(values) <= 1:
        return 0.0
    probs = [value / total for value in values]
    entropy = -sum(p * math.log(p) for p in probs if p > 0.0)
    return entropy / math.log(len(probs))


@dataclass(frozen=True, slots=True)
class PairTrajectory:
    source_scale: Scale
    target_scale: Scale
    source_feature: str
    target_feature: str
    timestamps: tuple[int, ...]
    source_values: tuple[float, ...]
    target_values: tuple[float, ...]
    strata: tuple[tuple[str, ...], ...]

    @property
    def edge(self) -> str:
        return f"{self.source_scale.value}->{self.target_scale.value}"


@dataclass(frozen=True, slots=True)
class PairAssociation:
    edge: str
    source_feature: str
    target_feature: str
    n: int
    raw_spearman: float | None
    residual_spearman: float | None
    status: str
    repeated_strata_fraction: float
    source_residual_std: float | None
    target_residual_std: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge": self.edge,
            "source_feature": self.source_feature,
            "target_feature": self.target_feature,
            "n": self.n,
            "raw_spearman": self.raw_spearman,
            "residual_spearman": self.residual_spearman,
            "status": self.status,
            "repeated_strata_fraction": self.repeated_strata_fraction,
            "source_residual_std": self.source_residual_std,
            "target_residual_std": self.target_residual_std,
        }


@dataclass(frozen=True, slots=True)
class RobustCoherenceReport:
    pair_reports: tuple[PairAssociation, ...]
    valid_pair_fraction: float
    raw_mean_abs_coherence: float | None
    residual_mean_abs_coherence: float | None
    required_edges: tuple[str, ...]
    valid_edges: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "pair_reports": [item.to_dict() for item in self.pair_reports],
            "valid_pair_fraction": self.valid_pair_fraction,
            "raw_mean_abs_coherence": self.raw_mean_abs_coherence,
            "residual_mean_abs_coherence": self.residual_mean_abs_coherence,
            "required_edges": list(self.required_edges),
            "valid_edges": list(self.valid_edges),
        }


def _index_window(window: CausalWindow) -> dict[tuple[int, Scale], ScaleObservation]:
    indexed: dict[tuple[int, Scale], ScaleObservation] = {}
    for observation in window.observations:
        key = (observation.timestamp, observation.scale)
        if key in indexed:
            raise FractalValidationError(
                f"duplicate observation at timestamp={observation.timestamp} scale={observation.scale.value}"
            )
        indexed[key] = observation
    return indexed


def _stratum_from_observations(
    source: ScaleObservation,
    target: ScaleObservation,
    names: Sequence[str],
) -> tuple[str, ...]:
    values: list[str] = []
    for name in names:
        s_value = source.metadata.get(name)
        t_value = target.metadata.get(name)
        if s_value is None or t_value is None:
            raise FractalValidationError(f"missing confounder metadata: {name}")
        if s_value != t_value:
            raise FractalValidationError(
                f"confounder mismatch at timestamp={source.timestamp}: {name} {s_value!r}!={t_value!r}"
            )
        values.append(str(s_value))
    return tuple(values)


def aligned_pair_trajectory(
    window: CausalWindow,
    mapping: FeatureMapping,
    pair: tuple[str, str],
    *,
    confounder_strata: Sequence[str],
) -> PairTrajectory:
    indexed = _index_window(window)
    timestamps = sorted(
        timestamp
        for timestamp, scale in indexed
        if scale == mapping.source_scale and (timestamp, mapping.target_scale) in indexed
    )
    source_values: list[float] = []
    target_values: list[float] = []
    strata: list[tuple[str, ...]] = []
    source_name, target_name = pair
    kept_timestamps: list[int] = []
    for timestamp in timestamps:
        source = indexed[(timestamp, mapping.source_scale)]
        target = indexed[(timestamp, mapping.target_scale)]
        if source_name not in source.features or target_name not in target.features:
            continue
        source_values.append(float(source.features[source_name]))
        target_values.append(float(target.features[target_name]))
        strata.append(_stratum_from_observations(source, target, confounder_strata))
        kept_timestamps.append(timestamp)
    if len(kept_timestamps) < 3:
        raise FractalValidationError(
            f"insufficient aligned observations for {mapping.source_scale.value}->{mapping.target_scale.value} "
            f"{source_name}->{target_name}"
        )
    return PairTrajectory(
        source_scale=mapping.source_scale,
        target_scale=mapping.target_scale,
        source_feature=source_name,
        target_feature=target_name,
        timestamps=tuple(kept_timestamps),
        source_values=tuple(source_values),
        target_values=tuple(target_values),
        strata=tuple(strata),
    )


def _std(values: Sequence[float]) -> float:
    return statistics.pstdev(float(value) for value in values)


def residualize_within_strata(
    values: Sequence[float],
    strata: Sequence[tuple[str, ...]],
) -> tuple[tuple[float, ...], float]:
    if len(values) != len(strata):
        raise FractalValidationError("values/strata length mismatch")
    grouped: dict[tuple[str, ...], list[int]] = defaultdict(list)
    for index, key in enumerate(strata):
        grouped[key].append(index)
    repeated = {key: idxs for key, idxs in grouped.items() if len(idxs) >= 2}
    repeated_count = sum(len(idxs) for idxs in repeated.values())
    fraction = repeated_count / len(values) if values else 0.0
    if repeated_count < 3:
        raise FractalValidationError("insufficient repeated confounder strata for exact residualization")
    residuals = [math.nan] * len(values)
    for idxs in repeated.values():
        mean = statistics.fmean(float(values[i]) for i in idxs)
        for index in idxs:
            residuals[index] = float(values[index]) - mean
    # Drop singleton strata identically in source and target by using NaN markers.
    output = tuple(value for value in residuals if math.isfinite(value))
    return output, fraction


def _paired_residuals(trajectory: PairTrajectory) -> tuple[tuple[float, ...], tuple[float, ...], float]:
    grouped: dict[tuple[str, ...], list[int]] = defaultdict(list)
    for index, key in enumerate(trajectory.strata):
        grouped[key].append(index)
    repeated = {key: idxs for key, idxs in grouped.items() if len(idxs) >= 2}
    keep = sorted(index for idxs in repeated.values() for index in idxs)
    fraction = len(keep) / len(trajectory.timestamps)
    if len(keep) < 3:
        raise FractalValidationError("insufficient repeated confounder strata for paired residualization")
    src = [trajectory.source_values[i] for i in keep]
    tgt = [trajectory.target_values[i] for i in keep]
    keys = [trajectory.strata[i] for i in keep]
    src_means: dict[tuple[str, ...], float] = {}
    tgt_means: dict[tuple[str, ...], float] = {}
    for key in set(keys):
        idxs = [i for i, current in enumerate(keys) if current == key]
        src_means[key] = statistics.fmean(src[i] for i in idxs)
        tgt_means[key] = statistics.fmean(tgt[i] for i in idxs)
    src_res = tuple(value - src_means[key] for value, key in zip(src, keys, strict=True))
    tgt_res = tuple(value - tgt_means[key] for value, key in zip(tgt, keys, strict=True))
    return src_res, tgt_res, fraction


def pair_association(trajectory: PairTrajectory) -> PairAssociation:
    raw: float | None
    try:
        raw = spearman(trajectory.source_values, trajectory.target_values)
    except FractalValidationError:
        raw = None
    try:
        src_res, tgt_res, repeated_fraction = _paired_residuals(trajectory)
    except FractalValidationError:
        return PairAssociation(
            edge=trajectory.edge,
            source_feature=trajectory.source_feature,
            target_feature=trajectory.target_feature,
            n=len(trajectory.timestamps),
            raw_spearman=raw,
            residual_spearman=None,
            status="INSUFFICIENT_REPEATED_STRATA",
            repeated_strata_fraction=0.0,
            source_residual_std=None,
            target_residual_std=None,
        )
    src_std = _std(src_res)
    tgt_std = _std(tgt_res)
    if src_std <= _EPS or tgt_std <= _EPS:
        return PairAssociation(
            edge=trajectory.edge,
            source_feature=trajectory.source_feature,
            target_feature=trajectory.target_feature,
            n=len(trajectory.timestamps),
            raw_spearman=raw,
            residual_spearman=None,
            status="COMMON_DRIVER_EXPLAINED_OR_DEGENERATE",
            repeated_strata_fraction=repeated_fraction,
            source_residual_std=src_std,
            target_residual_std=tgt_std,
        )
    residual = spearman(src_res, tgt_res)
    return PairAssociation(
        edge=trajectory.edge,
        source_feature=trajectory.source_feature,
        target_feature=trajectory.target_feature,
        n=len(trajectory.timestamps),
        raw_spearman=raw,
        residual_spearman=residual,
        status="VALID",
        repeated_strata_fraction=repeated_fraction,
        source_residual_std=src_std,
        target_residual_std=tgt_std,
    )


def robust_coherence_report(
    window: CausalWindow,
    *,
    mappings: Sequence[FeatureMapping],
    confounder_strata: Sequence[str],
) -> RobustCoherenceReport:
    reports: list[PairAssociation] = []
    required_edges = tuple(
        sorted({f"{mapping.source_scale.value}->{mapping.target_scale.value}" for mapping in mappings})
    )
    for mapping in mappings:
        for pair in mapping.pairs:
            try:
                trajectory = aligned_pair_trajectory(
                    window,
                    mapping,
                    pair,
                    confounder_strata=confounder_strata,
                )
                reports.append(pair_association(trajectory))
            except FractalValidationError as exc:
                reports.append(
                    PairAssociation(
                        edge=f"{mapping.source_scale.value}->{mapping.target_scale.value}",
                        source_feature=pair[0],
                        target_feature=pair[1],
                        n=0,
                        raw_spearman=None,
                        residual_spearman=None,
                        status=f"INVALID:{exc}",
                        repeated_strata_fraction=0.0,
                        source_residual_std=None,
                        target_residual_std=None,
                    )
                )
    valid = [item for item in reports if item.status == "VALID" and item.residual_spearman is not None]
    raw_values = [abs(item.raw_spearman) for item in reports if item.raw_spearman is not None]
    residual_values = [abs(item.residual_spearman) for item in valid if item.residual_spearman is not None]
    valid_edges = tuple(sorted({item.edge for item in valid}))
    return RobustCoherenceReport(
        pair_reports=tuple(reports),
        valid_pair_fraction=len(valid) / len(reports) if reports else 0.0,
        raw_mean_abs_coherence=statistics.fmean(raw_values) if raw_values else None,
        residual_mean_abs_coherence=statistics.fmean(residual_values) if residual_values else None,
        required_edges=required_edges,
        valid_edges=valid_edges,
    )


@dataclass(frozen=True, slots=True)
class NullFamilyResult:
    name: str
    mean: float
    p_value: float
    q95: float

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "mean": self.mean, "p_value": self.p_value, "q95": self.q95}


@dataclass(frozen=True, slots=True)
class RobustNullEvaluation:
    observed: float | None
    max_null_mean: float | None
    delta_vs_max_null_mean: float | None
    familywise_p_value: float | None
    families: tuple[NullFamilyResult, ...]
    iterations: int
    passed: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "observed": self.observed,
            "max_null_mean": self.max_null_mean,
            "delta_vs_max_null_mean": self.delta_vs_max_null_mean,
            "familywise_p_value": self.familywise_p_value,
            "families": [item.to_dict() for item in self.families],
            "iterations": self.iterations,
            "passed": self.passed,
            "reason": self.reason,
        }


def _valid_residual_pairs(
    window: CausalWindow,
    *,
    mappings: Sequence[FeatureMapping],
    confounder_strata: Sequence[str],
) -> list[tuple[tuple[float, ...], tuple[float, ...], tuple[tuple[str, ...], ...]]]:
    output: list[tuple[tuple[float, ...], tuple[float, ...], tuple[tuple[str, ...], ...]]] = []
    for mapping in mappings:
        for pair in mapping.pairs:
            try:
                trajectory = aligned_pair_trajectory(
                    window, mapping, pair, confounder_strata=confounder_strata
                )
                grouped: dict[tuple[str, ...], list[int]] = defaultdict(list)
                for index, key in enumerate(trajectory.strata):
                    grouped[key].append(index)
                keep = sorted(index for idxs in grouped.values() if len(idxs) >= 2 for index in idxs)
                if len(keep) < 3:
                    continue
                src = [trajectory.source_values[i] for i in keep]
                tgt = [trajectory.target_values[i] for i in keep]
                keys = [trajectory.strata[i] for i in keep]
                src_res: list[float] = []
                tgt_res: list[float] = []
                for key in keys:
                    idxs = [i for i, k in enumerate(keys) if k == key]
                    src_res.append(src[len(src_res)] - statistics.fmean(src[i] for i in idxs))
                    tgt_res.append(tgt[len(tgt_res)] - statistics.fmean(tgt[i] for i in idxs))
                if _std(src_res) <= _EPS or _std(tgt_res) <= _EPS:
                    continue
                output.append((tuple(src_res), tuple(tgt_res), tuple(keys)))
            except FractalValidationError:
                continue
    return output


def _mean_abs_spearman(pairs: Sequence[tuple[Sequence[float], Sequence[float]]]) -> float:
    values = [abs(spearman(src, tgt)) for src, tgt in pairs]
    return statistics.fmean(values) if values else 0.0


def _within_stratum_shuffle(
    target: Sequence[float],
    strata: Sequence[tuple[str, ...]],
    rng: random.Random,
) -> tuple[float, ...]:
    output = list(float(v) for v in target)
    grouped: dict[tuple[str, ...], list[int]] = defaultdict(list)
    for index, key in enumerate(strata):
        grouped[key].append(index)
    for idxs in grouped.values():
        values = [output[i] for i in idxs]
        rng.shuffle(values)
        for index, value in zip(idxs, values, strict=True):
            output[index] = value
    return tuple(output)


def _circular_shift(target: Sequence[float], rng: random.Random) -> tuple[float, ...]:
    n = len(target)
    if n < 3:
        return tuple(target)
    shift = rng.randrange(1, n)
    values = tuple(float(v) for v in target)
    return values[-shift:] + values[:-shift]


def _block_permutation(target: Sequence[float], rng: random.Random) -> tuple[float, ...]:
    values = [float(v) for v in target]
    n = len(values)
    block = max(2, int(math.sqrt(n)))
    blocks = [values[start : start + block] for start in range(0, n, block)]
    rng.shuffle(blocks)
    return tuple(value for chunk in blocks for value in chunk)


def evaluate_robust_nulls(
    window: CausalWindow,
    *,
    mappings: Sequence[FeatureMapping],
    confounder_strata: Sequence[str],
    null_models: Sequence[str],
    iterations: int,
    seed: int,
    min_delta: float,
    max_p_value: float,
) -> RobustNullEvaluation:
    if iterations < 200:
        raise ValueError("iterations must be >= 200 for robust null evaluation")
    report = robust_coherence_report(
        window, mappings=mappings, confounder_strata=confounder_strata
    )
    observed = report.residual_mean_abs_coherence
    residual_pairs = _valid_residual_pairs(
        window, mappings=mappings, confounder_strata=confounder_strata
    )
    if observed is None or not residual_pairs:
        return RobustNullEvaluation(
            observed=observed,
            max_null_mean=None,
            delta_vs_max_null_mean=None,
            familywise_p_value=None,
            families=(),
            iterations=iterations,
            passed=False,
            reason="NO_VALID_RESIDUAL_PAIRS",
        )
    supported = {
        "within_stratum_shuffle_target",
        "circular_shift_target",
        "block_permutation_target",
    }
    unknown = sorted(set(null_models) - supported)
    if unknown:
        raise ValueError(f"unsupported robust null models: {unknown}")
    rng = random.Random(seed)
    per_family: dict[str, list[float]] = {name: [] for name in null_models}
    max_nulls: list[float] = []
    for _ in range(iterations):
        iteration_values: list[float] = []
        for name in null_models:
            transformed: list[tuple[Sequence[float], Sequence[float]]] = []
            for src, tgt, strata in residual_pairs:
                if name == "within_stratum_shuffle_target":
                    null_target = _within_stratum_shuffle(tgt, strata, rng)
                elif name == "circular_shift_target":
                    null_target = _circular_shift(tgt, rng)
                else:
                    null_target = _block_permutation(tgt, rng)
                try:
                    transformed.append((src, null_target))
                except FractalValidationError:
                    continue
            value = _mean_abs_spearman(transformed)
            per_family[name].append(value)
            iteration_values.append(value)
        max_nulls.append(max(iteration_values) if iteration_values else 0.0)
    families: list[NullFamilyResult] = []
    for name, values in per_family.items():
        ordered = sorted(values)
        q95 = ordered[min(len(ordered) - 1, int(0.95 * len(ordered)))]
        p = (1 + sum(value >= observed for value in values)) / (len(values) + 1)
        families.append(
            NullFamilyResult(name=name, mean=statistics.fmean(values), p_value=p, q95=q95)
        )
    max_mean = statistics.fmean(max_nulls)
    familywise_p = (1 + sum(value >= observed for value in max_nulls)) / (len(max_nulls) + 1)
    delta = observed - max_mean
    passed = delta >= min_delta and familywise_p <= max_p_value
    reason = "PASS" if passed else "FAILED_MAX_NULL_GATE"
    return RobustNullEvaluation(
        observed=observed,
        max_null_mean=max_mean,
        delta_vs_max_null_mean=delta,
        familywise_p_value=familywise_p,
        families=tuple(families),
        iterations=iterations,
        passed=passed,
        reason=reason,
    )
