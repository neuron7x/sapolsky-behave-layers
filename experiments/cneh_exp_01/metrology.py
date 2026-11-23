"""Bounded Linux resource measurements; ceilings do not establish resource parity.

Reuses the existing simulator and timing harness. Energy, hardware FLOPs and real
network transport remain INSTRUMENT_INVALID. Unsigned measurements are internally
checkable records, not independently authenticated physical observations.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import random
import resource
import statistics
import struct
import subprocess
import sys
import tempfile
import time
from typing import Any

HERE = Path(__file__).resolve().parent
if __package__:
    from . import hardware, run
else:
    # -I -S workers deliberately exclude ambient site packages and PYTHONPATH.
    sys.path.insert(0, str(HERE))
    import hardware
    import run

CONTRACT = HERE / "metrology_contract.json"
LIMITATIONS = [
    "Shared Linux host; scheduler, thermal state and other processes are uncontrolled",
    "RSS is the entire fresh worker high-water mark, not incremental controller memory",
    "Profiled controller and serialization runs are separate from unprofiled timings",
    "Serialization fixture measures payload encoding, not a network or IPC transport",
    "Controller invocations are measured counts, not hardware FLOPs",
    "Ceiling admission and paired resource records do not establish resource parity",
    "Hashes need a trusted code anchor; consistent fabricated timings are not authenticated",
]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_hashes() -> dict[str, str]:
    names = ("metrology.py", "metrology_contract.json", "hardware.py", "run.py",
             "protocol.json", "qualification_contract.json")
    return {name: sha((HERE / name).read_bytes()) for name in names}


def runtime_identity() -> dict[str, Any]:
    modules = (platform, resource, statistics, struct, json)
    return {"python": sys.version, "implementation": platform.python_implementation(),
            "executable_sha256": sha(Path(sys.executable).resolve().read_bytes()),
            "stdlib_sha256": {module.__name__: sha(Path(module.__file__).read_bytes()) for module in modules},
            "third_party_dependencies": [], "precision": "binary64"}


def _read_optional(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return "UNAVAILABLE"


def host_identity() -> dict[str, Any]:
    cpu_info = _read_optional(Path("/proc/cpuinfo"))
    model = next((line.split(":", 1)[1].strip() for line in cpu_info.splitlines()
                  if line.startswith("model name") and ":" in line), "UNAVAILABLE")
    power = []
    for entry in sorted(Path("/sys/class/power_supply").glob("*")):
        power.append({"name": entry.name, **{name: _read_optional(entry / name)
                      for name in ("type", "online", "status", "capacity")}})
    gpu = [{"name": entry.name, "vendor": _read_optional(entry / "device/vendor")}
           for entry in sorted(Path("/sys/class/drm").glob("card[0-9]*"))
           if entry.name[4:].isdigit() and (entry / "device").exists()]
    return {"os": platform.system(), "kernel": platform.release(), "machine": platform.machine(),
            "cpu_model": model, "logical_cpus": os.cpu_count(), "affinity": sorted(os.sched_getaffinity(0)),
            "cpu0_governor": _read_optional(Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")),
            "power_supplies": power, "power_state_status": "RECORDED" if power else "UNAVAILABLE",
            "gpu_devices": gpu, "gpu_execution": "NOT_USED"}


def _positive_int(value: Any, name: str, *, zero: bool = False) -> int:
    if type(value) is not int or value < (0 if zero else 1):
        raise ValueError(f"invalid integer measurement: {name}")
    return value


def _finite_tree(value: Any) -> None:
    if type(value) is float and not math.isfinite(value):
        raise ValueError("nonfinite metrology value")
    if isinstance(value, dict):
        for item in value.values():
            _finite_tree(item)
    elif isinstance(value, list):
        for item in value:
            _finite_tree(item)


def _interval(row: dict, prefix: str) -> int:
    start = _positive_int(row[prefix + "_start_ns"], prefix + " start", zero=True)
    end = _positive_int(row[prefix + "_end_ns"], prefix + " end")
    if end <= start:
        raise ValueError("nonpositive measured interval")
    return end - start


def _nonoverlap(rows: list[dict], clock: str) -> None:
    last_end = None
    for row in rows:
        _interval(row, clock)
        if last_end is not None and row[clock + "_start_ns"] < last_end:
            raise ValueError("overlapping sequential measurement intervals")
        last_end = row[clock + "_end_ns"]


def _profile(arm: str, seed: int, protocol: dict) -> dict:
    original = run.Controller.act
    controller_ns = serialization_ns = calls = payload_bytes = packets = 0

    def measured(controller, t, sensed, goal, actual_arm, plant, **kwargs):
        nonlocal controller_ns, serialization_ns, calls, payload_bytes, packets
        start = time.perf_counter_ns()
        result = original(controller, t, sensed, goal, actual_arm, plant, **kwargs)
        controller_ns += time.perf_counter_ns() - start
        calls += 1
        values = sensed if arm in ("COUPLED", "SCRAMBLED_MATCHED_TRAFFIC") else sensed[:1] if arm == "ONE_WAY" else ()
        if values:
            start = time.perf_counter_ns()
            encoded = [struct.pack("!d", value) for value in values]
            serialization_ns += time.perf_counter_ns() - start
            payload_bytes += sum(len(packet) for packet in encoded)
            packets += len(encoded)
        return result

    start = time.perf_counter_ns()
    run.Controller.act = measured
    try:
        result = run.simulate(seed, arm, protocol)
    finally:
        run.Controller.act = original
    return {"seed": seed, "controller_calls": calls, "controller_ns": controller_ns,
            "profile_episode_wall_ns": time.perf_counter_ns() - start,
            "serialization_ns": serialization_ns, "payload_bytes": payload_bytes,
            "packets": packets, "training_steps": 0, "result": result}


def worker(arm: str, expected_sources: dict, expected_runtime: dict) -> dict:
    entered = time.perf_counter_ns()
    if sys.platform != "linux" or arm not in run.ARMS:
        raise ValueError("qualified worker requires Linux and a declared arm")
    if source_hashes() != expected_sources or runtime_identity() != expected_runtime:
        raise ValueError("worker source or runtime mismatch")
    contract = run.strict_json(CONTRACT.read_bytes())
    plan = contract["isolated"]
    protocol = run.strict_json((HERE / "protocol.json").read_bytes())
    # Linux ru_maxrss is KiB. This includes interpreter/import high-water overhead.
    baseline_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    for _ in range(plan["warmup_calls_per_arm"]):
        run.simulate(plan["seeds"][0], arm, protocol)
    samples = []
    for seed in plan["seeds"]:
        cpu_start, wall_start = time.process_time_ns(), time.perf_counter_ns()
        results = [run.simulate(seed, arm, protocol) for _ in range(plan["batch_calls_per_seed"])]
        wall_end, cpu_end = time.perf_counter_ns(), time.process_time_ns()
        if any(result != results[0] for result in results):
            raise ValueError("worker repeated trajectory mismatch")
        samples.append({"seed": seed, "calls": len(results), "result": results[0],
                        "wall_start_ns": wall_start, "wall_end_ns": wall_end,
                        "cpu_start_ns": cpu_start, "cpu_end_ns": cpu_end})
    profile = _profile(arm, plan["seeds"][0], protocol)
    result = {"arm": arm, "source_sha256": source_hashes(), "runtime": runtime_identity(),
              "baseline_peak_rss_bytes": baseline_rss,
              "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
              "rss_unit_conversion": "Linux ru_maxrss KiB multiplied by 1024",
              "samples": samples, "profile": profile, "worker_start_ns": entered,
              "worker_end_ns": time.perf_counter_ns()}
    if result["source_sha256"] != expected_sources:
        raise ValueError("worker source changed during measurement")
    return result


def launch_worker(arm: str, contract: dict, sources: dict, runtime: dict) -> dict:
    request = run.canonical({"sources": sources, "runtime": runtime})
    command = [sys.executable, "-I", "-S", str(Path(__file__).resolve()), "--worker", arm]
    start = time.perf_counter_ns()
    completed = subprocess.run(command, input=request, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               timeout=contract["limits"]["worker_timeout_seconds"], check=False)
    end = time.perf_counter_ns()
    if completed.returncode != 0:
        raise RuntimeError(f"metrology worker failed with exit {completed.returncode}")
    if len(completed.stdout) > contract["limits"]["worker_stdout_bytes_max"]:
        raise ValueError("worker output exceeded byte ceiling")
    result = run.strict_json(completed.stdout)
    if (type(result) is not dict or result.get("arm") != arm
            or result.get("source_sha256") != sources or result.get("runtime") != runtime):
        raise ValueError("unbound worker result")
    return {**result, "parent_start_ns": start, "parent_end_ns": end,
            "stdout_bytes": len(completed.stdout)}


def _verification_measurement(contract: dict, protocol: dict) -> list[dict]:
    with tempfile.TemporaryDirectory(prefix="cneh-metrology-verifier-") as directory:
        out = Path(directory) / "bundle"
        run.write_bundle(out, "SMOKE", contract["verification"]["seeds"], protocol)
        rows = []
        for repeat in range(contract["verification"]["repeats"]):
            cpu_start, wall_start = time.process_time_ns(), time.perf_counter_ns()
            verdict = run.verify_bundle(out, require_valid=True)
            wall_end, cpu_end = time.perf_counter_ns(), time.process_time_ns()
            rows.append({"repeat": repeat, "wall_start_ns": wall_start, "wall_end_ns": wall_end,
                         "cpu_start_ns": cpu_start, "cpu_end_ns": cpu_end,
                         "verdict": verdict["verdict"]})
        return rows


def _summary(workers: list[dict]) -> dict:
    summary = {}
    for arm in run.ARMS:
        records = [row for row in workers if row["arm"] == arm]
        walls = [_interval(s, "wall") / s["calls"] for row in records for s in row["samples"]]
        ordered = sorted(walls)
        summary[arm] = {"n_samples": len(walls), "median_wall_ns_per_call": statistics.median(walls),
                        "p95_wall_ns_per_call": ordered[math.ceil(0.95 * len(ordered)) - 1],
                        "min_wall_ns_per_call": min(walls), "max_wall_ns_per_call": max(walls),
                        "max_worker_peak_rss_bytes": max(row["peak_rss_bytes"] for row in records),
                        "median_dispatch_residual_ns": statistics.median(
                            _interval(row, "parent") - _interval(row, "worker") for row in records)}
    return summary


def _validate_host(host: dict) -> None:
    current = host_identity()
    if type(host) is not dict or set(host) != set(current):
        raise ValueError("host identity fields mismatch")
    # Power readings and governor are time-varying observations, not replayable
    # identity. Require their recorded schema; bind the stable execution context.
    for name in ("os", "kernel", "machine", "cpu_model", "logical_cpus", "affinity", "gpu_execution"):
        if run.canonical(host[name]) != run.canonical(current[name]):
            raise ValueError("host execution context mismatch")
    if not isinstance(host["cpu0_governor"], str):
        raise ValueError("invalid governor observation")
    for records, fields in ((host["power_supplies"], {"name", "type", "online", "status", "capacity"}),
                            (host["gpu_devices"], {"name", "vendor"})):
        if not isinstance(records, list) or any(type(record) is not dict or set(record) != fields
                                               or any(type(value) is not str for value in record.values())
                                               for record in records):
            raise ValueError("invalid device or power-state observation")
    if host["power_state_status"] != ("RECORDED" if host["power_supplies"] else "UNAVAILABLE"):
        raise ValueError("power-state availability mismatch")


def _validate_inherited(timing: dict, sources: dict, replay: dict) -> None:
    expected_fields = {"schema", "status", "cost_status", "scientific_promotion_authorized", "hardware",
                       "clock", "plan", "source_sha256", "physical_vector", "unmeasured_reasons", "limitations",
                       "emulator_trace_parity", "raw", "summary"}
    if type(timing) is not dict or set(timing) != expected_fields:
        raise ValueError("inherited timing fields mismatch")
    plan = run.strict_json((HERE / "qualification_contract.json").read_bytes())["timing"]
    constants = {
        "schema": "cneh-local-timing-v1", "plan": plan, "status": "LOCAL_TIMING_ONLY",
        "cost_status": "COST_INSTRUMENT_INVALID", "scientific_promotion_authorized": False,
        "emulator_trace_parity": True,
        "source_sha256": {name: sources[name] for name in ("hardware.py", "run.py", "protocol.json", "qualification_contract.json")},
        "hardware": {"platform": platform.platform(), "machine": platform.machine(),
                     "processor": platform.processor(), "python": sys.version,
                     "implementation": platform.python_implementation()},
        "physical_vector": {"wall_time": "MEASURED_LOCAL_END_TO_END", "cpu_time": "MEASURED_PROCESS_TIME",
                            "joules": None, "flops": None, "attributable_peak_ram_bytes": None},
        "unmeasured_reasons": {"joules": "No calibrated process-attributable energy instrument; shared host",
                               "flops": "No architecture-specific PMU mapping and calibration",
                               "attributable_peak_ram_bytes": "No per-arm memory instrument"},
        "limitations": ["Shared host; uncontrolled concurrent workloads and thermal state",
                        "Warmup and balanced order do not establish physical cost matching",
                        "Includes synthetic plant, trace hashing and batch result capture; not controller-only latency",
                        "All policies execute in one Python process; no distributed hardware interface",
                        "No scientific comparison or uncertainty-qualified hardware advantage"],
    }
    wall, cpu = time.get_clock_info("perf_counter"), time.get_clock_info("process_time")
    constants["clock"] = {"wall_implementation": wall.implementation, "wall_resolution_s": wall.resolution,
                          "cpu_implementation": cpu.implementation, "cpu_resolution_s": cpu.resolution}
    for name, expected in constants.items():
        if run.canonical(timing[name]) != run.canonical(expected):
            raise ValueError(f"inherited timing source/metadata mismatch: {name}")
    rng, expected_order = random.Random(plan["order_seed"]), []
    for repeat in range(plan["repeats"]):
        for seed in plan["seeds"]:
            arms = list(run.ARMS)
            rng.shuffle(arms)
            expected_order.extend((repeat, seed, position, arm) for position, arm in enumerate(arms))
    if [(r["repeat"], r["seed"], r["position"], r["arm"]) for r in timing["raw"]] != expected_order:
        raise ValueError("missing, duplicated or reordered inherited timing sample")
    row_fields = {"repeat", "seed", "position", "arm", "batch_calls", "wall_start_ns", "wall_end_ns",
                  "cpu_start_ns", "cpu_end_ns", "wall_ns_per_call", "cpu_ns_per_call", "trace_sha256"}
    for row in timing["raw"]:
        if set(row) != row_fields:
            raise ValueError("inherited sample fields mismatch")
        for name in ("repeat", "seed", "position", "batch_calls"):
            _positive_int(row[name], name, zero=name in ("repeat", "position"))
        if row["batch_calls"] != plan["batch_calls"] or row["trace_sha256"] != replay[row["seed"], row["arm"]]["trace_sha256"]:
            raise ValueError("inherited timing trajectory mismatch")
        for clock in ("wall", "cpu"):
            if row[clock + "_ns_per_call"] != _interval(row, clock) / row["batch_calls"]:
                raise ValueError("inherited timing arithmetic mismatch")
    _nonoverlap(timing["raw"], "wall")
    _nonoverlap(timing["raw"], "cpu")
    summary = {}
    for arm in run.ARMS:
        values = [row["wall_ns_per_call"] for row in timing["raw"] if row["arm"] == arm]
        summary[arm] = {"n_batches": len(values), "median_wall_ns_per_call": statistics.median(values),
                        "min_wall_ns_per_call": min(values), "max_wall_ns_per_call": max(values)}
    if run.canonical(timing["summary"]) != run.canonical(summary):
        raise ValueError("inherited timing summary mismatch")


def measured_failures(report: dict, contract: dict) -> list[str]:
    """Every declared engineering ceiling is applied, without cost-parity inference."""
    limits = contract["limits"]
    failures = []

    def ceiling(label: str, observed: float, bound: str) -> None:
        if observed > limits[bound]:
            failures.append(label + ":" + bound)

    for row in report["workers"]:
        label = f'{row["repeat"]}:{row["arm"]}'
        ceiling(label, row["peak_rss_bytes"], "worker_peak_rss_bytes_max")
        ceiling(label, row["stdout_bytes"], "worker_stdout_bytes_max")
        ceiling(label, _interval(row, "parent"), "parent_process_wall_ns_max")
        ceiling(label, _interval(row, "parent") / 1e9, "worker_timeout_seconds")
        for sample in row["samples"]:
            for clock in ("wall", "cpu"):
                ceiling(label, _interval(sample, clock) / sample["calls"], clock + "_ns_per_call_max")
        profile = row["profile"]
        for key, bound in (("profile_episode_wall_ns", "profile_episode_wall_ns_max"),
                           ("controller_ns", "controller_profile_ns_max"),
                           ("serialization_ns", "serialization_ns_max"),
                           ("payload_bytes", "payload_bytes_per_episode_max"),
                           ("training_steps", "training_steps_max")):
            ceiling(label, profile[key], bound)
    for row in report["verification"]:
        ceiling("verifier", _interval(row, "wall"), "verification_wall_ns_max")
    for row in report["inherited_timing"]["raw"]:
        for clock in ("wall", "cpu"):
            ceiling("inherited", _interval(row, clock) / row["batch_calls"], clock + "_ns_per_call_max")
    return failures


def validate_report(report: dict, *, require_admissible: bool = True) -> dict:
    """Replay semantic results and validate recorded arithmetic, not physical truth."""
    contract = run.strict_json(CONTRACT.read_bytes())
    _finite_tree(report)
    expected_fields = {"schema", "authority", "scientific_promotion_authorized", "resource_parity_verified",
                       "instruments", "source_sha256", "runtime", "host", "inherited_timing", "workers",
                       "verification", "summary", "admission", "limit_failures", "limitations"}
    if type(report) is not dict or set(report) != expected_fields:
        raise ValueError("metrology report field roster mismatch")
    if (report["schema"] != "cneh-linux-metrology-v1" or report["authority"] != contract["authority"]
            or report["scientific_promotion_authorized"] is not False
            or report["resource_parity_verified"] is not False
            or report["instruments"] != contract["unavailable_instruments"]
            or report["limitations"] != LIMITATIONS):
        raise ValueError("metrology authority overclaim")
    sources, runtime = source_hashes(), runtime_identity()
    if report["source_sha256"] != sources or report["runtime"] != runtime:
        raise ValueError("metrology source or runtime mismatch")
    _validate_host(report["host"])
    plan, protocol = contract["isolated"], run.strict_json((HERE / "protocol.json").read_bytes())
    expected_order = []
    rng = random.Random(plan["order_seed"])
    for repeat in range(plan["repeats"]):
        order = list(run.ARMS)
        rng.shuffle(order)
        expected_order.extend((repeat, position, arm) for position, arm in enumerate(order))
    if [(r["repeat"], r["position"], r["arm"]) for r in report["workers"]] != expected_order:
        raise ValueError("missing or reordered isolated arm block")
    _nonoverlap(report["workers"], "parent")
    replay = {(seed, arm): run.simulate(seed, arm, protocol) for seed in plan["seeds"] for arm in run.ARMS}
    worker_fields = {"arm", "source_sha256", "runtime", "baseline_peak_rss_bytes", "peak_rss_bytes",
                     "rss_unit_conversion", "samples", "profile", "worker_start_ns", "worker_end_ns",
                     "parent_start_ns", "parent_end_ns", "stdout_bytes", "repeat", "position"}
    for row in report["workers"]:
        if set(row) != worker_fields or row["source_sha256"] != sources or row["runtime"] != runtime:
            raise ValueError("worker source binding or fields mismatch")
        _positive_int(row["stdout_bytes"], "worker output bytes")
        reply = {name: value for name, value in row.items()
                 if name not in {"parent_start_ns", "parent_end_ns", "stdout_bytes", "repeat", "position"}}
        if row["stdout_bytes"] != len(run.canonical(reply)):
            raise ValueError("worker output byte count mismatch")
        _positive_int(row["repeat"], "worker repeat", zero=True)
        _positive_int(row["position"], "worker position", zero=True)
        if (_positive_int(row["peak_rss_bytes"], "peak RSS") < _positive_int(row["baseline_peak_rss_bytes"], "baseline RSS")
                or row["rss_unit_conversion"] != "Linux ru_maxrss KiB multiplied by 1024"):
            raise ValueError("RSS boundary or units mismatch")
        if not row["parent_start_ns"] <= row["worker_start_ns"] < row["worker_end_ns"] <= row["parent_end_ns"]:
            raise ValueError("worker interval escaped parent interval")
        if [sample["seed"] for sample in row["samples"]] != plan["seeds"]:
            raise ValueError("missing or duplicate worker seed")
        for sample in row["samples"]:
            if set(sample) != {"seed", "calls", "result", "wall_start_ns", "wall_end_ns", "cpu_start_ns", "cpu_end_ns"}:
                raise ValueError("worker sample fields mismatch")
            if (type(sample["calls"]) is not int or sample["calls"] != plan["batch_calls_per_seed"]
                    or run.canonical(sample["result"]) != run.canonical(replay[sample["seed"], row["arm"]])):
                raise ValueError("worker sample replay mismatch")
            _interval(sample, "wall"), _interval(sample, "cpu")
            if not row["worker_start_ns"] <= sample["wall_start_ns"] < sample["wall_end_ns"] <= row["worker_end_ns"]:
                raise ValueError("sample wall interval escaped worker interval")
        _nonoverlap(row["samples"], "wall")
        _nonoverlap(row["samples"], "cpu")
        p = row["profile"]
        expected_packets = protocol["model"]["step_horizon"] * (
            2 if row["arm"] in ("COUPLED", "SCRAMBLED_MATCHED_TRAFFIC") else 1 if row["arm"] == "ONE_WAY" else 0)
        if (set(p) != {"seed", "controller_calls", "controller_ns", "profile_episode_wall_ns", "serialization_ns",
                       "payload_bytes", "packets", "training_steps", "result"}
                or p["seed"] != plan["seeds"][0]
                or p["controller_calls"] != protocol["model"]["step_horizon"]
                or p["packets"] != expected_packets or p["payload_bytes"] != 8 * expected_packets
                or type(p["training_steps"]) is not int or p["training_steps"] != 0
                or run.canonical(p["result"]) != run.canonical(replay[p["seed"], row["arm"]])):
            raise ValueError("profile semantics or payload accounting mismatch")
        for key in ("controller_calls", "controller_ns", "profile_episode_wall_ns", "serialization_ns", "payload_bytes", "packets"):
            _positive_int(p[key], key, zero=key in ("serialization_ns", "payload_bytes", "packets"))
        _positive_int(p["seed"], "profile seed", zero=True)
        if p["controller_ns"] + p["serialization_ns"] > p["profile_episode_wall_ns"]:
            raise ValueError("profile subintervals exceed measured episode")
        if sum(_interval(sample, "wall") for sample in row["samples"]) + p["profile_episode_wall_ns"] > _interval(row, "worker"):
            raise ValueError("profile and sample intervals exceed worker duration")
    verification = report["verification"]
    if [v["repeat"] for v in verification] != list(range(contract["verification"]["repeats"])):
        raise ValueError("missing verification repetition")
    for row in verification:
        if set(row) != {"repeat", "wall_start_ns", "wall_end_ns", "cpu_start_ns", "cpu_end_ns", "verdict"} or row["verdict"] != "REPLICATION_NOT_TESTED":
            raise ValueError("verification measurement semantics mismatch")
        _interval(row, "wall"), _interval(row, "cpu")
    _nonoverlap(verification, "wall")
    _nonoverlap(verification, "cpu")
    _validate_inherited(report["inherited_timing"], sources, replay)
    if (report["workers"][0]["parent_start_ns"] < report["inherited_timing"]["raw"][-1]["wall_end_ns"]
            or verification[0]["wall_start_ns"] < report["workers"][-1]["parent_end_ns"]):
        raise ValueError("measurement phase chronology mismatch")
    if run.canonical(report["summary"]) != run.canonical(_summary(report["workers"])):
        raise ValueError("resource summary mismatch")
    failures = measured_failures(report, contract)
    if report["limit_failures"] != failures or report["admission"] != ("FAIL" if failures else "PASS"):
        raise ValueError("resource admission mismatch")
    if require_admissible and failures:
        raise ValueError("measured resource ceiling exceeded")
    return report


def measure() -> dict:
    if sys.platform != "linux":
        raise ValueError("Linux metrology contract required")
    contract = run.strict_json(CONTRACT.read_bytes())
    sources, runtime = source_hashes(), runtime_identity()
    inherited = hardware.measure()
    workers = []
    rng = random.Random(contract["isolated"]["order_seed"])
    for repeat in range(contract["isolated"]["repeats"]):
        arms = list(run.ARMS)
        rng.shuffle(arms)
        for position, arm in enumerate(arms):
            workers.append({**launch_worker(arm, contract, sources, runtime), "repeat": repeat, "position": position})
    protocol = run.strict_json((HERE / "protocol.json").read_bytes())
    report = {"schema": "cneh-linux-metrology-v1", "authority": contract["authority"],
              "scientific_promotion_authorized": False, "resource_parity_verified": False,
              "instruments": contract["unavailable_instruments"], "source_sha256": sources,
              "runtime": runtime, "host": host_identity(), "inherited_timing": inherited,
              "workers": workers, "verification": _verification_measurement(contract, protocol),
              "summary": _summary(workers), "admission": "NOT_TESTED", "limit_failures": [],
              "limitations": LIMITATIONS}
    report["limit_failures"] = measured_failures(report, contract)
    report["admission"] = "FAIL" if report["limit_failures"] else "PASS"
    validate_report(report, require_admissible=False)
    return report


def write_bundle(out: Path, report: dict) -> None:
    validate_report(report, require_admissible=False)
    out.mkdir(parents=True, exist_ok=False)
    for name, data in {"report.json": run.canonical(report), "contract.json": CONTRACT.read_bytes()}.items():
        with (out / name).open("xb") as stream:
            stream.write(data)
    (out / "SHA256SUMS").write_text("".join(f"{sha((out / name).read_bytes())}  {name}\n"
                                             for name in ("contract.json", "report.json")), encoding="ascii")


def verify_bundle(out: Path) -> dict:
    if out.is_symlink() or not out.is_dir() or {p.name for p in out.iterdir()} != {"report.json", "contract.json", "SHA256SUMS"}:
        raise ValueError("metrology artifact roster mismatch")
    if any(p.is_symlink() or not p.is_file() for p in out.iterdir()):
        raise ValueError("metrology artifact must be regular files")
    expected = "".join(f"{sha((out / name).read_bytes())}  {name}\n" for name in ("contract.json", "report.json"))
    if (out / "SHA256SUMS").read_text() != expected or (out / "contract.json").read_bytes() != CONTRACT.read_bytes():
        raise ValueError("metrology manifest or contract mismatch")
    return validate_report(run.strict_json((out / "report.json").read_bytes()), require_admissible=False)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--require-qualified-cost", action="store_true")
    parser.add_argument("--worker", choices=run.ARMS, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        request = run.strict_json(sys.stdin.buffer.read())
        print(run.canonical(worker(args.worker, request["sources"], request["runtime"])).decode(), end="")
        return 0
    if args.out is None:
        parser.error("--out is required")
    if args.verify:
        report = verify_bundle(args.out)
    else:
        if args.out.exists():
            raise FileExistsError("refuse overwrite of metrology evidence")
        report = measure()
        write_bundle(args.out, report)
    print(run.canonical({"admission": report["admission"], "resource_parity_verified": False,
                         "instruments": report["instruments"], "scientific_promotion_authorized": False}).decode(), end="")
    return 1 if report["admission"] == "FAIL" else 2 if args.require_qualified_cost else 0


if __name__ == "__main__":
    raise SystemExit(main())
