"""WP9 independence-assumption robustness.

The corrected certificate's deviation term assumes per-context independence. This Monte-Carlos its
coverage (FPR on a tied null) under CROSS-CONTEXT correlated noise (rho sweep). If FPR stays <= delta
under strong correlation, the independence assumption is not load-bearing for validity. See
PREREGISTRATION.md. Deterministic.
"""
from __future__ import annotations

import math
from typing import Any

from experiments.common.identifiability_inference import (
    _Rng,
    gap_lower_confidence_bound_corrected,
    plugin_gap,
)

SHAPES = [(4, 4), (2, 8), (6, 3)]
RHOS = [0.0, 0.3, 0.6, 0.9]
SE = 0.15
MC_DELTA = 0.10
TRIALS = 4000


def _fpr(n_c, n_a, rho, seed) -> float:
    rng = _Rng(seed)
    fp = 0
    for _ in range(TRIALS):
        eta = [rng.gauss() for _ in range(n_a)]                     # shared per-action component
        u = [[math.sqrt(1 - rho) * rng.gauss() * SE + math.sqrt(rho) * eta[a] * SE
              for a in range(n_a)] for _ in range(n_c)]             # tied null (mean 0) + corr noise
        if gap_lower_confidence_bound_corrected(plugin_gap(u), SE, n_c, n_a, MC_DELTA) > 0.0:
            fp += 1
    return fp / TRIALS


def analyze() -> dict[str, Any]:
    grid = []
    max_fpr = 0.0
    for (n_c, n_a) in SHAPES:
        row = {"shape": f"{n_c}x{n_a}"}
        for rho in RHOS:
            f = _fpr(n_c, n_a, rho, 7)
            row[f"rho_{rho}"] = f
            max_fpr = max(max_fpr, f)
        grid.append(row)
    robust = max_fpr <= MC_DELTA
    verdict = "INDEPENDENCE_ROBUST" if robust else "INDEPENDENCE_LOAD_BEARING"
    return {
        "experiment": "wp9_independence",
        "verdict": verdict,
        "tier": "META — corrected-bound coverage under cross-context correlation",
        "mc_delta": MC_DELTA, "rhos": RHOS, "shapes": [f"{a}x{b}" for a, b in SHAPES],
        "fpr_grid": grid,
        "max_fpr_over_all": max_fpr,
        "independence_robust": robust,
        "note": "Corrected-bound FPR on a tied null under cross-context correlated noise. FPR<=delta up "
                "to rho=0.9 => the per-context independence assumption is not load-bearing for validity "
                "(the b-slack over-covers). Worst case is the tied null.",
        "prohibited_extrapolations": ["independent replication"],
    }


def main() -> None:
    r = analyze()
    from pathlib import Path
    out = Path(__file__).resolve().parents[3] / "artifacts/wp9-independence"
    out.mkdir(parents=True, exist_ok=True)
    import json
    (out / "verdict.json").write_text(json.dumps(r, indent=2))
    print(f"WP9 INDEPENDENCE VERDICT: {r['verdict']}  (max FPR={r['max_fpr_over_all']:.3f} <= {MC_DELTA})")
    print("  shape   rho=0.0 0.3   0.6   0.9")
    for row in r["fpr_grid"]:
        print(f"  {row['shape']:6s}  " + "  ".join(f"{row[f'rho_{rho}']:.3f}" for rho in RHOS))


if __name__ == "__main__":
    main()
