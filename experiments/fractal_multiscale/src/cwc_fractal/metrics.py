from __future__ import annotations

import math
import statistics
from collections.abc import Iterable
from dataclasses import dataclass


def _as_floats(values: Iterable[float]) -> list[float]:
    output = [float(value) for value in values]
    if len(output) < 2:
        raise ValueError("at least two values are required")
    return output


def zscore(values: Iterable[float]) -> list[float]:
    data = _as_floats(values)
    mean = statistics.fmean(data)
    stdev = statistics.pstdev(data)
    if stdev == 0.0:
        return [0.0 for _ in data]
    return [(value - mean) / stdev for value in data]


def cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    x = [float(value) for value in left]
    y = [float(value) for value in right]
    if not x or not y:
        raise ValueError("vectors cannot be empty")
    if len(x) != len(y):
        raise ValueError("vectors must have equal length")
    dot = sum(a * b for a, b in zip(x, y, strict=True))
    nx = math.sqrt(sum(a * a for a in x))
    ny = math.sqrt(sum(b * b for b in y))
    if nx == 0.0 or ny == 0.0:
        return 0.0
    return dot / (nx * ny)


def box_counting_dimension(
    values: Iterable[float],
    boxes: tuple[int, ...] = (2, 4, 8, 16),
) -> float:
    data = zscore(values)
    n = len(data)
    usable: list[tuple[float, float]] = []
    min_value = min(data)
    max_value = max(data)
    span = max(max_value - min_value, 1e-12)
    for box_count in boxes:
        if box_count < 2 or box_count > n:
            continue
        occupied: set[tuple[int, int]] = set()
        for index, value in enumerate(data):
            x_bin = min(box_count - 1, int(index / n * box_count))
            y_bin = min(box_count - 1, int((value - min_value) / span * box_count))
            occupied.add((x_bin, y_bin))
        usable.append((math.log(box_count), math.log(max(len(occupied), 1))))
    if len(usable) < 2:
        return 0.0
    xs, ys = zip(*usable, strict=True)
    return _linear_slope(list(xs), list(ys))


def hurst_rs(values: Iterable[float], min_chunk: int = 4) -> float:
    data = _as_floats(values)
    chunks: list[tuple[float, float]] = []
    chunk = min_chunk
    while chunk <= len(data) // 2:
        rs_values: list[float] = []
        for start in range(0, len(data) - chunk + 1, chunk):
            segment = data[start : start + chunk]
            mean = statistics.fmean(segment)
            deviations = [value - mean for value in segment]
            cumulative: list[float] = []
            total = 0.0
            for value in deviations:
                total += value
                cumulative.append(total)
            spread = max(cumulative) - min(cumulative)
            stdev = statistics.pstdev(segment)
            if stdev > 0.0:
                rs_values.append(spread / stdev)
        if rs_values:
            chunks.append((math.log(chunk), math.log(statistics.fmean(rs_values))))
        chunk *= 2
    if len(chunks) < 2:
        return 0.5
    xs, ys = zip(*chunks, strict=True)
    return _linear_slope(list(xs), list(ys))


def multiscale_entropy(
    values: Iterable[float],
    scales: tuple[int, ...] = (1, 2, 4),
) -> dict[int, float]:
    data = _as_floats(values)
    return {scale: _coarse_entropy(data, scale) for scale in scales if 1 <= scale <= len(data)}


def roughness(values: Iterable[float]) -> float:
    data = zscore(values)
    if len(data) < 2:
        return 0.0
    return statistics.fmean(abs(b - a) for a, b in zip(data, data[1:], strict=False))


@dataclass(frozen=True)
class FractalMetrics:
    box_dimension: float
    hurst: float
    roughness: float
    multiscale_entropy: dict[int, float]

    def to_dict(self) -> dict[str, float | dict[int, float]]:
        return {
            "box_dimension": self.box_dimension,
            "hurst": self.hurst,
            "roughness": self.roughness,
            "multiscale_entropy": dict(self.multiscale_entropy),
        }


def compute_fractal_metrics(values: Iterable[float]) -> FractalMetrics:
    data = _as_floats(values)
    return FractalMetrics(
        box_dimension=box_counting_dimension(data),
        hurst=hurst_rs(data),
        roughness=roughness(data),
        multiscale_entropy=multiscale_entropy(data),
    )


def _coarse_entropy(data: list[float], scale: int) -> float:
    coarse = [
        statistics.fmean(data[start : start + scale])
        for start in range(0, len(data) - scale + 1, scale)
    ]
    if len(coarse) < 2:
        return 0.0
    normalized = zscore(coarse)
    signs = [1 if value >= 0 else 0 for value in normalized]
    counts = {0: signs.count(0), 1: signs.count(1)}
    total = len(signs)
    entropy = 0.0
    for count in counts.values():
        if count:
            probability = count / total
            entropy -= probability * math.log2(probability)
    return entropy


def _linear_slope(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        raise ValueError("slope requires matching vectors of length >= 2")
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    denominator = sum((x - mean_x) ** 2 for x in xs)
    if denominator == 0.0:
        return 0.0
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    return numerator / denominator
