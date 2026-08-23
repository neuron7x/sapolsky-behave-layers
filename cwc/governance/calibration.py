from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class SplitConformalLowerCalibrator:
    residual_quantile: float
    calibration_size: int
    alpha: float
    guaranteed_miscoverage_upper: float
    method: str = "ONE_SIDED_SPLIT_CONFORMAL_LOWER_V1"

    def lower_bound(self, prediction: float) -> float:
        prediction = float(prediction)
        if not math.isfinite(prediction):
            raise ValueError("prediction must be finite")
        return prediction + self.residual_quantile


def fit_split_conformal_lower(
    *,
    predictions: Sequence[float],
    outcomes: Sequence[float],
    alpha: float,
) -> SplitConformalLowerCalibrator:
    """Finite-sample one-sided lower prediction bound under exchangeability.

    For residual R=Y-f(X), choose the k-th smallest calibration residual with
    k=floor(alpha*(n+1)). Then, under exchangeability of calibration plus the
    next test residual and a frozen predictor, P(R_test < R_(k)) <= k/(n+1)
    <= alpha. k=0 yields an uninformative -infinity bound rather than inventing
    finite confidence from insufficient calibration data.
    """
    alpha = float(alpha)
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be in (0,1)")
    if not predictions or len(predictions) != len(outcomes):
        raise ValueError("equal non-empty predictions/outcomes required")
    residuals: list[float] = []
    for p, y in zip(predictions, outcomes, strict=True):
        p = float(p)
        y = float(y)
        if not math.isfinite(p) or not math.isfinite(y):
            raise ValueError("finite calibration values required")
        residuals.append(y - p)
    residuals.sort()
    n = len(residuals)
    k = math.floor(alpha * (n + 1))
    if k <= 0:
        quantile = float("-inf")
        miscoverage = 0.0
    else:
        quantile = residuals[k - 1]
        miscoverage = k / (n + 1)
    return SplitConformalLowerCalibrator(
        residual_quantile=quantile,
        calibration_size=n,
        alpha=alpha,
        guaranteed_miscoverage_upper=miscoverage,
    )
