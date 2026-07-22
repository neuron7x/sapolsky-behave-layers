"""WP18 pilot analysis (Act G3/G5/G7): oracle gap, variance components, prospective MDE, c_route.

PILOT ONLY -- estimates the quantities the Act requires *before* approving a confirmatory study or
cloud spend. Raises no architecture claim. Frozen decision rule in PREREGISTRATION.md:
a workload passes G3 iff G_lo > c_route; if BOTH fail, architecture work stops.
"""
from __future__ import annotations

import glob
import json
import math
import statistics
from pathlib import Path
from typing import Any

from experiments.common.identifiability_inference import (
    gap_lower_confidence_bound_corrected,
    plugin_gap,
)

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "artifacts/wp18-real-workload-pilot"
RAW = DATA / "raw_runs"
AC1_RAW = ROOT / "artifacts/wp5-adaptive-compute-identifiability/raw_runs"
DELTA = 0.05
# WP17 measured the deployable encoder router at 0.0006 of one model forward (K=1). Expressed in
# the certificate's lambda units (cost per compute unit, normalised by max K) that is the price the
# adaptive arm must beat. Measured, not assumed -- see artifacts/wp17-metrology/verdict.json.
C_ROUTE = 0.0006
POWER_Z = 2.802          # z_{1-alpha/2} + z_{power} for alpha=0.05 (two-sided), power=0.80


def _cert(mats: list[list[list[float]]], sign: int, costs: list[int], lam: float) -> float:
    """Debiased lower confidence bound on the oracle gap from n replicate utility matrices."""
    n = len(mats)
    n_c, n_a = len(mats[0]), len(mats[0][0])
    km = max(costs)
    uhat, se = [], 0.0
    for ci in range(n_c):
        row = []
        for ai in range(n_a):
            vals = [sign * mats[s][ci][ai] - lam * costs[ai] / km for s in range(n)]
            row.append(sum(vals) / n)
            if n > 1:
                v = statistics.pvariance(vals) * n / (n - 1)
                se = max(se, math.sqrt(v) / math.sqrt(n))
        uhat.append(row)
    return gap_lower_confidence_bound_corrected(plugin_gap(uhat), se, n_c, n_a, DELTA)


def _runs(family: str) -> list[dict]:
    return [json.loads(Path(f).read_text())
            for f in sorted(glob.glob(str(RAW / f"seed*_{family}_*.json")))]


def _matrices(runs: list[dict]) -> tuple[list[list[list[float]]], list[float], list[float]]:
    """One utility matrix per (run, shard); also per-shard and per-seed gap samples for variance."""
    mats, per_shard_gap, per_seed_gap = [], [], []
    for r in runs:
        ks = [str(k) for k in r["k_choices"]]
        seed_gaps = []
        for sh in r["shards"]:
            m = [[-sh["loss"][b][k] for k in ks] for b in r["buckets"]]   # utility = -loss
            mats.append(m)
            g = plugin_gap(m)
            per_shard_gap.append(g)
            seed_gaps.append(g)
        if seed_gaps:
            per_seed_gap.append(statistics.mean(seed_gaps))
    return mats, per_shard_gap, per_seed_gap


def _prospective(gaps: list[float]) -> dict[str, Any]:
    """From pilot variance: MDE at the pilot's n, and n needed to detect the observed effect."""
    n = len(gaps)
    sd = statistics.pstdev(gaps) * math.sqrt(n / (n - 1)) if n > 1 else float("nan")
    mean = statistics.mean(gaps) if gaps else float("nan")
    mde_at_n = POWER_Z * sd / math.sqrt(n) if n > 1 else float("nan")
    needed = (math.ceil((POWER_Z * sd / abs(mean)) ** 2)
              if n > 1 and mean and not math.isnan(sd) and abs(mean) > 1e-12 else None)
    return {"n_units": n, "mean_plugin_gap": mean, "sd": sd,
            "mde_at_pilot_n": mde_at_n, "n_needed_for_observed_effect": needed,
            "note": "alpha=0.05 two-sided, power=0.80. Unit = (seed x eval-shard) replicate."}


def _surface_probe(runs: list[dict]) -> dict[str, Any]:
    """Leakage probe: can the ranking of K be predicted from the bucket LABEL alone, ignoring the
    measured losses? If the best-K is identical in every bucket, there is no context x resource
    interaction to exploit -- the honest null this pilot is testing."""
    best_by_bucket: dict[str, list[int]] = {}
    for r in runs:
        ks = [str(k) for k in r["k_choices"]]
        for sh in r["shards"]:
            for b in r["buckets"]:
                row = [sh["loss"][b][k] for k in ks]
                best_by_bucket.setdefault(b, []).append(int(ks[row.index(min(row))]))
    modal = {b: statistics.mode(v) for b, v in best_by_bucket.items()}
    return {"modal_best_K_per_bucket": modal,
            "all_buckets_share_one_best_K": len(set(modal.values())) == 1,
            "fraction_agreeing_with_modal": {
                b: sum(1 for x in v if x == modal[b]) / len(v) for b, v in best_by_bucket.items()}}


