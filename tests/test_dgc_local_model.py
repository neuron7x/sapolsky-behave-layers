from __future__ import annotations

import numpy as np

from experiments.cwc_flagship_route_01.core import EvalRow
from experiments.dgc_03_local_model.core import conformal_lower_offset, split_calibration


def _row(i: int) -> EvalRow:
    return EvalRow(
        case_id=f"case-{i}", family="PROSE" if i % 2 == 0 else "CODE", cohort="CALIBRATION",
        loss1=2.0 + i * 1e-3, loss2=1.9 + i * 1e-3,
        feature=tuple(float(i + j) for j in range(65)),
    )


def test_dgc03_split_is_deterministic_disjoint_and_complete() -> None:
    rows = [_row(i) for i in range(120)]
    fit1, bound1 = split_calibration(rows)
    fit2, bound2 = split_calibration(rows)
    assert [r.case_id for r in fit1] == [r.case_id for r in fit2]
    assert [r.case_id for r in bound1] == [r.case_id for r in bound2]
    assert set(r.case_id for r in fit1).isdisjoint(r.case_id for r in bound1)
    assert len(fit1) + len(bound1) == len(rows)


def test_dgc03_conformal_lower_offset_is_frozen_order_statistic() -> None:
    residuals = np.linspace(-1.0, 1.0, 99)
    got = conformal_lower_offset(residuals, alpha=0.10)
    ordered = sorted(float(x) for x in residuals)
    k = max(1, int(np.floor(0.10 * (len(ordered) + 1))))
    assert got == ordered[k - 1]
