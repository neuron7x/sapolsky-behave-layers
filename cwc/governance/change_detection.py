from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class BoundedMeanChangeEProcess:
    n: int
    log_e_up: float
    log_e_down: float
    e_up: float
    e_down: float
    alpha: float
    baseline_mean: float
    tolerance: float
    alarm_up: bool
    alarm_down: bool
    lambda_schedule_digest: str
    method: str = "BOUNDED_CONDITIONAL_MEAN_TWO_SIDED_EPROCESS_V1"

    @property
    def alarm(self) -> bool:
        return self.alarm_up or self.alarm_down


def bounded_conditional_mean_change_eprocess(
    observations: Sequence[float], *, lower: float, upper: float,
    baseline_mean: float, tolerance: float, alpha: float,
    lambdas: Sequence[float], predictable_lambda_attested: bool,
) -> BoundedMeanChangeEProcess:
    """Anytime-valid two-sided conditional-mean departure detector.

    Under the no-upward-change null, E[X_t|F_{t-1}] <= baseline+tolerance;
    under the no-downward-change null, E[X_t|F_{t-1}] >= baseline-tolerance.
    For bounded observations and predictable lambda_t >= 0, Hoeffding's lemma
    yields one-sided e-processes. Bonferroni allocation alpha/2 per side gives an
    anytime-valid two-sided alarm. Dependence is allowed through the filtration;
    predictability of lambda_t and the conditional-mean null are external
    obligations. No alarm is NOT a stationarity certificate.
    """
    if not predictable_lambda_attested:
        raise ValueError("predictable lambda schedule attestation required")
    if not observations or len(observations) != len(lambdas):
        raise ValueError("non-empty observations and one lambda per observation required")
    lower, upper = float(lower), float(upper)
    baseline, tol, alpha = float(baseline_mean), float(tolerance), float(alpha)
    if not all(math.isfinite(v) for v in (lower, upper, baseline, tol, alpha)) or upper <= lower:
        raise ValueError("finite lower < upper and finite parameters required")
    if not lower <= baseline <= upper or tol < 0.0 or not 0.0 < alpha < 1.0:
        raise ValueError("invalid baseline/tolerance/alpha")
    if baseline - tol < lower - 1e-12 or baseline + tol > upper + 1e-12:
        raise ValueError("tolerance band must lie inside observation support")

    width = upper - lower
    z0 = (baseline - lower) / width
    tol_norm = tol / width
    up_null = z0 + tol_norm
    down_null_for_one_minus_z = 1.0 - (z0 - tol_norm)
    log_up = 0.0
    log_down = 0.0
    lambda_values: list[float] = []
    for raw_x, raw_lam in zip(observations, lambdas, strict=True):
        x, lam = float(raw_x), float(raw_lam)
        if not math.isfinite(x) or x < lower or x > upper:
            raise ValueError("observation outside declared support")
        if not math.isfinite(lam) or lam < 0.0:
            raise ValueError("lambdas must be finite and >= 0")
        z = (x - lower) / width
        log_up += lam * (z - up_null) - lam * lam / 8.0
        log_down += lam * ((1.0 - z) - down_null_for_one_minus_z) - lam * lam / 8.0
        lambda_values.append(lam)

    e_up = math.exp(min(log_up, 700.0))
    e_down = math.exp(min(log_down, 700.0))
    threshold = 2.0 / alpha
    schedule_digest = hashlib.sha256(
        json.dumps(lambda_values, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return BoundedMeanChangeEProcess(
        n=len(observations), log_e_up=log_up, log_e_down=log_down,
        e_up=e_up, e_down=e_down, alpha=alpha, baseline_mean=baseline,
        tolerance=tol, alarm_up=e_up >= threshold, alarm_down=e_down >= threshold,
        lambda_schedule_digest=schedule_digest,
    )
