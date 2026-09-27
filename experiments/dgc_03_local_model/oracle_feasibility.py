from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np

from experiments.cwc_flagship_route_02 import core as r2

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts/dgc-03-local-model"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def oracle_quality_preserving_ceiling(gains: np.ndarray) -> dict[str, float | int]:
    """Upper-bound block-2 skip count under aggregate CE non-inferiority.

    `gain = loss1-loss2`. Skipping block 2 changes aggregate CE by +gain.
    Therefore quality non-inferiority vs fixed depth-2 requires the sum of
    skipped gains to be <= 0. With equal block-2 compute cost, the maximal
    number of skips is the longest ascending-gain prefix whose cumulative sum
    is <= 0. This oracle observes realized gains and has zero routing overhead,
    so no executable policy can beat its compute-saving ceiling under the same
    finite rows and binary {depth1, depth2} action set.
    """
    values = np.asarray(gains, dtype=float)
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("finite non-empty 1D gains required")
    ordered = np.sort(values)
    cumulative = np.cumsum(ordered)
    feasible = np.flatnonzero(cumulative <= 1e-12)
    skips = int(feasible[-1] + 1) if feasible.size else 0
    skipped_sum = float(cumulative[skips - 1]) if skips else 0.0
    n = int(values.size)
    f = r2.flop_contract()
    savings = (skips / n) * (f.block / f.fixed_depth2)
    return {
        "rows": n,
        "max_skips": skips,
        "max_skip_rate": skips / n,
        "skipped_gain_sum": skipped_sum,
        "delta_quality_vs_depth2": -skipped_sum / n,
        "max_logical_flop_savings_zero_route_overhead": savings,
    }


def run() -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema": "dgc03-oracle-feasibility/1",
        "authority": "FINITE_WORKLOAD_OMNISCIENT_UPPER_BOUND",
        "action_set": ["DEPTH_1_STOP", "DEPTH_2_CONTINUE"],
        "route_overhead_assumed": 0.0,
        "cohorts": {},
    }
    for cohort in ("PRIMARY", "REPLICATION"):
        gains: list[float] = []
        for seed in r2.SEEDS[cohort]:
            cp = r2.OUT / "checkpoints" / f"seed{seed}.pt"
            model = r2.load_model(cp, expected_seed=seed)
            for family in ("PROSE", "CODE"):
                gains.extend(row.gain for row in r2.evaluate_rows(model, family, cohort))
        result["cohorts"][cohort] = oracle_quality_preserving_ceiling(np.asarray(gains, dtype=float))

    result["thirty_percent_feasible"] = all(
        float(result["cohorts"][c]["max_logical_flop_savings_zero_route_overhead"]) >= 0.30
        for c in ("PRIMARY", "REPLICATION")
    )
    result["verdict"] = (
        "LOCAL_MODEL_30PCT_ORACLE_FEASIBLE"
        if result["thirty_percent_feasible"]
        else "LOCAL_MODEL_30PCT_ORACLE_INFEASIBLE"
    )
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "oracle_feasibility.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


if __name__ == "__main__":
    run()
