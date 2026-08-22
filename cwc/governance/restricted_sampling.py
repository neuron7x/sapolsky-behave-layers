from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class RestrictedAdaptiveSamplingPolicy:
    target_distribution: tuple[tuple[str, float], ...]
    minimum_propensity: float
    max_importance_weight: float
    policy_digest: str
    method: str = "FROZEN_TARGET_PREDICTABLE_PROPENSITY_POLICY_V1"


def certify_restricted_adaptive_policy(
    *,
    target_distribution: Mapping[str, float],
    minimum_propensity: float,
) -> RestrictedAdaptiveSamplingPolicy:
    """Certify a narrow production policy compatible with IPW e-processes.

    The target distribution q is frozen. The online selector may adapt to past
    information, but every target-support item must retain predictable selection
    probability pi_t(i) >= minimum_propensity before its current outcome is seen.
    Hence q(i)/pi_t(i) <= max_i q(i)/minimum_propensity.

    This does not certify outcome-dependent propensities, hidden filtering, or
    arbitrary nonstationary target means.
    """
    if not target_distribution:
        raise ValueError("non-empty target_distribution required")
    q = {str(k): float(v) for k, v in target_distribution.items()}
    if any(not k.strip() for k in q):
        raise ValueError("non-empty target ids required")
    if any(not math.isfinite(v) or v < 0.0 or v > 1.0 for v in q.values()):
        raise ValueError("target probabilities must lie in [0,1]")
    if not math.isclose(math.fsum(q.values()), 1.0, abs_tol=1e-12, rel_tol=0.0):
        raise ValueError("target_distribution must sum to 1")
    pmin = float(minimum_propensity)
    if not math.isfinite(pmin) or not 0.0 < pmin <= 1.0:
        raise ValueError("minimum_propensity must be in (0,1]")
    support = [(k, q[k]) for k in sorted(q) if q[k] > 0.0]
    if not support:
        raise ValueError("positive target support required")
    if pmin * len(support) > 1.0 + 1e-12:
        raise ValueError("minimum_propensity infeasible over target support")
    wmax = max(v / pmin for _, v in support)
    payload = {"target_distribution": support, "minimum_propensity": pmin, "max_importance_weight": wmax}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return RestrictedAdaptiveSamplingPolicy(tuple(support), pmin, wmax, digest)
