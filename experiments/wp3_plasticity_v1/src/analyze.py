"""Plasticity oracle-gap analysis + verdict (spec §11.4). Identifiable only if
the per-task oracle allocation beats the best FIXED allocation (LCB95 > 0)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.wp2_routing_v1.src.analyze import _bootstrap_ci, _mean


def analyze(runs_dir: Path) -> dict:
    runs = [json.loads(f.read_text()) for f in sorted(runs_dir.glob("seed*.json"))]
    if not runs:
        return {"present": False}
    tasks = list(runs[0]["tasks"].keys())
    allocs = list(runs[0]["tasks"][tasks[0]].keys())

    # per-seed oracle utility (per task max over allocations) and best-fixed
    # (one allocation, best mean over tasks)
    oracle_gaps = []
    per_task_best = {t: {} for t in tasks}
    for r in runs:
        oracle_mean = _mean([max(r["tasks"][t][a]["utility"] for a in allocs) for t in tasks])
        fixed_means = {a: _mean([r["tasks"][t][a]["utility"] for t in tasks]) for a in allocs}
        best_fixed = max(fixed_means.values())
        oracle_gaps.append(oracle_mean - best_fixed)
        for t in tasks:
            best_a = max(allocs, key=lambda a: r["tasks"][t][a]["utility"])
            per_task_best[t][best_a] = per_task_best[t].get(best_a, 0) + 1

    lo, hi = _bootstrap_ci(oracle_gaps)
    # mean utility table
    table = {t: {a: _mean([r["tasks"][t][a]["utility"] for r in runs]) for a in allocs} for t in tasks}
    new_acc = {t: {a: _mean([r["tasks"][t][a]["new_acc"] for r in runs]) for a in allocs} for t in tasks}
    retention = {t: {a: _mean([r["tasks"][t][a]["retention_drop"] for r in runs]) for a in allocs} for t in tasks}

    identifiable = bool(lo is not None and lo > 0 and _mean(oracle_gaps) >= 0.05)
    verdict = "ORACLE_GAP_SUPPORTED" if identifiable else "PLASTICITY_BENCHMARK_NOT_IDENTIFIABLE"
    return {"present": True, "n_seeds": len(runs), "tasks": tasks, "allocations": allocs,
            "mean_oracle_gap": _mean(oracle_gaps), "oracle_gap_ci95": [lo, hi],
            "per_task_best_allocation_counts": per_task_best,
            "mean_utility": table, "mean_new_acc": new_acc, "mean_retention_drop": retention,
            "registry_checksums": sorted({r["registry_checksum"] for r in runs}),
            "verdict": verdict,
            "verdict_note": ("Identifiable only if per-task oracle allocation beats the best FIXED "
                             "allocation (LCB95>0, gap>=0.05). If one group (e.g. attention) is best "
                             "for every task, adaptive per-group plasticity has no advantage over "
                             "always updating that group — governor training is not justified (§11.4).")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=Path, default=Path("artifacts/wp3-plasticity-v1/oracle-gap/raw_runs"))
    ap.add_argument("--out", type=Path, default=Path("artifacts/wp3-plasticity-v1/oracle-gap"))
    args = ap.parse_args()
    res = analyze(args.runs)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "analysis.json").write_text(json.dumps(res, indent=2))
    (args.out / "verdict.json").write_text(json.dumps({"verdict": res.get("verdict", "NOT_TESTED")}, indent=2))
    print("VERDICT:", res.get("verdict"))
    if res.get("present"):
        print(f"  oracle gap = {res['mean_oracle_gap']:.4f} CI={res['oracle_gap_ci95']}")
        for t in res["tasks"]:
            print(f"  {t}: " + " ".join(f"{a}={res['mean_utility'][t][a]:.3f}" for a in res["allocations"])
                  + f"  best_counts={res['per_task_best_allocation_counts'][t]}")


if __name__ == "__main__":
    main()
