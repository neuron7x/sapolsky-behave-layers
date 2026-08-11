from __future__ import annotations

import copy
import json
import math
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts/cwc-flagship-route-01"
TOL = 1e-10


class VerificationError(RuntimeError):
    pass


def _mean(xs: list[float]) -> float:
    if not xs:
        raise VerificationError("empty vector")
    return sum(xs) / len(xs)


def _policy_loss(decisions: list[dict[str, Any]], key: str) -> float:
    return _mean([float(d["loss2"] if d[key] else d["loss1"]) for d in decisions])


def _frontier(loss1: float, loss2: float, budget: float, c1: float, c2: float) -> float | None:
    if budget > c2 + 1e-9:
        return None
    if budget < c1 - 1e-9:
        raise VerificationError("budget below fixed depth1")
    if loss2 >= loss1:
        return loss1
    q = min(1.0, max(0.0, (budget - c1) / (c2 - c1)))
    return loss1 + q * (loss2 - loss1)


def verify_cell(cell: dict[str, Any], flops: dict[str, Any]) -> dict[str, Any]:
    ds = cell["decisions"]
    n = len(ds)
    if n != int(cell["n_cases"]):
        raise VerificationError("case-count drift")
    keys = {
        "DECISION_RELEVANT": "candidate_continue",
        "RANDOM_MATCHED": "random_continue",
        "HIDDEN_NORM_MATCHED": "hidden_norm_continue",
        "DIFFICULTY_MATCHED": "difficulty_continue",
        "ORACLE_MATCHED": "oracle_continue",
    }
    counts = {name: sum(bool(d[k]) for d in ds) for name, k in keys.items()}
    if len(set(counts.values())) != 1:
        raise VerificationError(f"matched-count drift: {counts}")
    k = counts["DECISION_RELEVANT"]
    if k != int(cell["n_continue"]):
        raise VerificationError("candidate count drift")
    q = k / n
    if not math.isclose(q, float(cell["continue_rate"]), rel_tol=0.0, abs_tol=TOL):
        raise VerificationError("continue-rate drift")

    c1 = float(flops["fixed_depth1"])
    c2 = float(flops["fixed_depth2"])
    block = float(flops["block"])
    route = float(flops["route"])
    compute = c1 + route + q * block
    if not math.isclose(compute, float(cell["logical_flops_per_window"]), rel_tol=0.0, abs_tol=1e-6):
        raise VerificationError("logical FLOP drift")

    l1 = _mean([float(d["loss1"]) for d in ds])
    l2 = _mean([float(d["loss2"]) for d in ds])
    if not math.isclose(l1, float(cell["fixed_depth1_loss"]), rel_tol=0.0, abs_tol=TOL):
        raise VerificationError("depth1 loss drift")
    if not math.isclose(l2, float(cell["fixed_depth2_loss"]), rel_tol=0.0, abs_tol=TOL):
        raise VerificationError("depth2 loss drift")

    losses = {name: _policy_loss(ds, key) for name, key in keys.items()}
    for name, value in losses.items():
        if not math.isclose(value, float(cell["losses"][name]), rel_tol=0.0, abs_tol=TOL):
            raise VerificationError(f"policy loss drift: {name}")

    frontier = _frontier(l1, l2, compute, c1, c2)
    stored_frontier = cell["fixed_frontier_loss"]
    if frontier is None:
        if stored_frontier is not None:
            raise VerificationError("outside-frontier drift")
        advantage = None
    else:
        if stored_frontier is None or not math.isclose(frontier, float(stored_frontier), rel_tol=0.0, abs_tol=TOL):
            raise VerificationError("frontier loss drift")
        advantage = frontier - losses["DECISION_RELEVANT"]
        if not math.isclose(advantage, float(cell["candidate_advantage_vs_fixed_frontier"]), rel_tol=0.0, abs_tol=TOL):
            raise VerificationError("frontier advantage drift")

    eps = 1e-12
    endpoints = {
        "within_fixed_frontier": frontier is not None,
        "beats_fixed_frontier": frontier is not None and losses["DECISION_RELEVANT"] < frontier - eps,
        "beats_random_matched": losses["DECISION_RELEVANT"] < losses["RANDOM_MATCHED"] - eps,
        "no_worse_hidden_norm": losses["DECISION_RELEVANT"] <= losses["HIDDEN_NORM_MATCHED"] + eps,
        "beats_difficulty_matched": losses["DECISION_RELEVANT"] < losses["DIFFICULTY_MATCHED"] - eps,
        "oracle_sanity": losses["ORACLE_MATCHED"] <= losses["DECISION_RELEVANT"] + eps,
        "matched_counts": len(set(counts.values())) == 1,
    }
    if endpoints != cell["endpoints"]:
        raise VerificationError(f"endpoint drift: recomputed={endpoints} stored={cell['endpoints']}")
    passed = all(endpoints.values())
    if passed != bool(cell["passed"]):
        raise VerificationError("cell verdict drift")
    return {"passed": passed, "advantage": advantage, "family": cell["family"], "seed": int(cell["seed"])}


