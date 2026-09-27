from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Mapping, Sequence


def _digest_target(target: Mapping[str, float]) -> str:
    payload = [(str(k), float(target[k])) for k in sorted(target)]
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class AdaptiveImportanceSample:
    """One adaptively selected observation with a predictable chosen propensity."""

    item_id: str
    value: float
    selection_probability: float

    def __post_init__(self) -> None:
        if not self.item_id.strip():
            raise ValueError("item_id required")
        value = float(self.value)
        propensity = float(self.selection_probability)
        if not math.isfinite(value):
            raise ValueError("value must be finite")
        if not math.isfinite(propensity) or not 0.0 < propensity <= 1.0:
            raise ValueError("selection_probability must be in (0,1]")
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "selection_probability", propensity)


@dataclass(frozen=True, slots=True)
class AdaptiveMeanEProcess:
    n: int
    e_value: float
    log_e_value: float
    alpha: float
    lower_confidence_bound: float
    observation_lower: float
    observation_upper: float
    max_importance_weight: float
    target_distribution_digest: str
    rejected_null_mean: float | None
    method: str = "ADAPTIVE_IPW_HOEFFDING_EPROCESS_V2"

    @property
    def rejects(self) -> bool:
        return self.e_value >= 1.0 / self.alpha


def adaptive_importance_mean_eprocess(
    samples: Sequence[AdaptiveImportanceSample],
    *,
    target_distribution: Mapping[str, float],
    lower: float,
    upper: float,
    alpha: float,
    lambdas: Sequence[float],
    max_importance_weight: float,
    null_mean: float | None = None,
) -> AdaptiveMeanEProcess:
    """Anytime-valid one-sided evidence under predictable adaptive sampling.

    Contract. A single target distribution q is frozen before sampling. At time
    t the sampler chooses I_t with propensity pi_t(I_t)>0 that is fixed before
    observing the outcome. Observations are in [lower,upper], q/pi is bounded,
    and the importance-weighted observation is conditionally unbiased for one
    fixed target mean mu. For predictable lambda_t>=0, Hoeffding's lemma makes

      prod exp(lambda_t*(Z_t-m_norm)-lambda_t^2*w_max^2/8)

    a non-negative supermartingale under H0: mu<=m. Ville's inequality then
    controls crossing probability at arbitrary stopping times.

    The function verifies q is one normalized frozen distribution. Chosen
    propensities still require external telemetry authority; arbitrary adaptive
    search with outcome-dependent/unknown propensities remains unsupported.
    """
    lower = float(lower)
    upper = float(upper)
    alpha = float(alpha)
    w_max = float(max_importance_weight)
    if not math.isfinite(lower) or not math.isfinite(upper) or upper <= lower:
        raise ValueError("finite lower < upper required")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0,1)")
    if not math.isfinite(w_max) or w_max < 1.0:
        raise ValueError("max_importance_weight must be finite and >= 1")
    if not samples or len(samples) != len(lambdas):
        raise ValueError("non-empty samples and one lambda per sample required")
    if not target_distribution:
        raise ValueError("frozen target_distribution required")

    target = {str(k): float(v) for k, v in target_distribution.items()}
    if any(not k.strip() for k in target):
        raise ValueError("target item ids must be non-empty")
    if any(not math.isfinite(v) or v < 0.0 or v > 1.0 for v in target.values()):
        raise ValueError("target probabilities must be in [0,1]")
    if not math.isclose(math.fsum(target.values()), 1.0, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError("target_distribution must sum to 1")

    width = upper - lower
    weighted_sum = 0.0
    lambda_sum = 0.0
    penalty = 0.0
    for sample, raw_lambda in zip(samples, lambdas, strict=True):
        if sample.item_id not in target or target[sample.item_id] <= 0.0:
            raise ValueError("sample item absent from positive target support")
        lam = float(raw_lambda)
        if not math.isfinite(lam) or lam < 0.0:
            raise ValueError("lambdas must be finite and >= 0")
        if not lower <= sample.value <= upper:
            raise ValueError("sample outside declared support")
        importance_weight = target[sample.item_id] / sample.selection_probability
        if importance_weight > w_max + 1e-12:
            raise ValueError("importance weight exceeds declared maximum")
        normalized = (sample.value - lower) / width
        z = importance_weight * normalized
        weighted_sum += lam * z
        lambda_sum += lam
        penalty += (lam * lam * w_max * w_max) / 8.0

    if lambda_sum <= 0.0:
        raise ValueError("at least one lambda must be positive")
    log_threshold = math.log(1.0 / alpha)
    lcb_norm = (weighted_sum - penalty - log_threshold) / lambda_sum
    lcb = max(lower, min(upper, lower + width * lcb_norm))

    if null_mean is None:
        tested = None
        log_e = float("nan")
        e_value = float("nan")
    else:
        tested = float(null_mean)
        if not lower <= tested <= upper:
            raise ValueError("null_mean outside declared support")
        m_norm = (tested - lower) / width
        log_e = weighted_sum - lambda_sum * m_norm - penalty
        e_value = math.exp(min(log_e, 700.0))

    return AdaptiveMeanEProcess(
        n=len(samples),
        e_value=e_value,
        log_e_value=log_e,
        alpha=alpha,
        lower_confidence_bound=lcb,
        observation_lower=lower,
        observation_upper=upper,
        max_importance_weight=w_max,
        target_distribution_digest=_digest_target(target),
        rejected_null_mean=tested,
    )
