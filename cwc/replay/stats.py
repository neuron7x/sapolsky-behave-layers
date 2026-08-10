"""Small dependency-free paired random-sign tests used by replay experiments."""
from __future__ import annotations

import itertools
import math
from collections.abc import Sequence


def _t_stat(values: Sequence[float]) -> float:
    n = len(values)
    if n < 2:
        raise ValueError("at least two paired differences required")
    mean = sum(values) / n
    variance = sum((x - mean) ** 2 for x in values) / (n - 1)
    if variance <= 1e-18:
        if mean > 0:
            return float("inf")
        if mean < 0:
            return float("-inf")
        return 0.0
    return mean / math.sqrt(variance / n)


def exact_max_t_fwer(comparisons: Sequence[Sequence[float]]) -> tuple[float, ...]:
    """One-sided exact random-sign max-T p-values for paired comparisons.

    All comparisons must contain the same subjects.  Under the joint sharp null,
    each subject receives the same sign flip across comparisons, preserving their
    dependence.  This is exact for n <= 20 in the current confirmatory protocol.
    """
    if not comparisons:
        raise ValueError("comparisons must be non-empty")
    n = len(comparisons[0])
    if n < 2 or any(len(row) != n for row in comparisons):
        raise ValueError("comparison lengths must match and be >= 2")
    if n > 20:
        raise ValueError("exact enumeration capped at 20 pairs")
    observed = [_t_stat(row) for row in comparisons]
    exceed = [0 for _ in comparisons]
    total = 0
    for signs in itertools.product((-1.0, 1.0), repeat=n):
        perm_stats = [
            _t_stat([x * s for x, s in zip(row, signs, strict=True)])
            for row in comparisons
        ]
        max_stat = max(perm_stats)
        for idx, obs in enumerate(observed):
            if max_stat >= obs - 1e-15:
                exceed[idx] += 1
        total += 1
    return tuple(count / total for count in exceed)