def _cohort(cells: list[dict[str, Any]]) -> bool:
    return all(bool(c["passed"]) for c in cells)


def verify_bundle(bundle: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    results: dict[str, list[dict[str, Any]]] = {}
    for cohort in ("PRIMARY", "REPLICATION"):
        cells = bundle["cells"][cohort]
        results[cohort] = [verify_cell(c, policy["flops"]) for c in cells]
    primary_pass = _cohort(results["PRIMARY"])
    replication_pass = _cohort(results["REPLICATION"])
    expected = (
        "CWC_FLAGSHIP_ROUTE_01_NOT_SUPPORTED" if not primary_pass else
        "CWC_FLAGSHIP_ROUTE_01_PRIMARY_PASS_REPLICATION_FAIL" if not replication_pass else
        "CWC_FLAGSHIP_ROUTE_01_SUPPORTED_NARROW"
    )
    if bundle["verdict"] != expected:
        raise VerificationError(f"final verdict drift: {bundle['verdict']} != {expected}")
    return {
        "verdict": expected,
        "primary_cell_passes": sum(r["passed"] for r in results["PRIMARY"]),
        "primary_cells": len(results["PRIMARY"]),
        "replication_cell_passes": sum(r["passed"] for r in results["REPLICATION"]),
        "replication_cells": len(results["REPLICATION"]),
    }


def self_test(bundle: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    probes = []
    def kill(name: str, mutate) -> None:
        b = copy.deepcopy(bundle); p = copy.deepcopy(policy); mutate(b, p)
        try:
            verify_bundle(b, p)
        except VerificationError:
            probes.append((name, True)); return
        probes.append((name, False))

    kill("candidate_flag_flip", lambda b,p: b["cells"]["PRIMARY"][0]["decisions"][0].__setitem__("candidate_continue", True))
    kill("loss_drift", lambda b,p: b["cells"]["PRIMARY"][0]["losses"].__setitem__("DECISION_RELEVANT", 0.0))
    kill("flop_drift", lambda b,p: b["cells"]["PRIMARY"][0].__setitem__("logical_flops_per_window", 0.0))
    kill("endpoint_flip", lambda b,p: b["cells"]["PRIMARY"][0]["endpoints"].__setitem__("matched_counts", False))
    kill("verdict_promotion", lambda b,p: b.__setitem__("verdict", "CWC_FLAGSHIP_ROUTE_01_SUPPORTED_NARROW"))
    return {"passed": all(ok for _,ok in probes), "killed": sum(ok for _,ok in probes), "total": len(probes), "probes": probes}


def main() -> int:
    bundle = json.loads((OUT / "verdict.json").read_text())
    policy = json.loads((OUT / "CALIBRATION_POLICY.json").read_text())
    result = verify_bundle(bundle, policy)
    attacks = self_test(bundle, policy)
    print(f"CWC-FLAGSHIP-ROUTE-01 independent verify: {result}")
    print(f"mutation verifier: {attacks['killed']}/{attacks['total']} killed")
    return 0 if attacks["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
