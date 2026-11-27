"""Exact one-observation decision value under an explicit countermodel mixture."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from fractions import Fraction
from itertools import product


@dataclass(frozen=True, slots=True)
class EvidenceProbe:
    probe_id: str
    cost: int | Fraction
    laws: tuple[tuple[int | Fraction, ...], ...]


@dataclass(frozen=True, slots=True)
class EvidencePolicyValue:
    probe_id: str
    outcome_actions: tuple[int, ...]
    cost: Fraction
    radius: Fraction
    nominal_advantage: Fraction


@dataclass(frozen=True, slots=True)
class EvidenceValue:
    robust_first: EvidencePolicyValue | None
    nominal_first: EvidencePolicyValue | None
    evaluated_policies: int


def _exact(value: int | Fraction) -> Fraction:
    if type(value) not in (int, Fraction):
        raise ValueError("expected exact rational data")
    return Fraction(value)


def _value(
    utility: tuple[tuple[Fraction, ...], ...],
    weights: tuple[Fraction, ...],
    payoff: tuple[Fraction, ...],
    target: Fraction,
) -> tuple[Fraction, Fraction] | None:
    radius = Fraction(1)
    margins = []
    for constant in zip(*utility, strict=True):
        gains = tuple(p - a for p, a in zip(payoff, constant, strict=True))
        nominal = sum((p * d for p, d in zip(weights, gains, strict=True)), Fraction(0))
        if nominal < target:
            return None
        challenge = min(d for p, d in zip(weights, gains, strict=True) if p == 0)
        if challenge < target:
            radius = min(radius, (nominal - target) / (nominal - challenge))
        margins.append(nominal)
    return radius, min(margins)


def robust_evidence_value(
    *,
    utilities: Sequence[Sequence[int | Fraction]],
    nominal_weights: Sequence[int | Fraction],
    probes: Sequence[EvidenceProbe],
    target_advantage: int | Fraction,
) -> EvidenceValue:
    """Compare informed policies against all free fixed actions at every mixture.

    Positive weights designate the fixed nominal distribution. Zero-weight rows
    designate the countermodel set. The outcome policy may use the observation,
    and every policy is evaluated before any observation is seen.
    """
    target = _exact(target_advantage)
    if target <= 0 or not 2 <= len(utilities) <= 8 or len(nominal_weights) != len(utilities):
        raise ValueError("positive target and aligned world roster required")
    if not 1 <= len(probes) <= 8:
        raise ValueError("expected one to eight probes")
    if not 1 <= len(utilities[0]) <= 4 or any(len(row) != len(utilities[0]) for row in utilities):
        raise ValueError("invalid action roster")
    utility = tuple(tuple(map(_exact, row)) for row in utilities)
    weights = tuple(map(_exact, nominal_weights))
    if min(weights) != 0 or sum(weights) != 1:
        raise ValueError("expected normalized non-negative weights and explicit countermodels")
    if any(type(probe.probe_id) is not str or not probe.probe_id.strip() for probe in probes):
        raise ValueError("invalid probe id")
    if len({p.probe_id for p in probes}) != len(probes):
        raise ValueError("duplicate probe id")

    candidates = []
    evaluations = 0
    for probe in probes:
        cost = _exact(probe.cost)
        if cost < 0 or len(probe.laws) != len(utility):
            raise ValueError("invalid probe cost or law roster")
        outcomes = len(probe.laws[0])
        if not 1 <= outcomes <= 4 or any(len(row) != outcomes for row in probe.laws):
            raise ValueError("invalid outcome roster")
        laws = tuple(tuple(map(_exact, row)) for row in probe.laws)
        if any(min(row) < 0 or sum(row) != 1 for row in laws):
            raise ValueError("invalid observation distribution")
        for policy in product(range(len(utility[0])), repeat=outcomes):
            evaluations += 1
            payoff = tuple(
                sum((p * row[a] for p, a in zip(law, policy, strict=True)), Fraction(0)) - cost
                for row, law in zip(utility, laws, strict=True)
            )
            bounds = _value(utility, weights, payoff, target)
            if bounds is not None:
                radius, nominal = bounds
                candidates.append(EvidencePolicyValue(probe.probe_id, policy, cost, radius, nominal))

    robust = min(candidates, default=None, key=lambda p: (
        -p.radius, -p.nominal_advantage, p.cost, p.probe_id, p.outcome_actions,
    ))
    nominal_best = min(candidates, default=None, key=lambda p: (
        -p.nominal_advantage, -p.radius, p.cost, p.probe_id, p.outcome_actions,
    ))
    return EvidenceValue(robust, nominal_best, evaluations)
