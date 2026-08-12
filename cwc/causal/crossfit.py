"""Group-preserving cross-fitting primitives.

Splits operate on independent groups (request/document/episode), not nested token
rows.  This prevents a controller/outcome model from seeing another token from the
same experimental unit during training.
"""

from __future__ import annotations

import random
from collections.abc import Sequence


def grouped_kfold(
    groups: Sequence[str],
    *,
    n_splits: int,
    seed: int,
) -> list[tuple[list[int], list[int]]]:
    """Return deterministic group-disjoint ``(train_idx, test_idx)`` folds."""
    if not groups or any(not g for g in groups):
        raise ValueError("groups must be non-empty strings")
    unique = sorted(set(groups))
    if n_splits < 2 or n_splits > len(unique):
        raise ValueError("n_splits must be in [2, number of unique groups]")

    shuffled = unique[:]
    random.Random(seed).shuffle(shuffled)
    fold_groups = [set() for _ in range(n_splits)]
    for i, group in enumerate(shuffled):
        fold_groups[i % n_splits].add(group)

    result: list[tuple[list[int], list[int]]] = []
    all_idx = list(range(len(groups)))
    for held_out in fold_groups:
        test = [i for i, group in enumerate(groups) if group in held_out]
        test_set = set(test)
        train = [i for i in all_idx if i not in test_set]
        if {groups[i] for i in train} & {groups[i] for i in test}:
            raise AssertionError("group leakage detected")
        result.append((train, test))
    return result


def fold_assignment(groups: Sequence[str], *, n_splits: int, seed: int) -> dict[str, int]:
    """Return a machine-readable group→fold mapping for provenance manifests."""
    folds = grouped_kfold(groups, n_splits=n_splits, seed=seed)
    out: dict[str, int] = {}
    for fold, (_train, test) in enumerate(folds):
        for idx in test:
            group = groups[idx]
            prior = out.setdefault(group, fold)
            if prior != fold:
                raise AssertionError("group assigned to more than one fold")
    return out
