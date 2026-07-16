"""Phase H for WP-2 v1.1 — paired stats + adaptivity signal (per-type routing
divergence) + verdict. Reuses the deterministic bootstrap from analyze.py.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.wp2_routing_v1.src.analyze import _bootstrap_ci, _mean

CONFIGS = ["dense", "random", "frozen", "learned", "fixed_depth"]


def _load(runs: Path):
    out = {}
    for c in CONFIGS:
        d = runs / c
        out[c] = sorted(
            (json.loads(f.read_text()) for f in d.glob("seed*.json")),
            key=lambda r: r["seed"],
        ) if d.exists() else []
    return out


def analyze(runs: Path) -> dict:
    data = _load(runs)
    per = {}
    for c in CONFIGS:
        ces = [r["best_answer_ce"] for r in data[c]]
        accs = [r["final_eval"]["acc_overall"] for r in data[c]]
        acc_r = [r["final_eval"]["acc_recall"] for r in data[c]]
        acc_c = [r["final_eval"]["acc_copy"] for r in data[c]]
        divs = [r["final_eval"]["routing_divergence_copy_vs_recall"] for r in data[c]]
        per[c] = {
            "n": len(ces), "seeds": [r["seed"] for r in data[c]],
            "answer_ce": ces, "mean_ce": _mean(ces),
            "mean_acc": _mean(accs), "mean_acc_recall": _mean(acc_r), "mean_acc_copy": _mean(acc_c),
            "mean_routing_divergence": _mean(divs),
            "active_blocks": data[c][0]["active_blocks"] if data[c] else None,
            "active_inference_flops": data[c][0]["active_inference_flops"] if data[c] else None,
        }

    def paired(a, b):
        ra = {r["seed"]: r["best_answer_ce"] for r in data[a]}
        rb = {r["seed"]: r["best_answer_ce"] for r in data[b]}
        seeds = sorted(set(ra) & set(rb))
        d = [ra[s] - rb[s] for s in seeds]
        lo, hi = _bootstrap_ci(d) if d else (None, None)
        return {"n": len(d), "mean_delta": _mean(d), "ci95": [lo, hi],
                "learned_better": (hi is not None and hi < 0),
                "indistinguishable": (lo is not None and lo <= 0 <= hi)}

    comps = {f"learned_vs_{c}": paired("learned", c) for c in ["random", "frozen", "fixed_depth", "dense"]}

    # adaptivity (H2'): learned per-type routing divergence vs frozen/fixed
    learned_div = per["learned"]["mean_routing_divergence"]
    static_div = _mean([per["frozen"]["mean_routing_divergence"], per["fixed_depth"]["mean_routing_divergence"]])
    adaptive = learned_div is not None and learned_div > 0.1  # meaningfully routes by type

    # parity
    kc = ["random", "frozen", "learned", "fixed_depth"]
    fl = [per[c]["active_inference_flops"] for c in kc if per[c]["active_inference_flops"]]
    parity_ok = (max(fl) - min(fl)) / max(fl) <= 0.01 if len(fl) == len(kc) else None

    viols = sum(r["final_eval"]["budget_violations"] for c in kc for r in data[c] if r.get("final_eval"))

    n_seeds = per["learned"]["n"]
    beats_all_static = all(comps[f"learned_vs_{c}"]["learned_better"] for c in ["random", "frozen", "fixed_depth"])
    if n_seeds == 0 or any(per[c]["n"] == 0 for c in CONFIGS) or viols > 0:
        verdict = "MEASUREMENT_INVALID"
    elif parity_ok is False:
        verdict = "COMPUTE_MISMATCH"
    elif beats_all_static and adaptive:
        verdict = "ROUTING_SUPPORTED" if n_seeds >= 5 else "ROUTING_SUPPORTED_PILOT"
    elif not adaptive:
        verdict = "ROUTING_NOT_SUPPORTED_COLLAPSE"
    else:
        verdict = "ROUTING_NOT_SUPPORTED"

    return {"per_config": per, "comparisons": comps,
            "adaptivity": {"learned_routing_divergence": learned_div, "static_divergence": static_div,
                           "learned_is_adaptive": adaptive},
            "compute_parity_within_1pct": parity_ok, "budget_violations": viols,
            "n_seeds": n_seeds, "verdict": verdict}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=Path, default=Path("artifacts/wp2-routing-v1_1/raw_runs"))
    ap.add_argument("--out", type=Path, default=Path("artifacts/wp2-routing-v1_1/statistics"))
    args = ap.parse_args()
    res = analyze(args.runs)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "analysis.json").write_text(json.dumps(res, indent=2))
    print("VERDICT:", res["verdict"])
    for c in CONFIGS:
        p = res["per_config"][c]
        print(f"  {c:12s} n={p['n']} ce={p['mean_ce']} acc={p['mean_acc']} "
              f"(R={p['mean_acc_recall']} C={p['mean_acc_copy']}) route_div={p['mean_routing_divergence']}")
    print("  adaptivity:", res["adaptivity"])
    for k, v in res["comparisons"].items():
        print(f"  {k}: Δ={v['mean_delta']} ci={v['ci95']} better={v['learned_better']}")


if __name__ == "__main__":
    main()
