"""WP-R1 routability specification: does a closed-form condition predict the certificate's sign?

Derivation (not a fit): the corrected certificate is G_lo = Ghat - b(se,n_a) - 2*d(se,n_c,delta/2),
and BOTH correction terms are linear in se. For a fixed design they therefore collapse to a single
constant kappa read directly off the shipped implementation:

    routable  <=>  Ghat > c_route + kappa * se           (kappa ~ 4.9 for n_c=n_a=3, delta=0.05)

i.e. the oracle gap must exceed ~5 standard errors AND the measured route cost. This module derives
kappa, then tests the condition against EVERY certificate-bearing bundle frozen in the repository --
data recorded before this specification existed. See PREREGISTRATION.md: 100% or refuted.
"""
from __future__ import annotations

import glob
import json
import math
import statistics
from pathlib import Path
from typing import Any

from experiments.common.identifiability_inference import (
    deviation_bound,
    gap_lower_confidence_bound_corrected,
    oracle_bias_bound,
    plugin_gap,
)

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "artifacts/wpr1-routability-spec"
DELTA = 0.05
N_CTX = N_ACT = 3
C_ROUTE = 0.0006          # WP17 measurement


def derive_kappa() -> dict[str, Any]:
    """kappa = (b + 2d)/se, read off the implementation at several se; must be constant."""
    ratios = []
    for se in (1.0, 0.1, 0.01, 0.001):
        corr = oracle_bias_bound(se, N_ACT) + 2.0 * deviation_bound(se, N_CTX, DELTA / 2.0)
        ratios.append(corr / se)
    return {"kappa": ratios[0], "ratios_at_decreasing_se": ratios,
            "linear_in_se": max(ratios) - min(ratios) < 1e-9,
            "design": {"n_contexts": N_CTX, "n_actions": N_ACT, "delta": DELTA}}


def _stats(mats: list[list[list[float]]]) -> tuple[float, float]:
    """Plug-in gap of the mean matrix, and the worst-cell standard error -- exactly what the
    certificate consumes."""
    n = len(mats)
    uhat, se = [], 0.0
    for ci in range(len(mats[0])):
        row = []
        for ai in range(len(mats[0][0])):
            vals = [mats[s][ci][ai] for s in range(n)]
            row.append(sum(vals) / n)
            if n > 1:
                v = statistics.pvariance(vals) * n / (n - 1)
                se = max(se, math.sqrt(v) / math.sqrt(n))
        uhat.append(row)
    return plugin_gap(uhat), se


# ---------------------------------------------------------------- frozen test set
def _ac1() -> list[list[list[float]]]:
    runs = [json.loads(Path(f).read_text()) for f in
            sorted(glob.glob(str(ROOT / "artifacts/wp5-adaptive-compute-identifiability/raw_runs/seed*.json")))]
    dep = [str(d) for d in runs[0]["depths"]]
    ks = [str(k) for k in runs[0]["k_choices"]]
    return [[[r["acc"][d][k] for k in ks] for d in dep] for r in runs]


def _wp6_or_wp14(bundle: str) -> list[list[list[float]]]:
    runs = [json.loads(Path(f).read_text()) for f in
            sorted(glob.glob(str(ROOT / f"artifacts/{bundle}/raw_runs/seed*.json")))]
    bk = runs[0]["buckets"]
    ks = [str(k) for k in runs[0]["k_choices"]]
    return [[[-r["loss"][b][k] for k in ks] for b in bk] for r in runs]     # utility = -loss


def _wp18(family: str) -> list[list[list[float]]]:
    runs = [json.loads(Path(f).read_text()) for f in
            sorted(glob.glob(str(ROOT / f"artifacts/wp18-real-workload-pilot/raw_runs/seed*_{family}_*.json")))]
    mats = []
    for r in runs:
        ks = [str(k) for k in r["k_choices"]]
        for sh in r["shards"]:
            mats.append([[-sh["loss"][b][k] for k in ks] for b in r["buckets"]])
    return mats


def _wp19(family: str) -> list[list[list[float]]]:
    runs = [json.loads(Path(f).read_text()) for f in
            sorted(glob.glob(str(ROOT / f"artifacts/wp19-negative-robustness/raw_runs/{family}_L*.json")))]
    depths = sorted({r["depth"] for r in runs})
    seeds = sorted({r["seed"] for r in runs})
    buckets = runs[0]["buckets"]
    mats = []
    for sd in seeds:
        by_d = {r["depth"]: r for r in runs if r["seed"] == sd}
        if set(by_d) != set(depths):
            continue
        for si in range(len(by_d[depths[0]]["shards"])):
            mats.append([[-by_d[d]["shards"][si]["loss"][b] for d in depths] for b in buckets])
    return mats


