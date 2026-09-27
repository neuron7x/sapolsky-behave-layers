from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True, slots=True)
class ConformalRiskControlResult:
    selected_index: int
    selected_threshold: float
    calibration_mean_risk: float
    corrected_empirical_risk: float
    risk_limit: float
    loss_upper_bound: float
    calibration_size: int
    method: str = "CONFORMAL_RISK_CONTROL_ICLR2024_FINITE_GRID_V1"


def conformal_risk_control(
    *,
    thresholds: Sequence[float],
    losses_by_example: Sequence[Sequence[float]],
    risk_limit: float,
    loss_upper_bound: float,
    monotonicity_certified: bool,
    terminal_safety_certified: bool,
) -> ConformalRiskControlResult:
    """Finite-grid conformal risk control for monotone bounded losses.

    Contract mirrors the monotone-loss theorem of Angelopoulos et al. (ICLR
    2024). Calibration and the next test loss-function must be exchangeable;
    thresholds are ordered from less to more conservative; each example's loss
    is non-increasing in threshold; losses are bounded above by B; and the most
    conservative threshold has loss <= risk_limit for every calibration row.

    Select the first threshold satisfying

        (sum_i L_i(lambda) + B) / (n + 1) <= risk_limit.

    Under the theorem's exchangeability conditions, the expected next-sample
    loss at the selected threshold is <= risk_limit. This implementation is a
    finite-grid specialization and does not claim conditional-risk control.
    """
    if not monotonicity_certified:
        raise ValueError("monotonicity requires external certification")
    if not terminal_safety_certified:
        raise ValueError("terminal safety requires external certification")
    if not thresholds or not losses_by_example:
        raise ValueError("non-empty thresholds and calibration losses required")
    grid = [float(x) for x in thresholds]
    if any(not math.isfinite(x) for x in grid):
        raise ValueError("thresholds must be finite")
    if any(b <= a for a, b in zip(grid, grid[1:])):
        raise ValueError("thresholds must be strictly increasing")
    alpha = float(risk_limit)
    B = float(loss_upper_bound)
    if not math.isfinite(alpha) or not 0.0 <= alpha <= B:
        raise ValueError("risk_limit must be in [0, loss_upper_bound]")
    if not math.isfinite(B) or B <= 0.0:
        raise ValueError("loss_upper_bound must be finite and > 0")

    rows: list[list[float]] = []
    for raw_row in losses_by_example:
        if len(raw_row) != len(grid):
            raise ValueError("one loss per threshold required")
        row = [float(x) for x in raw_row]
        if any(not math.isfinite(x) or x < 0.0 or x > B for x in row):
            raise ValueError("loss outside declared [0,B] support")
        if any(next_loss > loss + 1e-12 for loss, next_loss in zip(row, row[1:])):
            raise ValueError("loss must be non-increasing in threshold")
        if row[-1] > alpha + 1e-12:
            raise ValueError("most conservative threshold must satisfy per-row risk limit")
        rows.append(row)

    n = len(rows)
    for j, threshold in enumerate(grid):
        total = math.fsum(row[j] for row in rows)
        corrected = (total + B) / (n + 1)
        if corrected <= alpha + 1e-15:
            return ConformalRiskControlResult(
                selected_index=j,
                selected_threshold=threshold,
                calibration_mean_risk=total / n,
                corrected_empirical_risk=corrected,
                risk_limit=alpha,
                loss_upper_bound=B,
                calibration_size=n,
            )
    raise RuntimeError("no threshold satisfies conformal risk-control criterion")
