"""Phase H — paired statistics + causal/Pareto verdict from raw run JSONs.

Reads artifacts/wp2-routing-v1/raw_runs/<config>/seed*.json, computes per-config
per-seed best_query_ce, paired deltas learned−{random,frozen,fixed}, bootstrap
95% CIs, and emits the Act §11/§16 verdict. Deterministic bootstrap (fixed
seed via index hashing — no Math.random equivalent needed).

Usage: PYTHONPATH=. python experiments/wp2_routing_v1/src/analyze.py \
    --runs artifacts/wp2-routing-v1/raw_runs --out artifacts/wp2-routing-v1/statistics
"""
from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

CONFIGS = ["dense", "random", "frozen", "learned", "fixed_depth"]


def _load(runs: Path) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for c in CONFIGS:
        d = runs / c
        out[c] = sorted(
            (json.loads(f.read_text()) for f in d.glob("seed*.json")),
            key=lambda r: r["seed"],
        ) if d.exists() else []
    return out


def _bootstrap_ci(deltas: list[float], iters: int = 10000, seed: int = 12345):
    if not deltas:
        return (None, None)
    n = len(deltas)
    rnd = random.Random(seed)
    means = []
    for _ in range(iters):
        s = sum(deltas[rnd.randrange(n)] for _ in range(n))
        means.append(s / n)
    means.sort()
    lo = means[int(0.025 * iters)]
    hi = means[min(int(0.975 * iters), iters - 1)]
    return (lo, hi)


def _mean(xs):
    return sum(xs) / len(xs) if xs else None


def analyze(runs: Path) -> dict:
    data = _load(runs)
    per_config = {}
    for c in CONFIGS:
        ces = [r["best_query_ce"] for r in data[c]]
        per_config[c] = {
            "seeds": [r["seed"] for r in data[c]],
            "best_query_ce": ces,
            "mean": _mean(ces),
            "median": sorted(ces)[len(ces) // 2] if ces else None,
            "n": len(ces),
            "active_blocks": data[c][0]["active_blocks"] if data[c] else None,
            "active_inference_flops": data[c][0]["active_inference_flops"] if data[c] else None,
            "controller_flops": data[c][0]["controller_flops"] if data[c] else None,
            "e2e_latency_ms": _mean([r["e2e_latency_ms_per_256batch"] for r in data[c]]),
            "peak_vram": data[c][0]["peak_vram_allocated_bytes"] if data[c] else None,
        }

    # paired deltas: learned − control, matched by seed (lower CE is better, so
    # a NEGATIVE delta means learned is better)
    def paired(a: str, b: str):
        ra = {r["seed"]: r["best_query_ce"] for r in data[a]}
        rb = {r["seed"]: r["best_query_ce"] for r in data[b]}
        seeds = sorted(set(ra) & set(rb))
        d = [ra[s] - rb[s] for s in seeds]
        lo, hi = _bootstrap_ci(d) if d else (None, None)
        return {
            "seeds": seeds, "deltas_learned_minus_control": d, "mean_delta": _mean(d),
            "ci95": [lo, hi],
            "learned_better": (hi is not None and hi < 0),   # entire CI below 0
            "indistinguishable": (lo is not None and lo <= 0 <= hi),
        }

    comparisons = {
        "learned_vs_random": paired("learned", "random"),
        "learned_vs_frozen": paired("learned", "frozen"),
        "learned_vs_fixed_depth": paired("learned", "fixed_depth"),
        "learned_vs_dense": paired("learned", "dense"),
    }

    # compute parity among K-configs (Act F1)
    kcfgs = ["random", "frozen", "learned", "fixed_depth"]
    flops = [per_config[c]["active_inference_flops"] for c in kcfgs if per_config[c]["active_inference_flops"]]
    parity_ok = None
    if len(flops) == len(kcfgs):
        parity_ok = (max(flops) - min(flops)) / max(flops) <= 0.01

    # routing collapse check (learned): utilization spread across layers
    collapse = None
    if data["learned"]:
        util = data["learned"][0]["final_eval"]["per_layer_utilization"]
        # collapse if all sequences pick the same K blocks (utilization ∈ {0,1})
        collapse = all(u < 1e-6 or u > 0.999 for u in util)

    # budget violations — only the K-budget configs are constrained; dense
    # (E0) legitimately runs all L blocks and is the quality ceiling, not a
    # budget violation.
    k_budget_configs = ["random", "frozen", "learned", "fixed_depth"]
    viols = sum(
        r["final_eval"]["budget_violations"] for c in k_budget_configs for r in data[c]
        if r.get("final_eval")
    )

    # Verdict (Act H3)
    lr = comparisons["learned_vs_random"]
    lf = comparisons["learned_vs_frozen"]
    n_seeds = per_config["learned"]["n"]
    if n_seeds == 0 or any(per_config[c]["n"] == 0 for c in CONFIGS) or viols > 0:
        verdict = "MEASUREMENT_INVALID"
    elif parity_ok is False:
        verdict = "COMPUTE_MISMATCH"
    elif collapse:
        verdict = "ROUTER_COLLAPSE"
    elif lr["learned_better"] and lf["learned_better"]:
        verdict = "ROUTING_SUPPORTED" if n_seeds >= 5 else "ROUTING_SUPPORTED_PILOT"
    else:
        verdict = "ROUTING_NOT_SUPPORTED"
    if n_seeds < 5 and verdict.startswith("ROUTING") and "PILOT" not in verdict:
        verdict = "PILOT_ONLY:" + verdict

    return {
        "per_config": per_config,
        "comparisons": comparisons,
        "compute_parity_within_1pct": parity_ok,
        "router_collapse": collapse,
        "budget_violations_total": viols,
        "n_seeds": n_seeds,
        "verdict": verdict,
        "verdict_note": (
            "lower query_ce is better; learned_better = entire paired 95% CI of "
            "(learned − control) below 0. NULL (indistinguishable) is a valid "
            "negative completion per Act §17."
        ),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=Path, default=Path("artifacts/wp2-routing-v1/raw_runs"))
    ap.add_argument("--out", type=Path, default=Path("artifacts/wp2-routing-v1/statistics"))
    args = ap.parse_args()
    res = analyze(args.runs)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "analysis.json").write_text(json.dumps(res, indent=2))
    print("VERDICT:", res["verdict"])
    for c in CONFIGS:
        pc = res["per_config"][c]
        print(f"  {c:12s} n={pc['n']} mean_query_ce={pc['mean']} active={pc['active_blocks']}")
    for name, cmp in res["comparisons"].items():
        print(f"  {name}: mean_delta={cmp['mean_delta']} ci95={cmp['ci95']} better={cmp['learned_better']}")


if __name__ == "__main__":
    main()