TEST_SET = {
    "AC1-synthetic-positive": _ac1,
    "WP6-real-lm-unigram": lambda: _wp6_or_wp14("wp6-real-lm"),
    "WP14-real-lm-bigram": lambda: _wp6_or_wp14("wp14-real-lm-contextual"),
    "WP18-prose-tiedK": lambda: _wp18("prose"),
    "WP18-code-tiedK": lambda: _wp18("code"),
    "WP19-prose-untied-depth": lambda: _wp19("prose"),
    "WP19-code-untied-depth": lambda: _wp19("code"),
}


def boundary_sweep(n_points: int = 61) -> dict[str, Any]:
    """Probe the spec WHERE IT CAN FAIL: none of the frozen bundles sit near the threshold
    (negatives have G/se ~ 0, the positive ~665), so agreement there tests the functional form but
    not the threshold VALUE. This sweeps a real frozen dataset continuously across the boundary by
    shrinking its interaction term, and checks the spec predicts the exact flip point of the
    certificate -- a test the spec can lose.
    """
    base = _ac1()
    # decompose each matrix into (row means) + interaction, then shrink the interaction by alpha
    def shrink(m: list[list[float]], a: float) -> list[list[float]]:
        gm = sum(sum(r) for r in m) / (len(m) * len(m[0]))
        rows = [sum(r) / len(r) for r in m]
        cols = [sum(m[i][j] for i in range(len(m))) / len(m) for j in range(len(m[0]))]
        return [[rows[i] + cols[j] - gm + a * (m[i][j] - rows[i] - cols[j] + gm)
                 for j in range(len(m[0]))] for i in range(len(m))]

    # LOG-spaced alpha: a linear grid jumps straight past the transition (the first attempt put
    # ZERO points in the near-threshold band, i.e. it still did not test where the spec can fail).
    kappa = derive_kappa()["kappa"]
    alphas = [0.0] + [10 ** (-5 + 5 * i / (n_points - 2)) for i in range(n_points - 1)]
    pts, mismatches = [], 0
    for a in alphas:
        mats = [shrink(m, a) for m in base]
        gap, se = _stats(mats)
        predicted = gap > C_ROUTE + kappa * se
        actual = gap_lower_confidence_bound_corrected(gap, se, N_CTX, N_ACT, DELTA) > C_ROUTE
        if predicted != actual:
            mismatches += 1
        pts.append({"alpha": a, "gap_over_se": (gap / se if se else float("inf")),
                    "required_gap_over_se": (kappa + C_ROUTE / se if se else float("nan")),
                    "predicted": predicted, "certificate": actual, "agrees": predicted == actual})
    crossings = [j for j in range(1, len(pts)) if pts[j]["certificate"] != pts[j - 1]["certificate"]]
    near = [p for p in pts if 0.5 * kappa < p["gap_over_se"] < 2 * kappa]
    j = crossings[0] if crossings else None
    return {"n_points": n_points, "mismatches": mismatches,
            "certificate_sign_changes": len(crossings),
            "predicted_threshold_gap_over_se": (pts[j]["required_gap_over_se"] if j is not None else kappa),
            "kappa_only": kappa,
            "flip_bracket_gap_over_se": ([pts[j - 1]["gap_over_se"], pts[j]["gap_over_se"]]
                                         if j is not None else None),
            "resolution_note": ("the certificate's flip is bracketed by two grid points; the FULL "
                                "predicted threshold (kappa + c_route/se, NOT kappa alone) must lie "
                                "inside that bracket. Comparing against kappa alone was a reporting "
                                "error caught here and fixed -- the route-cost term is part of the "
                                "condition."),
            "flip_alpha": pts[crossings[0]]["alpha"] if crossings else None,
            "flip_gap_over_se": pts[crossings[0]]["gap_over_se"] if crossings else None,
            "n_points_near_threshold": len(near),
            "all_near_threshold_agree": all(p["agrees"] for p in near),
            "points": pts}


