"""Analyze the sealed-evidence VIA-V1 method validation.

There is deliberately no scientific VIA-V1 PASS state here.  Agreement with
already-frozen evidence validates the new causal software only; the WP18 kill rule
continues to block architecture ascension.
"""
from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Any

from cwc.causal.cate import oracle_gap
from experiments.common.identifiability_inference import (
    gap_lower_confidence_bound_corrected,
    plugin_gap,
)
from experiments.via_v1_causal_surface.nulls import permutation_gaps, structural_nulls

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts/via-v1-causal-surface"
DELTA = 0.05
PERMUTATIONS = 1000
PERMUTATION_SEED = 20260809
NULL_TOL = 1e-12
FROZEN_TOL = 1e-12


def cell_statistics(matrices: list[list[list[float]]]) -> tuple[list[list[float]], float]:
    """Mean utility matrix and conservative maximum cell standard error."""
    if not matrices or not matrices[0] or not matrices[0][0]:
        raise ValueError("matrices must be non-empty")
    n = len(matrices)
    n_c, n_a = len(matrices[0]), len(matrices[0][0])
    if any(len(m) != n_c or any(len(row) != n_a for row in m) for m in matrices):
        raise ValueError("replicate matrices must have identical shape")
    mean_matrix: list[list[float]] = []
    max_se = 0.0
    for c in range(n_c):
        row: list[float] = []
        for a in range(n_a):
            values = [float(matrices[s][c][a]) for s in range(n)]
            if any(not math.isfinite(v) for v in values):
                raise ValueError("matrix values must be finite")
            row.append(sum(values) / n)
            if n > 1:
                sample_var = statistics.pvariance(values) * n / (n - 1)
                max_se = max(max_se, math.sqrt(sample_var) / math.sqrt(n))
        mean_matrix.append(row)
    return mean_matrix, max_se


def _quantile(values: list[float], q: float) -> float:
    if not values or not 0.0 <= q <= 1.0:
        raise ValueError("invalid quantile request")
    ordered = sorted(values)
    pos = q * (len(ordered) - 1)
    lo, hi = math.floor(pos), math.ceil(pos)
    if lo == hi:
        return ordered[lo]
    weight = pos - lo
    return ordered[lo] * (1.0 - weight) + ordered[hi] * weight


def analyze_bundle(bundle: dict[str, Any], route_cost: float) -> dict[str, Any]:
    matrices = bundle["matrices"]
    mean_matrix, max_cell_se = cell_statistics(matrices)
    gap = float(plugin_gap(mean_matrix))
    n_c, n_a = len(mean_matrix), len(mean_matrix[0])
    g_lo = float(gap_lower_confidence_bound_corrected(gap, max_cell_se, n_c, n_a, DELTA))
    direct = float(oracle_gap(mean_matrix)["gap"])
    if not math.isclose(gap, direct, rel_tol=0.0, abs_tol=1e-12):
        raise AssertionError("causal oracle-gap implementation disagrees with existing certificate primitive")

    nulls = structural_nulls(mean_matrix)
    perm = permutation_gaps(matrices, n_permutations=PERMUTATIONS, seed=PERMUTATION_SEED)
    p_right = (1 + sum(v >= gap for v in perm)) / (len(perm) + 1)
    frozen = bundle.get("frozen_g_lo")
    frozen_matches = frozen is None or math.isclose(g_lo, float(frozen), rel_tol=0.0, abs_tol=FROZEN_TOL)
    return {
        "name": bundle["name"],
        "tier": bundle["tier"],
        "n_replicate_matrices": len(matrices),
        "n_contexts": n_c,
        "n_actions": n_a,
        "plugin_gap": gap,
        "max_cell_se": max_cell_se,
        "corrected_g_lo": g_lo,
        "route_cost": route_cost,
        "g_lo_minus_route_cost": g_lo - route_cost,
        "retrospective_routable_by_frozen_rule": g_lo > route_cost,
        "best_fixed_action_index": int(oracle_gap(mean_matrix)["best_fixed_action_index"]),
        "mean_matrix": mean_matrix,
        "structural_nulls": nulls,
        "permutation_diagnostic": {
            "n": len(perm),
            "seed": PERMUTATION_SEED,
            "mean_gap": statistics.mean(perm),
            "q95_gap": _quantile(perm, 0.95),
            "right_tail_fraction_plus_one": p_right,
            "interpretation": "retrospective diagnostic only; not a confirmatory p-value",
        },
        "frozen_g_lo": frozen,
        "frozen_g_lo_matches": frozen_matches,
        "source_bundle_sha256": bundle["source_bundle_sha256"],
    }


