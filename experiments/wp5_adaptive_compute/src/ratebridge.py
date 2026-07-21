"""WP5-AC4 compute rate-function bridge.

Compares the learned compute-controller's realised value (committed AC3 recovery) against the
master rate function V*(I) on the compute utility. Confirms V* is a valid, high-info-tight ceiling
and documents the low-info committed-vs-RI gap. Compute-axis twin of L4i. See
PREREGISTRATION_RATEBRIDGE.md. Deterministic.
"""
from __future__ import annotations

import glob
import json
import math
import statistics
from pathlib import Path
from typing import Any

from experiments.common.value_of_information_rate import optimal_value_at_rate_ri, oracle_gap_value

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "artifacts/wp5-adaptive-compute-identifiability/raw_runs"
AC3 = ROOT / "artifacts/wp5-adaptive-compute-inferred/verdict.json"
OUT = ROOT / "artifacts/wp5-adaptive-compute-ratebridge"

LAMBDA = 0.5
EVAL_SEEDS = {4, 5, 6, 7}
HIGH_INFO_BITS = 1.0
SAT_FLOOR = 0.90
CEIL_TOL = 1e-6


def _utility():
    runs = [json.load(open(f)) for f in sorted(glob.glob(str(RAW / "seed*.json")))]
    depths = [str(d) for d in runs[0]["depths"]]
    ks = [str(k) for k in runs[0]["k_choices"]]
    kmax = max(int(k) for k in ks)
    u = [[statistics.mean([r["acc"][d][k] - LAMBDA * int(k) / kmax
                           for r in runs if r["seed"] in EVAL_SEEDS]) for k in ks] for d in depths]
    return u, [1.0 / len(depths)] * len(depths)


def analyze() -> dict[str, Any]:
    u, prior = _utility()
    gap = oracle_gap_value(u, prior)
    ac3 = json.loads(AC3.read_text())

    rows = []
    ceiling_ok = True
    min_high_info_sat = 1.0
    min_sat_all = 1.0
    for r in ac3["sweep"]:
        info_bits = r["info_bits"]
        v_star = optimal_value_at_rate_ri(u, info_bits * math.log(2.0), prior)
        v_gov = max(0.0, r["recovery_mean"]) * gap
        under = v_gov <= v_star + CEIL_TOL
        ceiling_ok = ceiling_ok and under
        sat = (v_gov / v_star) if v_star > 1e-9 else 1.0
        if v_star > 1e-9:
            min_sat_all = min(min_sat_all, sat)
            if info_bits >= HIGH_INFO_BITS:
                min_high_info_sat = min(min_high_info_sat, sat)
        rows.append({"flip_p": r["flip_p"], "info_bits": info_bits, "v_gov": v_gov,
                     "v_star": v_star, "saturation": sat, "under_ceiling": under})

    high_info_ok = min_high_info_sat >= SAT_FLOOR
    if not ceiling_ok:
        verdict = "AC4_CEILING_VIOLATED"
    elif high_info_ok:
        verdict = "AC4_RATE_BRIDGE_CONFIRMED"
    else:
        verdict = "AC4_CEILING_ONLY"

    return {
        "experiment": "wp5_adaptive_compute_ratebridge",
        "verdict": verdict,
        "tier": "SYNTHETIC — theory<->mechanism bridge on the compute mechanism",
        "oracle_gap": gap, "high_info_bits_threshold": HIGH_INFO_BITS,
        "curve": rows,
        "ceiling_holds": ceiling_ok,
        "min_high_info_saturation": min_high_info_sat,
        "min_saturation_all": min_sat_all,
        "note": "committed greedy controller: V* ceiling holds everywhere and is tight at high info; "
                "saturation falls at low info (committed != RI soft-routing, gap widens with contexts)",
        "prohibited_extrapolations": ["real-workload", "L7 compute-equivalent Pareto",
                                      "independent replication"],
    }


def main() -> None:
    r = analyze()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verdict.json").write_text(json.dumps(r, indent=2))
    print(f"WP5-AC4 RATE-BRIDGE VERDICT: {r['verdict']}")
    print(f"  gap={r['oracle_gap']:.4f}")
    print("  p      I(bits)  V_gov     V*(I)     sat     under")
    for row in r["curve"]:
        print(f"  {row['flip_p']:.3f}  {row['info_bits']:.3f}   {row['v_gov']:+.4f}   "
              f"{row['v_star']:+.4f}   {row['saturation']:.3f}   {row['under_ceiling']}")
    print(f"  ceiling_holds={r['ceiling_holds']}  min high-info sat={r['min_high_info_saturation']:.3f}  "
          f"min sat (all)={r['min_saturation_all']:.3f}")


if __name__ == "__main__":
    main()