def analyze() -> dict[str, Any]:
    k = derive_kappa()
    kappa = k["kappa"]
    cases, mismatches = [], 0
    for name, load in TEST_SET.items():
        mats = load()
        gap, se = _stats(mats)
        predicted = gap > C_ROUTE + kappa * se           # the closed-form screen
        actual_glo = gap_lower_confidence_bound_corrected(gap, se, N_CTX, N_ACT, DELTA)
        actual = actual_glo > C_ROUTE                    # what the real certificate says
        ok = predicted == actual
        mismatches += 0 if ok else 1
        cases.append({"bundle": name, "n_replicates": len(mats), "plugin_gap": gap, "se": se,
                      "gap_over_se": (gap / se if se else float("inf")),
                      "required_gap_over_se": kappa + C_ROUTE / se if se else float("nan"),
                      "predicted_routable": predicted, "certificate_g_lo": actual_glo,
                      "certificate_routable": actual, "agrees": ok})
    # Budget requirement per bundle, machine-derived: n >= (kappa*sigma/(G-c_route))^2 where sigma
    # is the CELL standard deviation the certificate consumes (se*sqrt(n)) -- NOT the sd of the gap
    # statistic, which is ~150x smaller and would understate the requirement by ~4 orders.
    budget = []
    for c in cases:
        sigma = c["se"] * math.sqrt(c["n_replicates"])
        margin = c["plugin_gap"] - C_ROUTE
        need = ((kappa * sigma / margin) ** 2) if margin > 0 else None
        budget.append({"bundle": c["bundle"], "cell_sigma": sigma, "gap_minus_c_route": margin,
                       "n_replicates_now": c["n_replicates"],
                       "n_needed_for_certification": need,
                       "unreachable": need is None or need > 1e6})

    sweep = boundary_sweep()
    total_mismatch = mismatches + sweep["mismatches"]
    verdict = "SPEC_PREDICTS_CERTIFICATE" if total_mismatch == 0 else "SPEC_REFUTED"
    return {
        "experiment": "wpr1_routability_spec",
        "verdict": verdict,
        "tier": "SCREENING INSTRUMENT -- closed-form routability condition, tested out-of-sample "
                "on frozen evidence",
        "class_ceiling": "no mechanism claim; cannot unblock L7 or L8",
        "specification": "routable <=> plugin_gap > c_route + kappa * se",
        "kappa_derivation": k,
        "c_route_measured_wp17": C_ROUTE,
        "n_cases": len(cases), "mismatches": mismatches,
        "cases": cases,
        "budget_requirement": budget,
        "budget_note": ("sigma is the CELL sd the certificate consumes (se*sqrt(n)), not the sd of "
                        "the gap statistic; using the latter understates the requirement by ~4 "
                        "orders of magnitude. This was caught while checking the write-up."),
        "boundary_sweep": sweep,
        "boundary_sweep_note": (
            "The frozen bundles all sit far from the threshold (negatives G/se~0, positive ~665), "
            "so agreement there tests the functional form but not the threshold VALUE. The sweep "
            "shrinks a real frozen dataset's interaction continuously across the boundary and "
            "checks the spec predicts the certificate's exact flip point -- where it can lose."),
        "interpretation": (
            "The gap must exceed ~5 standard errors AND the measured route cost. Because se = "
            "sigma/sqrt(n), a workload with a small effect can only be certified by paying "
            "n >= (kappa*sigma/(G-c_route))^2 -- which is why the real workloads are unreachable, "
            "not merely unlucky."),
        "prohibited_extrapolations": [
            "any architecture claim", "L7", "L8",
            "kappa as a universal constant (it is design-specific)",
            "passing the screen implies routability (it only fails to exclude)"],
    }


def main() -> None:
    r = analyze()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verdict.json").write_text(json.dumps(r, indent=2) + "\n")
    print(f"WP-R1 VERDICT: {r['verdict']}  (kappa={r['kappa_derivation']['kappa']:.4f}, "
          f"linear_in_se={r['kappa_derivation']['linear_in_se']})")
    print(f"  {'bundle':<26} {'G/se':>10} {'need':>8}  pred  cert   G_lo")
    for c in r["cases"]:
        print(f"  {c['bundle']:<26} {c['gap_over_se']:>10.3f} {c['required_gap_over_se']:>8.3f}  "
              f"{str(c['predicted_routable']):<5} {str(c['certificate_routable']):<5} "
              f"{c['certificate_g_lo']:+.4f} {'OK' if c['agrees'] else 'MISMATCH'}")
    print(f"  mismatches on frozen bundles: {r['mismatches']}/{r['n_cases']}")
    print("  budget requirement (n needed to certify):")
    for b in r["budget_requirement"]:
        nn = "n/a (gap <= c_route)" if b["n_needed_for_certification"] is None else f"{b['n_needed_for_certification']:.3g}"
        print(f"    {b['bundle']:<26} now={b['n_replicates_now']:<5} needed={nn}")
    sw = r["boundary_sweep"]
    print(f"  BOUNDARY SWEEP: {sw['n_points']} points, mismatches={sw['mismatches']}, "
          f"certificate flips at alpha={sw['flip_alpha']} (G/se={sw['flip_gap_over_se']:.3f}), "
          f"{sw['n_points_near_threshold']} points near threshold all agree="
          f"{sw['all_near_threshold_agree']}")
    br = sw["flip_bracket_gap_over_se"]
    print(f"  flip bracketed by G/se in [{br[0]:.3f}, {br[1]:.3f}]; predicted threshold "
          f"kappa={sw['predicted_threshold_gap_over_se']:.3f} "
          f"{'INSIDE' if br[0] <= sw['predicted_threshold_gap_over_se'] <= br[1] else 'OUTSIDE'}")


if __name__ == "__main__":
    main()
