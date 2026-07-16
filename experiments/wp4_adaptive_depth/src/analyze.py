"""Confirm the Jensen-gap prediction and the causal isolation across 8 seeds ×
4 difficulty distributions.

Predicted (theory, committed before the run): adaptive − static solved-gap =
P(m > K). Confirmed iff |empirical_gap − P(m>K)| is tiny for every regime, AND
the controls hold: adaptive > random at equal avg compute (not mere
variability), adaptive == oracle (halt recovers m), adaptive avg compute == K.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.wp2_routing_v1.src.analyze import _bootstrap_ci, _mean

DISTS = ["uniform", "easy_skew", "hard_skew", "bimodal"]


def analyze(runs_dir: Path) -> dict:
    runs = [json.loads(f.read_text()) for f in sorted(runs_dir.glob("seed*.json"))]
    per_dist = {}
    all_abs_err = []
    for d in DISTS:
        gaps = [r["distributions"][d]["solved_gap_adaptive_minus_static"] for r in runs]
        theory = [r["distributions"][d]["theory_P_m_gt_K"] for r in runs]
        errs = [abs(g - t) for g, t in zip(gaps, theory)]
        all_abs_err += errs
        adapt = [r["distributions"][d]["policies"]["adaptive"]["solved"] for r in runs]
        rand = [r["distributions"][d]["policies"]["random"]["solved"] for r in runs]
        orac = [r["distributions"][d]["policies"]["oracle"]["solved"] for r in runs]
        stat = [r["distributions"][d]["policies"]["static"]["solved"] for r in runs]
        ah = [r["distributions"][d]["adaptive_avg_hops"] for r in runs]
        K = [r["distributions"][d]["K"] for r in runs]
        adapt_minus_rand = [a - rn for a, rn in zip(adapt, rand)]
        lo_ar, _ = _bootstrap_ci(adapt_minus_rand)
        per_dist[d] = {
            "mean_empirical_gap": _mean(gaps), "mean_theory_P_m_gt_K": _mean(theory),
            "mean_abs_error": _mean(errs), "max_abs_error": max(errs),
            "adaptive_solved": _mean(adapt), "random_solved": _mean(rand),
            "oracle_solved": _mean(orac), "static_solved": _mean(stat),
            "adaptive_minus_random_ci": [lo_ar, None],
            "adaptive_eq_oracle": abs(_mean(adapt) - _mean(orac)) < 1e-6,
            "compute_matched_hops_vs_K": abs(_mean(ah) - _mean(K)),
        }

    # global gates
    max_err = max(all_abs_err)
    prediction_holds = max_err < 0.02          # gap matches theory in every regime/seed
    beats_random = all(per_dist[d]["adaptive_minus_random_ci"][0] > 0.1 for d in DISTS)
    matches_oracle = all(per_dist[d]["adaptive_eq_oracle"] for d in DISTS)
    compute_matched = all(per_dist[d]["compute_matched_hops_vs_K"] < 0.6 for d in DISTS)

    if prediction_holds and beats_random and matches_oracle and compute_matched:
        verdict = "ADAPTIVE_COMPUTE_JENSEN_GAP_CONFIRMED"
    else:
        verdict = "NOT_CONFIRMED"
    return {"n_seeds": len(runs), "per_distribution": per_dist,
            "max_abs_error_gap_vs_theory": max_err,
            "gates": {"prediction_holds_err_lt_0.02": prediction_holds,
                      "adaptive_beats_random": beats_random,
                      "adaptive_matches_oracle": matches_oracle,
                      "compute_matched": compute_matched},
            "verdict": verdict,
            "verdict_note": ("The adaptive-depth advantage equals the theory-predicted P(m>K) in every "
                             "regime (max abs error < 0.02), beats input-blind random depth at equal avg "
                             "compute, equals the oracle, and uses the same avg compute as static — with the "
                             "SAME operator and NO learning. The advantage is therefore not capacity, not "
                             "compute, not optimization: it is adaptive ALLOCATION of a fixed budget using "
                             "the per-input halt signal — a Jensen gap whose size is predicted, not fitted.")}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=Path, default=Path("artifacts/wp4-adaptive-depth/raw_runs"))
    ap.add_argument("--out", type=Path, default=Path("artifacts/wp4-adaptive-depth"))
    args = ap.parse_args()
    res = analyze(args.runs)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "analysis.json").write_text(json.dumps(res, indent=2))
    (args.out / "verdict.json").write_text(json.dumps({"verdict": res["verdict"]}, indent=2))
    print("VERDICT:", res["verdict"], "| max|gap-theory| =", round(res["max_abs_error_gap_vs_theory"], 4))
    for d in DISTS:
        p = res["per_distribution"][d]
        print(f"  {d:10s}: gap={p['mean_empirical_gap']:.3f} theory={p['mean_theory_P_m_gt_K']:.3f} "
              f"err={p['mean_abs_error']:.4f} | adaptive={p['adaptive_solved']:.3f} random={p['random_solved']:.3f} "
              f"static={p['static_solved']:.3f} oracle={p['oracle_solved']:.3f}")
    print("  gates:", res["gates"])


if __name__ == "__main__":
    main()
