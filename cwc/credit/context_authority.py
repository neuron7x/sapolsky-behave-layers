from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ContextAuthorityDecision:
    state: str
    candidate: str | None
    sign: int | None
    context_signs: dict[str, int]


def decide_context_direction(
    credits_by_context: Mapping[str, Mapping[str, float]], *, tolerance: float = 1e-9
) -> ContextAuthorityDecision:
    if not credits_by_context:
        return ContextAuthorityDecision("ABSTAIN_NO_CONTEXT_EVIDENCE", None, None, {})
    candidates = sorted(next(iter(credits_by_context.values())).keys())
    mean_abs = {
        p: sum(abs(float(v[p])) for v in credits_by_context.values()) / len(credits_by_context) for p in candidates
    }
    candidate = max(candidates, key=lambda p: (mean_abs[p], p))
    signs: dict[str, int] = {}
    for context, values in credits_by_context.items():
        x = float(values[candidate])
        signs[str(context)] = 0 if abs(x) <= tolerance else (1 if x > 0 else -1)
    nonzero = {v for v in signs.values() if v != 0}
    if len(nonzero) > 1:
        return ContextAuthorityDecision("CONTEXT_CONDITIONAL_ONLY", candidate, None, signs)
    if not nonzero:
        return ContextAuthorityDecision("ABSTAIN_UNRESOLVED_DIRECTION", candidate, None, signs)
    sign = next(iter(nonzero))
    if any(v == 0 for v in signs.values()):
        return ContextAuthorityDecision("CONTEXT_CONDITIONAL_ONLY", candidate, None, signs)
    return ContextAuthorityDecision("GLOBAL_DIRECTION_ACCEPT", candidate, sign, signs)
