"""Post-primary temporal audit of EXP03; never a replacement primary endpoint.

The original sealed bundle is freshly replayed by the frozen runner before this
audit consumes it. Metrics below are explicitly descriptive. A zero total spike
contrast does not imply a zero temporal contrast.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path
from typing import Any

from experiments.cneh_exp_03 import run

ARMS = ("SHAM_BASE", "SHAM_PROBE_A", "CUT_AB_BASE", "CUT_AB_PROBE_A")
SIGNS = (-1, 1, 1, -1)


def temporal_contrast(series: dict[str, list[int]]) -> dict[str, Any]:
    """Integer population counts, not individual spike trains or synchrony."""
    if set(series) != set(ARMS):
        raise ValueError("incomplete factorial arms")
    lengths = {len(s) for s in series.values()}
    if len(lengths) != 1 or next(iter(lengths)) == 0:
        raise ValueError("unequal or empty time grid")
    if any(type(x) is not int or x < 0 for s in series.values() for x in s):
        raise ValueError("invalid population spike counts")
    d = [sum(sign * series[arm][t] for arm, sign in zip(ARMS, SIGNS, strict=True))
         for t in range(next(iter(lengths)))]
    running = 0
    cumulative = []
    for value in d:
        running += value
        cumulative.append(running)
    totals = {arm: sum(series[arm]) for arm in ARMS}
    endpoint = sum(sign * totals[arm] for arm, sign in zip(ARMS, SIGNS, strict=True))
    if endpoint != running:
        raise ValueError("integer integration invariant violated")
    return {
        "arm_totals": totals,
        "all_arm_totals_equal": len(set(totals.values())) == 1,
        "terminal_factorial_count": endpoint,
        "instantaneous_factorial_counts": d,
        "cumulative_factorial_counts": cumulative,
        "sum_abs_instantaneous_factorial_counts": sum(abs(x) for x in d),
        "max_abs_cumulative_factorial_count": max(abs(x) for x in cumulative),
        "nonzero_temporal_interaction": any(d),
        "endpoint_null_hides_temporal_interaction": endpoint == 0 and any(d),
    }


def mean_free_reference(values: list[float]) -> list[float]:
    """Future-design reference: zero DC with matched uncentered probe L2 effort.

    Does not change any EXP03 treatment. This is a mathematical construction,
    not proof of orthogonality to feedback or physical energy equivalence.
    """
    if not values or not all(math.isfinite(x) for x in values):
        raise ValueError("invalid probe")
    offset = math.fsum(values) / len(values)
    centered = [x - offset for x in values]
    old_energy = math.fsum(x * x for x in values)
    new_energy = math.fsum(x * x for x in centered)
    if not math.isfinite(old_energy) or not math.isfinite(new_energy):
        raise ValueError("nonfinite probe effort")
    if new_energy == 0:
        if old_energy == 0:
            return centered
        raise ValueError("constant nonzero probe cannot preserve effort by centering")
    scale = math.sqrt(old_energy / new_energy)
    result = [scale * x for x in centered]
    if not all(math.isfinite(x) for x in result):
        raise ValueError("nonfinite centered reference")
    return result


def probe_diagnostics(original: list[float], baseline: float, bound: float, dt_ms: float) -> dict[str, Any]:
    if not math.isfinite(dt_ms) or dt_ms <= 0:
        raise ValueError("invalid time step")
    candidate = mean_free_reference(original)
    n = len(original)
    if any(not 0 <= baseline + x <= bound for x in candidate):
        raise ValueError("mean-free reference violates the declared input envelope")
    old_l2 = math.fsum(x * x for x in original)
    new_l2 = math.fsum(x * x for x in candidate)
    if abs(math.fsum(candidate)) > 1e-10 * max(1.0, math.fsum(abs(x) for x in candidate)):
        raise ValueError("reference DC balance failed")
    if not math.isclose(old_l2, new_l2, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError("reference L2 effort mismatch")
    return {
        "n_ticks": n,
        "original_mean_offset_pA": math.fsum(original) / n,
        "original_signed_input_area_pA_ms_per_neuron": dt_ms * math.fsum(original),
        "original_probe_l2_pA2_ticks": old_l2,
        "future_reference_mean_offset_pA": math.fsum(candidate) / n,
        "future_reference_probe_l2_pA2_ticks": new_l2,
        "future_reference_min_current_pA": min(baseline + x for x in candidate),
        "future_reference_max_current_pA": max(baseline + x for x in candidate),
        "reference_used_in_primary": False,
        "physical_energy_qualified": False,
    }


def describe(episodes: list[dict[str, Any]], protocol: dict[str, Any]) -> dict[str, Any]:
    n = protocol["network"]
    t0, steps = n["intervention_tick"], n["steps"]
    worlds = {}
    for e in episodes:
        seed, arm = e["seed"], e["arm"]
        key = (seed, arm)
        if key in worlds:
            raise ValueError("duplicate seed/arm")
        worlds[key] = e
    if set(worlds) != {(seed, arm) for seed in protocol["seeds"] for arm in ARMS}:
        raise ValueError("missing or foreign world/arm")
    rows = []
    probe = None
    for seed in protocol["seeds"]:
        traces = {arm: worlds[(seed, arm)]["trace"] for arm in ARMS}
        for trace in traces.values():
            if [r["tick"] for r in trace] != list(range(steps)):
                raise ValueError("unexpected time grid")
        a = temporal_contrast({arm: [r["spikes_A"] for r in trace[t0:]] for arm, trace in traces.items()})
        b = temporal_contrast({arm: [r["spikes_B"] for r in trace[t0:]] for arm, trace in traces.items()})
        for name, metric in (("A", a), ("B", b)):
            if any(x > len(n["population_" + name]) for trace in traces.values()
                   for x in [r["spikes_" + name] for r in trace]):
                raise ValueError("spike count exceeds population")
            if metric["terminal_factorial_count"] != metric["cumulative_factorial_counts"][-1]:
                raise ValueError("temporal endpoint mismatch")
        b_primary = math.fsum(sign * worlds[(seed, arm)]["B_post_spikes_per_neuron"]
                              for arm, sign in zip(ARMS, SIGNS, strict=True))
        if b_primary != b["terminal_factorial_count"] / len(n["population_B"]):
            raise ValueError("frozen primary endpoint disagrees with independent temporal reduction")
        source = [float.fromhex(r["u_A_pA"]) - float(protocol["stimulus"]["base_current_pA"])
                  for r in traces["SHAM_PROBE_A"][t0:]]
        if probe is not None and probe != source:
            raise ValueError("probe waveform differs across worlds")
        probe = source
        rows.append({"seed": seed, "A": a, "B": b, "original_primary_B": b_primary})
    if probe is None:
        raise ValueError("no worlds")
    stim = protocol["stimulus"]
    return {
        "schema": "cneh-exp03-post-primary-temporal-audit-v1",
        "authority": "POST_PRIMARY_DESCRIPTIVE_ONLY",
        "scientific_promotion_authorized": False,
        "primary_endpoint_replaced": False,
        "independent_replication": "REPLICATION_NOT_TESTED",
        "physical_energy": "INSTRUMENT_INVALID",
        "n_worlds": len(rows),
        "all_B_arm_totals_equal_in_each_world": all(w["B"]["all_arm_totals_equal"] for w in rows),
        "B_worlds_with_zero_primary_contrast": sum(w["B"]["terminal_factorial_count"] == 0 for w in rows),
        "B_worlds_with_temporal_interaction": sum(w["B"]["nonzero_temporal_interaction"] for w in rows),
        "B_worlds_with_endpoint_cancellation": sum(w["B"]["endpoint_null_hides_temporal_interaction"] for w in rows),
        "probe": probe_diagnostics(probe, float(stim["base_current_pA"]), float(stim["max_current_pA"]), n["dt_ms"]),
        "worlds": rows,
        "interpretation_limits": [
            "Population count histograms cannot identify individual spike timing, phase synchrony or PID.",
            "Global gain feedback remains active; a total factorial effect is not unique direct synaptic mediation.",
            "Finite-window harmonic input may include a nonzero DC component.",
            "No inferential threshold, efficacy claim or retrospective promotion is permitted.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--primary", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists() or args.out.is_symlink():
        raise FileExistsError("post-primary output must be new")
    expected = run.payload(args.source)
    run.verify_payload(args.primary, expected)
    p = run.read_protocol()
    audit = describe(run.pinned.strict_json(expected["episodes.json"]), p)
    audit["primary_manifest_sha256"] = run.pinned.sha((args.primary / "SHA256SUMS").read_bytes())
    audit["auditor_sha256"] = run.pinned.sha(Path(__file__).read_bytes())
    audit["parent_runner_sha256"] = run.pinned.sha(Path(run.__file__).read_bytes())
    files = {"audit.json": run.pinned.canonical(audit)}
    run.write_bundle(args.out, files)
    run.verify_payload(args.out, files)
    summary = {k: v for k, v in audit.items() if k != "worlds"}
    print(run.pinned.canonical(summary).decode().strip())


if __name__ == "__main__":
    main()
