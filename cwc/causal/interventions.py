"""Randomization and adversarial-control utilities for causal compute allocation."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
import random


def balanced_randomized_assignments(
    unit_ids: Sequence[str],
    actions: Sequence[str],
    *,
    seed: int,
    strata: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Create a deterministic, approximately balanced randomized intervention.

    Units are randomized *within* preregistered strata.  For every stratum the
    count difference between any two actions is at most one.  The routine returns
    only assignments; it cannot peek at outcomes.
    """
    if not unit_ids or len(set(unit_ids)) != len(unit_ids) or any(not u for u in unit_ids):
        raise ValueError("unit_ids must be unique non-empty strings")
    if not actions or len(set(actions)) != len(actions) or any(not a for a in actions):
        raise ValueError("actions must be unique non-empty strings")
    if strata is not None and set(strata) != set(unit_ids):
        raise ValueError("strata must contain exactly one label for every unit")

    grouped: dict[str, list[str]] = defaultdict(list)
    for unit in unit_ids:
        grouped[(strata or {}).get(unit, "__all__")].append(unit)

    rng = random.Random(seed)
    assignment: dict[str, str] = {}
    for label in sorted(grouped):
        units = sorted(grouped[label])
        rng.shuffle(units)
        cycle: list[str] = []
        while len(cycle) < len(units):
            block = list(actions)
            rng.shuffle(block)
            cycle.extend(block)
        for unit, action in zip(units, cycle, strict=False):
            assignment[unit] = action
    return assignment


def permute_context_labels(
    labels: Sequence[str],
    *,
    seed: int,
) -> list[str]:
    """Permutation null that preserves the marginal context-label counts."""
    if not labels or any(not label for label in labels):
        raise ValueError("labels must be non-empty strings")
    out = list(labels)
    random.Random(seed).shuffle(out)
    return out


def permute_each_replicate_context_rows(
    matrices: Sequence[Sequence[Sequence[float]]],
    *,
    seed: int,
) -> list[list[list[float]]]:
    """Destroy stable context×action structure while preserving every cell value.

    Each independent replicate receives its own random row permutation.  This is
    stricter than applying one global permutation, which would merely rename
    contexts and leave the oracle gap invariant.
    """
    rng = random.Random(seed)
    out: list[list[list[float]]] = []
    for matrix in matrices:
        copied = [list(map(float, row)) for row in matrix]
        if not copied or not copied[0]:
            raise ValueError("matrices must be non-empty")
        width = len(copied[0])
        if any(len(row) != width for row in copied):
            raise ValueError("matrices must be rectangular")
        rng.shuffle(copied)
        out.append(copied)
    return out
