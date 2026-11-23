"""Measured local end-to-end timing; no complete physical cost qualification.

The frozen synthetic workload is synchronous. Package energy on this shared host
cannot be attributed to this process; no FLOP event mapping has been qualified.
Unavailable dimensions stay null, never fabricated from operation proxies.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import statistics
import sys
import time
from pathlib import Path

if __package__:
    from . import run
else:
    import run

HERE = Path(__file__).resolve().parent


def measure() -> dict:
    contract = json.loads((HERE / "qualification_contract.json").read_text())
    plan = contract["timing"]
    protocol = json.loads((HERE / "protocol.json").read_text())
    wall_info = time.get_clock_info("perf_counter")
    cpu_info = time.get_clock_info("process_time")
    if not wall_info.monotonic or not cpu_info.monotonic:
        raise RuntimeError("measurement requires monotonic clocks")
    for arm in run.ARMS:
        for _ in range(plan["warmup_calls_per_arm"]):
            run.simulate(plan["seeds"][0], arm, protocol)
    rng = random.Random(plan["order_seed"])
    raw = []
    trace_by_seed_arm = {}
    for repeat in range(plan["repeats"]):
        for seed in plan["seeds"]:
            order = list(run.ARMS)
            rng.shuffle(order)
            for position, arm in enumerate(order):
                # CPU brackets include the wall-clock calls; raw boundaries retained.
                cpu_start = time.process_time_ns()
                wall_start = time.perf_counter_ns()
                results = [run.simulate(seed, arm, protocol)
                           for _ in range(plan["batch_calls"])]
                wall_end = time.perf_counter_ns()
                cpu_end = time.process_time_ns()
                if wall_end <= wall_start or cpu_end <= cpu_start:
                    raise RuntimeError("nonpositive measured interval")
                # Check every timed call and every repeat; a last-value overwrite
                # would hide transient failures inside a batch or early repeats.
                for result in results:
                    expected = trace_by_seed_arm.setdefault((seed, arm), result["trace_sha256"])
                    if result["trace_sha256"] != expected:
                        raise RuntimeError("deterministic trace parity failed within timed repetitions")
                raw.append({"repeat": repeat, "seed": seed, "position": position,
                            "arm": arm, "batch_calls": plan["batch_calls"],
                            "wall_start_ns": wall_start, "wall_end_ns": wall_end,
                            "cpu_start_ns": cpu_start, "cpu_end_ns": cpu_end,
                            "wall_ns_per_call": (wall_end - wall_start) / plan["batch_calls"],
                            "cpu_ns_per_call": (cpu_end - cpu_start) / plan["batch_calls"],
                            "trace_sha256": result["trace_sha256"]})
    if any(trace_by_seed_arm[s, "COUPLED"] != trace_by_seed_arm[s, "CENTRAL_EMULATOR"] for s in plan["seeds"]):
        raise RuntimeError("emulator parity failed during timing")
    summary = {}
    for arm in run.ARMS:
        values = [r["wall_ns_per_call"] for r in raw if r["arm"] == arm]
        summary[arm] = {"n_batches": len(values), "median_wall_ns_per_call": statistics.median(values),
                        "min_wall_ns_per_call": min(values), "max_wall_ns_per_call": max(values)}
    source_files = [Path(__file__), Path(run.__file__), HERE / "protocol.json", HERE / "qualification_contract.json"]
    return {"schema": "cneh-local-timing-v1", "status": "LOCAL_TIMING_ONLY",
            "cost_status": "COST_INSTRUMENT_INVALID", "scientific_promotion_authorized": False,
            "hardware": {"platform": platform.platform(), "machine": platform.machine(),
                         "processor": platform.processor(), "python": sys.version,
                         "implementation": platform.python_implementation()},
            "clock": {"wall_implementation": wall_info.implementation,
                      "wall_resolution_s": wall_info.resolution,
                      "cpu_implementation": cpu_info.implementation,
                      "cpu_resolution_s": cpu_info.resolution},
            "plan": plan, "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in source_files},
            "physical_vector": {"wall_time": "MEASURED_LOCAL_END_TO_END",
                                "cpu_time": "MEASURED_PROCESS_TIME",
                                "joules": None, "flops": None, "attributable_peak_ram_bytes": None},
            "unmeasured_reasons": {"joules": "No calibrated process-attributable energy instrument; shared host",
                                   "flops": "No architecture-specific PMU mapping and calibration",
                                   "attributable_peak_ram_bytes": "No per-arm memory instrument"},
            "limitations": ["Shared host; uncontrolled concurrent workloads and thermal state",
                            "Warmup and balanced order do not establish physical cost matching",
                            "Includes synthetic plant, trace hashing and batch result capture; not controller-only latency",
                            "All policies execute in one Python process; no distributed hardware interface",
                            "No scientific comparison or uncertainty-qualified hardware advantage"],
            "emulator_trace_parity": True, "raw": raw, "summary": summary}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--require-qualified-cost", action="store_true")
    args = parser.parse_args()
    if args.out.exists():
        raise FileExistsError("refuse overwrite of measured evidence")
    report = measure()
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
    print("LOCAL_TIMING_ONLY; COST_INSTRUMENT_INVALID; raw batches=" + str(len(report["raw"])))
    raise SystemExit(2 if args.require_qualified_cost else 0)


if __name__ == "__main__":
    main()
