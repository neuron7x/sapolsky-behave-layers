"""Shared evidence accounting and bounded, selective policy revision."""
from __future__ import annotations

import hashlib
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction

from cwc.epistemics.evidence_sequential import Scalar, Vector
from cwc.epistemics.evidence_value import _exact

_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


@dataclass(frozen=True, slots=True)
class EvidenceCharge:
    evidence_id: str
    digest: str
    cost: Scalar


@dataclass(frozen=True, slots=True)
class EvidenceComponent:
    world_payoffs: tuple[tuple[str, Scalar], ...]
    work_cost: Scalar
    evidence: tuple[EvidenceCharge, ...] = ()


def compose_evidence_payoffs(
    worlds: Sequence[str], components: Sequence[EvidenceComponent], budget: Scalar,
) -> tuple[Vector, Fraction]:
    """Compose additive payoffs over matching worlds; charge each shared item once."""
    if (not worlds or len(set(worlds)) != len(worlds) or any(not world for world in worlds)
            or not components or _exact(budget) < 0):
        raise ValueError("invalid composition roster or budget")
    total_payoffs = dict.fromkeys(worlds, Fraction(0))
    shared: dict[str, tuple[str, Fraction]] = {}
    cost = Fraction(0)
    for component in components:
        payouts = dict(component.world_payoffs)
        if len(payouts) != len(component.world_payoffs) or set(payouts) != set(worlds):
            raise ValueError("component must use the same complete world roster")
        for world, value in payouts.items():
            total_payoffs[world] += _exact(value)
        work = _exact(component.work_cost)
        if work < 0:
            raise ValueError("negative work cost")
        cost += work
        for evidence in component.evidence:
            charge = _exact(evidence.cost)
            if not evidence.evidence_id or not _DIGEST.fullmatch(evidence.digest) or charge < 0:
                raise ValueError("invalid evidence charge")
            record = (evidence.digest, charge)
            if record != shared.setdefault(evidence.evidence_id, record):
                raise ValueError("conflicting shared evidence identity or cost")
    cost += sum((item[1] for item in shared.values()), Fraction(0))
    if cost > budget:
        raise ValueError("composition exceeds its shared budget")
    return tuple(total_payoffs[world] - cost for world in worlds), cost


@dataclass(frozen=True, slots=True)
class CountermodelCandidate:
    candidate_id: str
    signature: str
    proxy_harm: Scalar


@dataclass(frozen=True, slots=True)
class ChallengeResult:
    checked: tuple[str, ...]
    contradicted: tuple[str, ...]


def challenge_countermodels(
    *, candidates: Sequence[CountermodelCandidate], observation_signature: str, budget: int,
    inspect: Callable[[str], Scalar], mode: str, seed: int,
) -> ChallengeResult:
    """Order compatible challenges before the independent judge sees the roster."""
    if (type(budget) is not int or budget < 0 or type(seed) is not int or not observation_signature
            or mode not in {"guided", "uniform"}):
        raise ValueError("invalid challenge contract")
    if any(not candidate.candidate_id for candidate in candidates):
        raise ValueError("empty candidate id")
    if len({candidate.candidate_id for candidate in candidates}) != len(candidates):
        raise ValueError("duplicate candidate id")
    eligible = [candidate for candidate in candidates if candidate.signature == observation_signature]
    if mode == "guided":
        eligible.sort(key=lambda item: (-_exact(item.proxy_harm), item.candidate_id))
    else:
        eligible.sort(key=lambda item: (
            hashlib.sha256(f"{seed}|{item.candidate_id}".encode()).digest(), item.candidate_id,
        ))
    checked = tuple(item.candidate_id for item in eligible[:budget])
    contradicted = tuple(key for key in checked if _exact(inspect(key)) > 0)
    return ChallengeResult(checked, contradicted)


def invalidated_certificates(
    dependencies: Mapping[str, Sequence[str]], before: Mapping[str, str], after: Mapping[str, str],
) -> tuple[str, ...]:
    """Propagate changed evidence through a fixed, bounded decision DAG."""
    if len(dependencies) > 64 or set(dependencies) & (set(before) | set(after)):
        raise ValueError("invalid certificate roster")
    if any(not key or not _DIGEST.fullmatch(digest)
           for snapshot in (before, after) for key, digest in snapshot.items()):
        raise ValueError("invalid snapshot identity")
    if any(not key or not edges for key, edges in dependencies.items()):
        raise ValueError("a certificate requires identity and evidence")
    visited: dict[str, bool] = {}
    active: set[str] = set()

    def walk(key: str) -> bool:
        if key in before:
            return before[key] != after.get(key)
        if key not in dependencies:
            raise ValueError("unknown certificate dependency")
        if key in active:
            raise ValueError("cyclic certificate dependencies")
        if key not in visited:
            active.add(key)
            # Check every edge even after a changed dependency is discovered.
            edges = [walk(parent) for parent in dependencies[key]]
            active.remove(key)
            visited[key] = any(edges)
        return visited[key]

    return tuple(key for key in sorted(dependencies) if walk(key))
