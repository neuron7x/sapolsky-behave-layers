from __future__ import annotations

import copy
import inspect
import tempfile
from pathlib import Path

import numpy as np

from . import core


def self_test() -> dict:
    killed = []

    # 1 target bytes cannot enter feature API: EvalRow feature is explicit and evaluate_rows builds it from h1.
    sig = inspect.signature(core.fit_ridge)
    killed.append(("fit_requires_calibration", "cohort" in sig.parameters))
    try:
        core.fit_ridge(np.zeros((2, 65)), np.zeros(2), cohort="PRIMARY")
        ok = False
    except core.ProtocolViolation:
        ok = True
    killed.append(("primary_fit_rejected", ok))

    # 2 window membership cannot accept a model seed.
    killed.append(("window_offsets_seed_independent", "seed" not in inspect.signature(core._window_offsets).parameters))

    # 3 route cost must be nonzero and charged even with zero continuation.
    f = core.flop_contract()
    killed.append(("router_nonzero", f.route > 0))
    killed.append(("router_charged_at_q0", core.dynamic_compute(0, 10) == f.fixed_depth1 + f.route))

    # 4 outside frontier must fail, never clamp.
    try:
        core.fixed_frontier_loss(2.0, 1.0, f.fixed_depth2 + 1)
        ok = False
    except core.ProtocolViolation:
        ok = True
    killed.append(("outside_frontier_rejected", ok))

    # 5 seed mutation is rejected.
    old = core.SEEDS
    try:
        core.SEEDS = {**old, "PRIMARY": (74201, 74202, 99999)}
        try:
            core.validate_seed_contract(); ok = False
        except core.ProtocolViolation:
            ok = True
    finally:
        core.SEEDS = old
    killed.append(("seed_drift_rejected", ok))

    # 6 replication cannot rescue primary.
    p = {"passed": False}; r = {"passed": True}
    killed.append(("replication_no_rescue", core.final_verdict(p, r) == "CWC_FLAGSHIP_ROUTE_01_NOT_SUPPORTED"))

    # 7 oracle can only be sanity comparator; final verdict has no oracle promotion branch.
    src = inspect.getsource(core.final_verdict)
    killed.append(("oracle_no_promotion_branch", "ORACLE" not in src))

    # 8 SHA mutation is detected on a temporary substitution of expected hash.
    name = next(iter(core.EXPECTED_SHA256))
    old_hash = core.EXPECTED_SHA256[name]
    try:
        core.EXPECTED_SHA256[name] = "0" * 64
        try:
            core.verify_data_hashes(); ok = False
        except core.ProtocolViolation:
            ok = True
    finally:
        core.EXPECTED_SHA256[name] = old_hash
    killed.append(("sha_drift_rejected", ok))

    # 9 matched top selector must produce exact count even with ties.
    m = core._select_top(np.ones(10), 4, [f"{i:02d}" for i in range(10)])
    killed.append(("matched_count_exact", int(m.sum()) == 4))

    # 10 candidate cannot fit a different feature dimension.
    try:
        core.fit_ridge(np.zeros((3, 64)), np.zeros(3), cohort="CALIBRATION"); ok = False
    except core.ProtocolViolation:
        ok = True
    killed.append(("feature_dimension_locked", ok))

    # 11 zero/invalid case count cannot enter compute accounting.
    try:
        core.dynamic_compute(0, 0); ok = False
    except core.ProtocolViolation:
        ok = True
    killed.append(("invalid_case_count_rejected", ok))

    # 12 fixed frontier may leave budget unused when depth2 is worse.
    budget = (f.fixed_depth1 + f.fixed_depth2) / 2
    killed.append(("dominated_depth2_not_forced", core.fixed_frontier_loss(1.0, 2.0, budget) == 1.0))

    failures = [name for name, ok in killed if not ok]
    return {"killed": sum(ok for _, ok in killed), "total": len(killed), "failures": failures,
            "passed": not failures, "attacks": [{"name": n, "killed": ok} for n, ok in killed]}


def main() -> None:
    r = self_test()
    print(f"CWC-FLAGSHIP-ROUTE-01 semantic gate: {r['killed']}/{r['total']} killed")
    for a in r["attacks"]:
        print(f"  {'KILLED' if a['killed'] else 'SURVIVED'} {a['name']}")
    raise SystemExit(0 if r["passed"] else 1)


if __name__ == "__main__":
    main()
