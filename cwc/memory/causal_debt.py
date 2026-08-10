"""Deferred causal-credit ledger.

This module implements a narrow computational object, not a neuroscience claim.
Candidate dependencies can retain weak observational eligibility while authoritative
credit is withheld until matched counterfactual evidence is directionally coherent
across more than one context.

Design invariants
-----------------
* observational association is *eligibility*, never causal authority;
* replay evidence is append-only at the ledger API;
* consolidation is fail-closed under insufficient context coverage;
* debt is finite, deterministic, and prioritizes consequential unresolved candidates;
* absence of counterfactual leverage reduces authority rather than being interpreted
  as evidence for a causal effect.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import fmean
from typing import Iterable


@dataclass(frozen=True, slots=True)
class ReplayEvidence:
    """One replay probe for one candidate in one context.

    ``effect`` is a signed causal-leverage estimate in an experiment-declared unit.
    Positive values mean the candidate perturbation supports the candidate's initial
    signed direction; zero means no measured leverage.  ``surprise`` is optional
    scheduler information and has no direct authority over consolidation.
    """

    candidate_id: str
    context_id: str
    effect: float
    surprise: float = 0.0

    def __post_init__(self) -> None:
        if not self.candidate_id or not self.context_id:
            raise ValueError("candidate_id and context_id must be non-empty")
        if not math.isfinite(self.effect) or not math.isfinite(self.surprise):
            raise ValueError("effect and surprise must be finite")
        if self.surprise < 0.0:
            raise ValueError("surprise must be non-negative")


@dataclass(frozen=True, slots=True)
class ConsolidationDecision:
    candidate_id: str
    consolidated: bool
    reason: str
    credit: float
    lower_confidence: float
    context_count: int
    replay_count: int


@dataclass(frozen=True, slots=True)
class CandidateSnapshot:
    candidate_id: str
    eligibility: float
    observational_credit: float
    causal_credit: float
    uncertainty: float
    lower_confidence: float
    context_count: int
    replay_count: int
    invariance: float
    debt: float
    consolidated: bool


@dataclass(slots=True)
class _Candidate:
    candidate_id: str
    eligibility: float
    observational_credit: float
    evidence: list[ReplayEvidence] = field(default_factory=list)


class CausalDebtLedger:
    """Append-only candidate ledger with cross-context consolidation gates."""

    def __init__(
        self,
        *,
        min_replays: int = 3,
        min_contexts: int = 2,
        min_abs_credit: float = 0.15,
        z_value: float = 1.64,
        prior_strength: float = 1.0,
    ) -> None:
        if min_replays < 1 or min_contexts < 1:
            raise ValueError("minimum replay/context counts must be positive")
        if min_abs_credit < 0.0 or z_value < 0.0 or prior_strength <= 0.0:
            raise ValueError("invalid ledger thresholds")
        self.min_replays = min_replays
        self.min_contexts = min_contexts
        self.min_abs_credit = min_abs_credit
        self.z_value = z_value
        self.prior_strength = prior_strength
        self._candidates: dict[str, _Candidate] = {}

    def register(self, candidate_id: str, *, eligibility: float, observational_credit: float) -> None:
        if not candidate_id:
            raise ValueError("candidate_id must be non-empty")
        if candidate_id in self._candidates:
            raise ValueError(f"duplicate candidate {candidate_id!r}")
        if not math.isfinite(eligibility) or not math.isfinite(observational_credit):
            raise ValueError("candidate values must be finite")
        if eligibility < 0.0:
            raise ValueError("eligibility must be non-negative")
        self._candidates[candidate_id] = _Candidate(
            candidate_id=candidate_id,
            eligibility=eligibility,
            observational_credit=observational_credit,
        )

    @property
    def candidate_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._candidates))

    def append(self, evidence: ReplayEvidence) -> None:
        try:
            candidate = self._candidates[evidence.candidate_id]
        except KeyError as exc:
            raise KeyError(f"unknown candidate {evidence.candidate_id!r}") from exc
        candidate.evidence.append(evidence)

    def evidence(self, candidate_id: str) -> tuple[ReplayEvidence, ...]:
        return tuple(self._get(candidate_id).evidence)

    def _get(self, candidate_id: str) -> _Candidate:
        try:
            return self._candidates[candidate_id]
        except KeyError as exc:
            raise KeyError(f"unknown candidate {candidate_id!r}") from exc

    @staticmethod
    def _mean_se(values: Iterable[float]) -> tuple[float, float]:
        vals = tuple(float(v) for v in values)
        if not vals:
            return 0.0, float("inf")
        mean = fmean(vals)
        if len(vals) == 1:
            # Deliberately conservative: one intervention cannot create precision.
            return mean, 1.0
        variance = sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)
        return mean, math.sqrt(max(variance, 1e-12) / len(vals))

    def _context_means(self, candidate: _Candidate) -> dict[str, float]:
        grouped: dict[str, list[float]] = {}
        for ev in candidate.evidence:
            grouped.setdefault(ev.context_id, []).append(ev.effect)
        return {ctx: fmean(vals) for ctx, vals in grouped.items()}

    def causal_credit(self, candidate_id: str) -> float:
        candidate = self._get(candidate_id)
        if not candidate.evidence:
            return 0.0
        # Shrink very small replay counts toward zero; observational association is
        # not used as a causal prior.
        raw = fmean(ev.effect for ev in candidate.evidence)
        n = len(candidate.evidence)
        return raw * n / (n + self.prior_strength)

    def uncertainty(self, candidate_id: str) -> float:
        candidate = self._get(candidate_id)
        if not candidate.evidence:
            return 1.0
        _, se = self._mean_se(ev.effect for ev in candidate.evidence)
        # Count uncertainty even when empirical variance is zero.
        count_floor = 1.0 / math.sqrt(len(candidate.evidence) + 1.0)
        return max(se, count_floor)

    def invariance(self, candidate_id: str) -> float:
        """Return [0,1] cross-context directional coherence.

        With fewer than ``min_contexts`` contexts this returns zero by design.
        Otherwise it is the fraction of context means sharing the global non-zero
        sign, multiplied by the weakest/strongest absolute context-effect ratio.
        This penalizes sign flips and context-specific collapse.
        """
        candidate = self._get(candidate_id)
        means = self._context_means(candidate)
        if len(means) < self.min_contexts:
            return 0.0
        global_mean = fmean(means.values())
        if math.isclose(global_mean, 0.0, abs_tol=1e-12):
            return 0.0
        sign = 1.0 if global_mean > 0 else -1.0
        signed = [sign * value for value in means.values()]
        coherent_fraction = sum(value > 0.0 for value in signed) / len(signed)
        magnitudes = [abs(value) for value in means.values()]
        max_mag = max(magnitudes)
        if max_mag <= 1e-12:
            return 0.0
        stability = min(magnitudes) / max_mag
        return max(0.0, min(1.0, coherent_fraction * stability))

    def lower_confidence(self, candidate_id: str) -> float:
        candidate = self._get(candidate_id)
        if not candidate.evidence:
            return 0.0
        mean, se = self._mean_se(ev.effect for ev in candidate.evidence)
        magnitude_lcb = max(0.0, abs(mean) - self.z_value * se)
        return magnitude_lcb * self.invariance(candidate_id)

    def debt(self, candidate_id: str) -> float:
        """Priority score for unresolved but potentially consequential credit.

        Debt is high when observational eligibility is high, causal uncertainty is
        high, and authoritative precision is low.  Once a candidate is consolidated
        or strongly falsified, debt falls.  A small exploration floor prevents a
        candidate with zero first-probe effect from becoming permanently unreachable.
        """
        candidate = self._get(candidate_id)
        decision = self.consolidation(candidate_id)
        if decision.consolidated:
            return 0.0
        uncertainty = self.uncertainty(candidate_id)
        credit = abs(self.causal_credit(candidate_id))
        lcb = self.lower_confidence(candidate_id)
        unresolved = max(0.0, candidate.eligibility - lcb)
        exploration = 0.05 / math.sqrt(len(candidate.evidence) + 1.0)
        return max(0.0, candidate.eligibility * uncertainty + 0.5 * credit + unresolved + exploration)

    def resolution_aware_debt(self, candidate_id: str) -> float:
        """V2 replay priority that allows negative evidence to discharge debt.

        This intentionally does **not** change consolidation semantics.  Before any
        intervention, observational eligibility seeds priority.  As replay evidence
        accumulates, that observational term decays as ``1/(n+1)`` and measured
        causal leverage becomes the dominant term.  Thus repeated zero-effect probes
        lower scheduling priority without being converted into a positive causal
        claim.

        The original :meth:`debt` method is retained unchanged for exact V1
        reproducibility.
        """
        candidate = self._get(candidate_id)
        decision = self.consolidation(candidate_id)
        if decision.consolidated:
            return 0.0
        n = len(candidate.evidence)
        decayed_eligibility = candidate.eligibility / (n + 1.0)
        causal_term = abs(self.causal_credit(candidate_id)) * (1.0 + self.uncertainty(candidate_id))
        exploration = 0.05 / math.sqrt(n + 1.0)
        return max(0.0, decayed_eligibility + causal_term + exploration)

    def consolidation(self, candidate_id: str) -> ConsolidationDecision:
        candidate = self._get(candidate_id)
        n = len(candidate.evidence)
        contexts = len(self._context_means(candidate))
        credit = self.causal_credit(candidate_id)
        lcb = self.lower_confidence(candidate_id)
        if n < self.min_replays:
            return ConsolidationDecision(candidate_id, False, "insufficient_replays", credit, lcb, contexts, n)
        if contexts < self.min_contexts:
            return ConsolidationDecision(candidate_id, False, "insufficient_contexts", credit, lcb, contexts, n)
        context_means = tuple(self._context_means(candidate).values())
        has_positive = any(value > 1e-12 for value in context_means)
        has_negative = any(value < -1e-12 for value in context_means)
        if has_positive and has_negative:
            return ConsolidationDecision(candidate_id, False, "context_fragile", credit, lcb, contexts, n)
        if max((abs(value) for value in context_means), default=0.0) < self.min_abs_credit:
            return ConsolidationDecision(candidate_id, False, "insufficient_causal_precision", credit, lcb, contexts, n)
        if self.invariance(candidate_id) <= 0.0:
            return ConsolidationDecision(candidate_id, False, "context_fragile", credit, lcb, contexts, n)
        if lcb < self.min_abs_credit:
            return ConsolidationDecision(candidate_id, False, "insufficient_causal_precision", credit, lcb, contexts, n)
        return ConsolidationDecision(candidate_id, True, "cross_context_causal_credit", credit, lcb, contexts, n)

    def snapshot(self, candidate_id: str) -> CandidateSnapshot:
        candidate = self._get(candidate_id)
        decision = self.consolidation(candidate_id)
        return CandidateSnapshot(
            candidate_id=candidate_id,
            eligibility=candidate.eligibility,
            observational_credit=candidate.observational_credit,
            causal_credit=self.causal_credit(candidate_id),
            uncertainty=self.uncertainty(candidate_id),
            lower_confidence=self.lower_confidence(candidate_id),
            context_count=decision.context_count,
            replay_count=decision.replay_count,
            invariance=self.invariance(candidate_id),
            debt=self.debt(candidate_id) if decision.consolidated is False else 0.0,
            consolidated=decision.consolidated,
        )
