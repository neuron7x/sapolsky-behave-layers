"""L4i rate-function bridge — does the plasticity governor realise V*(R)?

Compares the learned governor's realised value against the master value-of-information rate
function V*(I) on the real plasticity utility. Confirms V* is a valid ceiling and quantifies
how close the governor comes to the rational-inattention optimum. See PREREGISTRATION.md.
Deterministic.
"""
from __future__ import annotations

import glob
import json
import math
import statistics
from pathlib import Path
from typing import Any

from experiments.common.value_of_information_rate import oracle_gap_value, optimal_value_at_rate_ri

ROOT = Path(__file__).resolve().parents[3]
RAW = ROOT / "artifacts/wp3-plasticity-v2-confirmatory/raw_runs"
OUT = ROOT / "artifacts/wp3-plasticity-v11-ratebridge"

GROUPS = ["attn", "mlp", "head", "embed"]
TASKS = ["lexical", "relational"]
EVAL_SEEDS = set(range(13, 21))
FLIP_SWEEP = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5]
GOV_SLOPE = 2.146          # committed-routing slope from L4b (recovery = 1 - slope*p)
SATURATION_FLOOR = 0.90
CEIL_TOL = 1e-6


def _utility() -> list[list[float]]:
    runs = [json.load(open(f)) for f in sorted(glob.glob(str(RAW / "seed*.json")))]
    cost = {a: runs[0]["tasks"][TASKS[0]][a]["cost_params"] for a in GROUPS}
    km = max(cost.values())
    return [[statistics.mean([r["tasks"][t][a]["new_acc"] - cost[a] / km
                              for r in runs if r["seed"] in EVAL_SEEDS]) for a in GROUPS]
            for t in TASKS]


def _entropy2(p: float) -> float:
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


def analyze() -> dict[str, Any]:
    u = _utility()
    prior = [0.5, 0.5]
    gap = oracle_gap_value(u, prior)
    rows = []
    ceiling_ok = True
    min_saturation = 1.0
    for p in FLIP_SWEEP:
        info_bits = 1.0 - _entropy2(p)
        v_star = optimal_value_at_rate_ri(u, info_bits * math.log(2.0), prior)
        v_gov = max(0.0, (1.0 - GOV_SLOPE * p)) * gap
        under = v_gov <= v_star + CEIL_TOL
        ceiling_ok = ceiling_ok and under
        sat = (v_gov / v_star) if v_star > 1e-9 else 1.0
        if v_star > 1e-9:
            min_saturation = min(min_saturation, sat)
        rows.append({"flip_p": p, "info_bits": info_bits, "v_gov": v_gov, "v_star": v_star,
                     "under_ceiling": under, "saturation": sat})

    if not ceiling_ok:
        verdict = "L4I_CEILING_VIOLATED"
    elif min_saturation >= SATURATION_FLOOR:
        verdict = "L4I_BRIDGE_CONFIRMED"
    else:
        verdict = "L4I_CEILING_ONLY"

    return {
        "experiment": "wp3_plasticity_v11_ratebridge",
        "verdict": verdict,
        "tier": "SYNTHETIC — theory<->mechanism bridge (governor realises V*(R))",
        "utility": u, "oracle_gap": gap,
        "curve": rows,
        "ceiling_holds": ceiling_ok,
        "min_saturation": min_saturation,
        "saturation_floor": SATURATION_FLOOR,
        "prohibited_extrapolations": ["real-workload behavior", "L7 compute-equivalent Pareto",
                                      "energy or latency advantage", "independent replication"],
    }


def main() -> None:
    r = analyze()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verdict.json").write_text(json.dumps(r, indent=2))
    print(f"L4i RATE-BRIDGE VERDICT: {r['verdict']}")
    print(f"  gap={r['oracle_gap']:.4f}")
    print("  p     I(bits)  V_gov     V*(I)     sat    under")
    for row in r["curve"]:
        print(f"  {row['flip_p']:.1f}   {row['info_bits']:.3f}   {row['v_gov']:+.4f}   "
              f"{row['v_star']:+.4f}   {row['saturation']:.3f}  {row['under_ceiling']}")
    print(f"  ceiling_holds={r['ceiling_holds']}  min_saturation={r['min_saturation']:.3f}")


if __name__ == "__main__":
    main()
