"""Deterministic/reproducible replay scheduling policies."""

from __future__ import annotations

import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from cwc.memory.causal_debt import CausalDebtLedger


@dataclass(frozen=True, slots=True)
class ReplayChoice:
    candidate_id: str
    context_id: str


def _argmax_stable(scores: Mapping[str, float]) -> str:
    if not scores:
        raise ValueError("scores must be non-empty")
    return max(sorted(scores), key=lambda key: scores[key])


def choose_candidate(
    policy: str,
    *,
    ledger: CausalDebtLedger,
    observational_strength: Mapping[str, float],
    replay_counts: Mapping[str, int],
    rng: random.Random,
    fifo_index: int = 0,
) -> str:
    ids = ledger.candidate_ids
    if not ids:
        raise ValueError("ledger has no candidates")
    if policy.startswith("fifo"):
        return ids[fifo_index % len(ids)]
    if policy.startswith("uniform"):
        return rng.choice(ids)
    if policy.startswith("rpe"):
        # In this controlled benchmark initial absolute observational association
        # serves as a fixed prediction-error salience proxy. Ties are stable.
        return _argmax_stable({cid: abs(observational_strength[cid]) for cid in ids})
    if policy.startswith("uncertainty"):
        return _argmax_stable({cid: 1.0 / (1.0 + replay_counts.get(cid, 0)) for cid in ids})
    if policy.startswith("causal_debt_v2"):
        return _argmax_stable({cid: ledger.resolution_aware_debt(cid) for cid in ids})
    if policy.startswith("causal_debt"):
        return _argmax_stable({cid: ledger.debt(cid) for cid in ids})
    raise ValueError(f"unknown replay policy {policy!r}")


def choose_least_covered_context(
    candidate_id: str,
    *,
    contexts: Sequence[str],
    ledger: CausalDebtLedger,
    rng: random.Random,
    randomize: bool,
) -> str:
    if not contexts:
        raise ValueError("contexts must be non-empty")
    if randomize:
        return rng.choice(tuple(contexts))
    counts = dict.fromkeys(contexts, 0)
    for ev in ledger.evidence(candidate_id):
        if ev.context_id in counts:
            counts[ev.context_id] += 1
    minimum = min(counts.values())
    tied = sorted(ctx for ctx, count in counts.items() if count == minimum)
    return tied[0]
