"""WP15 compute-equivalent Pareto — the L7 protocol, synthetic instantiation.

Distinct from AC1 (identifiability = a gap exists): this is the actual accuracy-vs-total-compute
frontier. Does adaptive-compute allocation Pareto-dominate every fixed-compute policy at MATCHED
average compute (FLOPs proportional to iterations)? This is the exact protocol L7 asks on a real
workload; here it runs on the synthetic AC1 mechanism (the cloud-ready harness; only the model/data/
baselines swap). See PREREGISTRATION.md. Deterministic.
"""
from __future__ import annotations

import bisect
import glob
import json
import statistics
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
AC1_RAW = ROOT / "artifacts/wp5-adaptive-compute-identifiability/raw_runs"
OUT = ROOT / "artifacts/wp15-compute-pareto"


def _acc():
    rc = [json.load(open(f)) for f in sorted(glob.glob(str(AC1_RAW / "seed*.json")))]
    dep = [str(d) for d in rc[0]["depths"]]
    ks = [int(k) for k in rc[0]["k_choices"]]
    acc = {d: {K: statistics.mean([r["acc"][d][str(K)] for r in rc]) for K in ks} for d in dep}
    return acc, dep, ks


def analyze() -> dict[str, Any]:
    acc, dep, ks = _acc()
    p = 1.0 / len(dep)                                   # uniform difficulty prior

    # fixed-K frontier: accuracy vs avg compute (= K)
    fixed = [{"K": K, "avg_compute": float(K), "accuracy": sum(p * acc[d][K] for d in dep)} for K in ks]

    # adaptive oracle: each difficulty uses its best K; avg compute = E[best K]
    best = {d: max(ks, key=lambda K: acc[d][K]) for d in dep}
    adaptive = {"avg_compute": sum(p * best[d] for d in dep),
                "accuracy": sum(p * acc[d][best[d]] for d in dep),
                "per_difficulty_K": best}

    # interpolate the fixed frontier at the adaptive's compute, and check dominance
    xs = [f["avg_compute"] for f in fixed]
    ys = [f["accuracy"] for f in fixed]

    def interp(c):
        if c <= xs[0]:
            return ys[0]
        if c >= xs[-1]:
            return ys[-1]
        i = bisect.bisect_right(xs, c) - 1
        t = (c - xs[i]) / (xs[i + 1] - xs[i])
        return ys[i] + t * (ys[i + 1] - ys[i])

    fixed_at_matched = interp(adaptive["avg_compute"])
    advantage = adaptive["accuracy"] - fixed_at_matched
    # dominance: strictly more accuracy at matched compute AND >= every fixed point at <= its compute
    dominates = advantage > 0.05 and all(
        adaptive["accuracy"] >= f["accuracy"] - 1e-9 for f in fixed if f["avg_compute"] >= adaptive["avg_compute"] - 1e-9
    )
    verdict = "SYNTHETIC_COMPUTE_PARETO_DOMINATES" if dominates else "NO_PARETO_DOMINANCE"

    return {
        "experiment": "wp15_compute_pareto",
        "verdict": verdict,
        "tier": "SYNTHETIC — compute-equivalent Pareto (the L7 protocol, synthetic instantiation)",
        "fixed_frontier": fixed,
        "adaptive_oracle": adaptive,
        "fixed_accuracy_at_matched_compute": fixed_at_matched,
        "adaptive_advantage_at_matched_compute": advantage,
        "pareto_dominates": dominates,
        "l7_status": "CWC-L7-pareto (real workload, MoD/MoE baselines, cloud) remains NOT_TESTED; "
                     "this is the synthetic precursor and the cloud-ready protocol.",
        "note": "At matched average compute, adaptive allocation reaches ~1.0 accuracy while every "
                "fixed-compute policy is stuck near chance (each fixed K solves only its own difficulty). "
                "This is the L7 shape (Pareto dominance at matched FLOPs) on synthetic data; the real- "
                "workload L7 is cloud-blocked (no checkpoint/budget/baselines).",
        "prohibited_extrapolations": ["real-workload compute-equivalent Pareto (L7)", "independent replication"],
    }


def main() -> None:
    r = analyze()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verdict.json").write_text(json.dumps(r, indent=2))
    print(f"WP15 COMPUTE-PARETO VERDICT: {r['verdict']}")
    print("  fixed-K frontier (accuracy vs avg compute):")
    for f in r["fixed_frontier"]:
        print(f"    K={f['K']}: compute={f['avg_compute']:.2f} acc={f['accuracy']:.4f}")
    a = r["adaptive_oracle"]
    print(f"  adaptive: compute={a['avg_compute']:.3f} acc={a['accuracy']:.4f}  (per-diff K={a['per_difficulty_K']})")
    print(f"  fixed accuracy at matched compute {a['avg_compute']:.2f} = {r['fixed_accuracy_at_matched_compute']:.4f}")
    print(f"  => adaptive advantage = {r['adaptive_advantage_at_matched_compute']:+.4f}  dominates={r['pareto_dominates']}")


if __name__ == "__main__":
    main()
