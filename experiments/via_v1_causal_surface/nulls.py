"""Structural and permutation nulls for the VIA-V1 causal opportunity audit."""
from __future__ import annotations

import random
from collections.abc import Sequence

from cwc.causal.cate import collapse_context, destroy_interaction, oracle_gap
from cwc.causal.interventions import permute_each_replicate_context_rows


def structural_nulls(mean_matrix: Sequence[Sequence[float]]) -> dict[str, float]:
    additive = destroy_interaction(mean_matrix)
    collapsed = collapse_context(mean_matrix)
    return {
        "interaction_destroyed_gap": float(oracle_gap(additive)["gap"]),
        "collapsed_context_gap": float(oracle_gap(collapsed)["gap"]),
    }


def permutation_gaps(
    matrices: Sequence[Sequence[Sequence[float]]],
    *,
    n_permutations: int,
    seed: int,
) -> list[float]:
    """Diagnostic null distribution after independently relabelling contexts per replicate."""
    if n_permutations < 1:
        raise ValueError("n_permutations must be positive")
    # Draw child seeds up front so adding analysis after this function cannot
    # perturb the permutation sequence.
    rng = random.Random(seed)
    child_seeds = [rng.randrange(0, 2**63) for _ in range(n_permutations)]
    out: list[float] = []
    for child in child_seeds:
        permuted = permute_each_replicate_context_rows(matrices, seed=child)
        n = len(permuted)
        n_c = len(permuted[0])
        n_a = len(permuted[0][0])
        mean_matrix = [
            [sum(float(permuted[s][c][a]) for s in range(n)) / n for a in range(n_a)]
            for c in range(n_c)
        ]
        out.append(float(oracle_gap(mean_matrix)["gap"]))
    return out