def analyze() -> dict[str, Any]:
    source_path = OUT / "reanalysis_input.json"
    if not source_path.is_file():
        raise FileNotFoundError("run normalization first: experiments.via_v1_causal_surface.run")
    source = json.loads(source_path.read_text())
    if source.get("ascension_authority") is not False:
        raise ValueError("retrospective input unexpectedly claims ascension authority")
    if source.get("prior_kill_rule") != "WP18_KILL_RULE_TRIGGERED_NO_REAL_IDENTIFIABILITY":
        raise ValueError("binding prior kill rule missing")
    route_cost = float(source["route_cost"])
    results = [analyze_bundle(bundle, route_cost) for bundle in source["bundles"]]

    real = [r for r in results if r["tier"] == "REAL_RETROSPECTIVE"]
    positive = next(r for r in results if r["tier"] == "SYNTHETIC_POSITIVE_CONTROL")
    structural_ok = all(
        abs(r["structural_nulls"]["interaction_destroyed_gap"]) <= NULL_TOL
        and abs(r["structural_nulls"]["collapsed_context_gap"]) <= NULL_TOL
        for r in results
    )
    frozen_ok = all(r["frozen_g_lo_matches"] for r in real)
    real_not_promoted = all(not r["retrospective_routable_by_frozen_rule"] for r in real)
    positive_ok = positive["corrected_g_lo"] > 0.0
    prior_kill_binding = source["prior_kill_rule"] == "WP18_KILL_RULE_TRIGGERED_NO_REAL_IDENTIFIABILITY"

    method_valid = structural_ok and frozen_ok and real_not_promoted and positive_ok and prior_kill_binding
    verdict = "VIA_V1_METHOD_VALIDATED_ASCENSION_BLOCKED" if method_valid else "VIA_V1_METHOD_INVALID"
    return {
        "experiment": "via_v1_causal_surface",
        "verdict": verdict,
        "class": "RETROSPECTIVE_METHOD_VALIDATION_ONLY",
        "scientific_level": "VIA-V1",
        "ascension_authorized": False,
        "next_scientific_level_authorized": False,
        "blocking_fact": (
            "WP18 preregistered kill rule remains binding; this run contains no new admissible "
            "preregistered mechanism/workload evidence"
        ),
        "method_checks": {
            "structural_nulls_zero": structural_ok,
            "frozen_real_certificates_reproduced": frozen_ok,
            "real_evidence_not_promoted": real_not_promoted,
            "synthetic_positive_control_positive": positive_ok,
            "prior_kill_rule_bound": prior_kill_binding,
        },
        "route_cost": route_cost,
        "bundles": results,
        "prohibited_extrapolations": [
            "VIA-V1 scientific PASS",
            "VIA-V2 authorization",
            "architecture work reopened",
            "large-model behavior",
            "general adaptive-compute benefit",
        ],
    }


def _results_markdown(result: dict[str, Any]) -> str:
    rows = []
    for bundle in result["bundles"]:
        rows.append(
            f"| {bundle['name']} | {bundle['plugin_gap']:+.6f} | "
            f"{bundle['corrected_g_lo']:+.6f} | {bundle['route_cost']:.6f} | "
            f"{str(bundle['retrospective_routable_by_frozen_rule'])} |"
        )
    return "\n".join([
        "# VIA-V1 Causal Surface — RESULTS",
        "",
        f"**Verdict:** `{result['verdict']}`",
        "",
        "This is a retrospective method-validation run. It has **no ascension authority**.",
        "The prior WP18 kill rule remains binding by construction.",
        "",
        "| bundle | plugin gap | corrected G_lo | c_route | frozen-rule routable |",
        "|---|---:|---:|---:|---|",
        *rows,
        "",
        "## Method checks",
        "",
        *[f"- `{key}`: **{value}**" for key, value in result["method_checks"].items()],
        "",
        "## Decision",
        "",
        "Engineering substrate: validated against sealed evidence.",
        "Scientific ascension: **BLOCKED_AT_VIA_V1** until a genuinely new, admissible,",
        "preregistered causal study passes its frozen net-value gate.",
        "",
    ])


def main() -> None:
    result = analyze()
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verdict.json").write_text(json.dumps(result, indent=2) + "\n")
    (OUT / "RESULTS.md").write_text(_results_markdown(result))
    print(f"VIA-V1 VERDICT: {result['verdict']}")
    for bundle in result["bundles"]:
        print(
            f"  {bundle['name']:<28} G={bundle['plugin_gap']:+.6f} "
            f"G_lo={bundle['corrected_g_lo']:+.6f} route={bundle['route_cost']:.6f} "
            f"routable={bundle['retrospective_routable_by_frozen_rule']}"
        )
    print(f"  method checks: {result['method_checks']}")
    print("  SCIENTIFIC ASCENSION: BLOCKED_AT_VIA_V1 (binding prior kill rule)")


if __name__ == "__main__":
    main()
