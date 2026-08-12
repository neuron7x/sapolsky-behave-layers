"""Canonical statistical helpers for the CWC WP-1 measurement layer.

Single source of truth: `scripts/instrumentation_overhead.py`,
`scripts/infer_bench.py`, and the meters previously each carried a private copy
of `percentile`; they now all import from here so there is exactly one tested
implementation (DRY, and a single place a mutation test can target).

`percentile` is deliberately constant-exact: for a list whose two interpolation
endpoints are equal it returns that endpoint verbatim, with no float mixing, so
the deterministic reporting path stays byte-reproducible (Hypothesis found that
the naive `lo*(1-w) + hi*w` form loses a ULP even when lo == hi).
"""

from __future__ import annotations

import random
import statistics


def percentile(values: list[float], q: float) -> float:
    """Linear-interpolation percentile. q in [0, 1]. Empty list -> 0.0."""
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    index = (len(ordered) - 1) * q
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    low_value = ordered[lower]
    high_value = ordered[upper]
    if low_value == high_value:
        # Constant-exact: no float mixing when the endpoints coincide.
        return low_value
    weight = index - lower
    return low_value * (1.0 - weight) + high_value * weight


def bootstrap_ci(
    deltas: list[float], *, resamples: int = 2000, seed: int, confidence: float = 0.95
) -> tuple[float, float]:
    """Percentile bootstrap CI of the mean. Deterministic given `seed`.

    For a constant input every resample has the same mean, so the interval
    collapses to that exact constant (uses `statistics.mean`, which is
    fraction-exact for a constant list, not `fmean`, whose float summation
    loses a ULP — again found by Hypothesis).
    """
    if not deltas:
        return 0.0, 0.0
    if len(deltas) == 1:
        return deltas[0], deltas[0]
    rng = random.Random(seed)
    n = len(deltas)
    means: list[float] = []
    for _ in range(resamples):
        sample = [deltas[rng.randrange(n)] for _ in range(n)]
        means.append(statistics.mean(sample))
    means.sort()
    tail = (1.0 - confidence) / 2.0
    lower_idx = int(tail * len(means))
    upper_idx = min(int((1.0 - tail) * len(means)), len(means) - 1)
    return means[lower_idx], means[upper_idx]