def analyze() -> dict[str, Any]:
    card = json.loads((DATA / "dataset_card.json").read_text())
    workloads: dict[str, Any] = {}
    for fam in ("prose", "code"):
        runs = _runs(fam)
        mats, shard_gaps, seed_gaps = _matrices(runs)
        costs = runs[0]["k_choices"]
        g_lo = {str(lam): _cert(mats, +1, costs, lam) for lam in (0.0, 0.3)}
        best_g = max(g_lo.values())
        workloads[fam] = {
            "n_cells": len(runs), "n_replicate_matrices": len(mats),
            "g_lo_by_lambda": g_lo,
            "best_g_lo": best_g,
            "c_route_measured_wp17": C_ROUTE,
            "passes_g3": best_g > C_ROUTE,
            "variance_between_shards": _prospective(shard_gaps),
            "variance_between_seeds": _prospective(seed_gaps),
            "surface_probe": _surface_probe(runs),
            "contamination_clean": card["workloads"][fam]["contamination_clean"],
        }

    # Mandatory positive control on the synthetic AC1 mechanism -- if this fails, nothing concludes.
    ac1 = [json.loads(Path(f).read_text()) for f in sorted(glob.glob(str(AC1_RAW / "seed*.json")))]
    dep = [str(d) for d in ac1[0]["depths"]]
    aks = [str(k) for k in ac1[0]["k_choices"]]
    pos = _cert([[[r["acc"][d][k] for k in aks] for d in dep] for r in ac1],
                +1, ac1[0]["k_choices"], 0.0)

    any_pass = any(w["passes_g3"] for w in workloads.values())
    if pos <= 0.0:
        verdict = "WP18_VOID"
    elif any_pass:
        verdict = "WP18_REAL_WORKLOAD_IDENTIFIABLE"
    else:
        verdict = "WP18_KILL_RULE_TRIGGERED_NO_REAL_IDENTIFIABILITY"
    return {
        "experiment": "wp18_real_workload_pilot",
        "verdict": verdict,
        "tier": "PILOT -- real-workload identifiability, small from-scratch models, no cloud",
        "class_ceiling": "PILOT: estimates gap/variance/MDE/c_route only. NO architecture claim; "
                         "cannot support L7.",
        "workloads": workloads,
        "positive_control_synthetic_ac1_g_lo": pos,
        "decision": {
            "rule": "a workload passes G3 iff G_lo > c_route (frozen in PREREGISTRATION.md); "
                    "if BOTH fail, architecture work stops and the negative is published",
            "c_route": C_ROUTE,
            "prose_passes": workloads["prose"]["passes_g3"],
            "code_passes": workloads["code"]["passes_g3"],
            "kill_rule_triggered": not any_pass,
        },
        "prohibited_extrapolations": [
            "real-workload compute-equivalent Pareto (L7)",
            "any architecture claim", "large-model or production behaviour",
            "generalisation beyond byte-level from-scratch models on these two corpora"],
    }


def main() -> None:
    r = analyze()
    (DATA / "verdict.json").write_text(json.dumps(r, indent=2) + "\n")
    print(f"WP18 VERDICT: {r['verdict']}")
    for fam, w in r["workloads"].items():
        print(f"  {fam:6s}: G_lo {w['g_lo_by_lambda']} best={w['best_g_lo']:+.4f} "
              f"vs c_route {w['c_route_measured_wp17']} -> passes_G3={w['passes_g3']}")
        v = w["variance_between_shards"]
        print(f"          shards n={v['n_units']} mean_gap={v['mean_plugin_gap']:+.4f} "
              f"sd={v['sd']:.4f} MDE@n={v['mde_at_pilot_n']:.4f} "
              f"n_needed={v['n_needed_for_observed_effect']}")
        print(f"          surface probe: modal best-K per bucket "
              f"{w['surface_probe']['modal_best_K_per_bucket']} "
              f"(single-K={w['surface_probe']['all_buckets_share_one_best_K']})")
    print(f"  positive control (synthetic AC1): G_lo={r['positive_control_synthetic_ac1_g_lo']:+.4f}")
    print(f"  KILL RULE triggered: {r['decision']['kill_rule_triggered']}")


if __name__ == "__main__":
    main()
