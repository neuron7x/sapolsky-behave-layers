from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True, slots=True)
class WeightedL1TransportGeometry:
    feature_names: tuple[str, ...]
    feature_weights: tuple[float, ...]
    coordinate_lipschitz: tuple[float, ...]
    global_lipschitz_upper: float
    feature_authority_digest: str
    geometry_digest: str
    method: str = "AUDITED_WEIGHTED_L1_WASSERSTEIN_GEOMETRY_V1"


def certify_weighted_l1_transport_geometry(*, feature_weights: Mapping[str, float], coordinate_lipschitz: Mapping[str, float], feature_authority_digest: str) -> WeightedL1TransportGeometry:
    """Certify an auditable continuous high-dimensional transport metric.

    c(x,y)=sum_i a_i |x_i-y_i| with a_i>0 is a metric. If an external proof or
    bound certifies |g(x)-g(y)| <= sum_i L_i |x_i-y_i|, then g is K-Lipschitz
    under c with K=max_i L_i/a_i. This K may be used in a Wasserstein penalty
    K*rho. The function validates geometry algebra; it does not learn feature
    semantics, scales, L_i, or rho from data.
    """
    if not feature_authority_digest.strip() or not feature_weights:
        raise ValueError("feature authority digest and non-empty weights required")
    if set(feature_weights) != set(coordinate_lipschitz):
        raise ValueError("weights and coordinate Lipschitz maps must share keys")
    names = tuple(sorted(feature_weights))
    weights = tuple(float(feature_weights[n]) for n in names)
    lips = tuple(float(coordinate_lipschitz[n]) for n in names)
    if any(not math.isfinite(w) or w <= 0.0 for w in weights):
        raise ValueError("feature weights must be finite and >0")
    if any(not math.isfinite(l) or l < 0.0 for l in lips):
        raise ValueError("coordinate Lipschitz constants must be finite and >=0")
    k = max((l/w for l,w in zip(lips,weights,strict=True)), default=0.0)
    payload = {"features": list(names), "weights": list(weights), "coordinate_lipschitz": list(lips), "feature_authority_digest": feature_authority_digest}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return WeightedL1TransportGeometry(names, weights, lips, k, feature_authority_digest, digest)


def weighted_l1_distance(x: Sequence[float], y: Sequence[float], geometry: WeightedL1TransportGeometry) -> float:
    if len(x) != len(y) or len(x) != len(geometry.feature_weights):
        raise ValueError("vectors must match geometry dimension")
    total = 0.0
    for a,b,w in zip(x,y,geometry.feature_weights,strict=True):
        a,b=float(a),float(b)
        if not math.isfinite(a) or not math.isfinite(b):
            raise ValueError("finite vector coordinates required")
        total += w*abs(a-b)
    return total
