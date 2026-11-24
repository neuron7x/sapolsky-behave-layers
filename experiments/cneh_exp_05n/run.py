"""Pinned finite BN-Syn native checkpoint/replay engineering diagnostic."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import importlib
import itertools
import json
import math
import os
from pathlib import Path
import platform
import sys

from experiments.cneh_exp_04b import run as neural
from experiments.cneh_exp_04d import run as d

pinned, parent = d.pinned, d.parent
EXPERIMENT = "CNEH-EXP-05N"
HERE = Path(__file__).resolve().parent
LOCK = HERE.parent / "cneh_exp_01" / "bnsyn_integration_contract.json"
REQUIREMENTS = LOCK.with_name("bnsyn-requirements.lock")
SEEDS = (92001, 92002)
ARMS = ("WAIT", "G0", "G1", "ALTERNATE")
STEPS = 512
CHECKPOINTS = (0, 128, 256, 384, 480)
SUFFIX = 32
SCHEDULE = {128: 1, 256: 2, 384: 3}
WORKERS = ("A", "B")
PROFILES = ("DEFAULT", "BASELINE")
ATTEMPTS = (1, 2)
ARRAYS = ("V", "w", "g_ampa", "g_nmda", "g_gabaa", "I_ext")
NET_FIELDS = set("np adex syn dt_ms rng backend nE nI is_inhib W_exc W_inh state g_ampa g_nmda g_gabaa _I_ext_buffer branch sigma_ctl gain _A_prev _use_torch _torch_device _W_exc_t _W_inh_t".split())
STATE_FIELDS = {"V_mV", "w_pA", "spiked"}
BRANCH_FIELDS = {"eps", "ema_alpha", "_sigma_ema"}
SIGMA_FIELDS = {"params", "gain"}
THREADS = {"OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1",
           "MKL_NUM_THREADS": "1", "BNSYN_USE_TORCH": "0"}


def need(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def file_sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def digest(value):
    return sha(canonical(value))


def hex_float(value):
    f = float(value)
    need(math.isfinite(f), "nonfinite numeric state")
    return f.hex()


def parse_float(value):
    need(type(value) is str, "non-string state float")
    f = float.fromhex(value)
    need(math.isfinite(f) and f.hex() == value, "invalid noncanonical state float")
    return f


def array_hex(values, np):
    a = np.asarray(values)
    need(a.shape == (32,) and a.dtype == np.float64, "invalid native array shape/dtype")
    return [hex_float(x) for x in a]


def decode_array(values, np):
    need(type(values) is list and len(values) == 32, "invalid checkpoint array shape")
    return np.array([parse_float(x) for x in values], dtype=np.float64)


def bit_array(values, np):
    a = np.asarray(values)
    need(a.shape == (32,) and a.dtype == np.bool_, "invalid native bit array")
    return [bool(x) for x in a]


def decode_bits(values, np):
    need(type(values) is list and len(values) == 32 and all(type(x) is bool for x in values),
         "invalid checkpoint bits")
    return np.array(values, dtype=np.bool_)


def initial(seed, rt):
    np, network, config = (rt[k] for k in ("np", "network", "config"))
    net = network.Network(network.NetworkParams(N=32, frac_inhib=.25, p_conn=0.),
                          config.AdExParams(), config.SynapseParams(), config.CriticalityParams(),
                          dt_ms=.1, rng=np.random.default_rng(seed), backend="reference")
    set_mode(net, 0, np)
    return net


def set_mode(net, mode, np):
    need(type(mode) is int and 0 <= mode < 4, "invalid route mode")
    connectivity = importlib.import_module("bnsyn.connectivity").SparseConnectivity
    return neural.apply_mode(net, mode, np, connectivity)


def config_state(net):
    need(set(vars(net)) == NET_FIELDS and set(vars(net.state)) == STATE_FIELDS
         and set(vars(net.branch)) == BRANCH_FIELDS and set(vars(net.sigma_ctl)) == SIGMA_FIELDS,
         "pinned native attribute roster drift")
    need(net.backend == "reference" and net.nE == 24 and net.nI == 8
         and net._use_torch is False and net._torch_device is None
         and net._W_exc_t is None and net._W_inh_t is None
         and type(net.rng.bit_generator).__name__ == "PCG64",
         "native domain boundary drift")
    return {"network": asdict(net.np), "adex": net.adex.model_dump(mode="json"),
            "synapse": net.syn.model_dump(mode="json"),
            "criticality": net.sigma_ctl.params.model_dump(mode="json"),
            "dt_ms": hex_float(net.dt_ms), "backend": net.backend,
            "nE": net.nE, "nI": net.nI, "rng_class": type(net.rng.bit_generator).__name__}


def snapshot(net, mode, tick, np):
    need(type(tick) is int and 0 <= tick <= STEPS, "invalid checkpoint tick")
    cfg = config_state(net)
    arrays = {"V": net.state.V_mV, "w": net.state.w_pA, "g_ampa": net.g_ampa,
              "g_nmda": net.g_nmda, "g_gabaa": net.g_gabaa, "I_ext": net._I_ext_buffer}
    matrix = parent.matrix_digest(net.W_exc.to_dense(), net.W_inh.to_dense())
    return {"tick": tick, "mode": mode, "configuration": cfg, "matrix_sha256": matrix,
            "arrays": {k: array_hex(v, np) for k, v in arrays.items()},
            "spikes": bit_array(net.state.spiked, np), "is_inhib": bit_array(net.is_inhib, np),
            "gain": hex_float(net.gain), "A_prev": hex_float(net._A_prev),
            "branch": {k: hex_float(getattr(net.branch, k)) for k in sorted(BRANCH_FIELDS)},
            "sigma_gain": hex_float(net.sigma_ctl.gain),
            "rng": json.loads(canonical(net.rng.bit_generator.state)),
            "physical_sha256": parent.physical_state_digest(net, np)}


def seal(data):
    return {"data": data, "sha256": digest(data)}


def authenticated(checkpoint, expected, tick):
    need(type(checkpoint) is dict and set(checkpoint) == {"data", "sha256"}, "invalid checkpoint envelope")
    data = checkpoint["data"]
    need(checkpoint["sha256"] == expected == digest(data), "checkpoint anchor digest mismatch")
    need(type(data) is dict and data.get("tick") == tick and type(data["tick"]) is int,
         "stale checkpoint tick")
    return data


def restore(checkpoint, expected, seed, tick, rt):
    np = rt["np"]
    data = authenticated(checkpoint, expected, tick)
    net = initial(seed, rt)
    need(data["configuration"] == config_state(net), "checkpoint configuration drift")
    need(set(data["arrays"]) == set(ARRAYS) and set(data["branch"]) == BRANCH_FIELDS,
         "checkpoint state roster")
    mode = data["mode"]
    need(set_mode(net, mode, np) == data["matrix_sha256"], "checkpoint topology mismatch")
    arrays = {k: decode_array(data["arrays"][k], np) for k in ARRAYS}
    net.state = type(net.state)(V_mV=arrays["V"], w_pA=arrays["w"],
                                spiked=decode_bits(data["spikes"], np))
    need(bit_array(net.is_inhib, np) == data["is_inhib"], "checkpoint population mask mismatch")
    for k in ("g_ampa", "g_nmda", "g_gabaa"):
        setattr(net, k, arrays[k])
    net._I_ext_buffer = arrays["I_ext"]
    net.gain = parse_float(data["gain"])
    net._A_prev = parse_float(data["A_prev"])
    for k in BRANCH_FIELDS:
        setattr(net.branch, k, parse_float(data["branch"][k]))
    net.sigma_ctl.gain = parse_float(data["sigma_gain"])
    net.rng.bit_generator.state = data["rng"]
    need(snapshot(net, mode, tick, np) == data, "restored checkpoint state mismatch")
    return net, mode


def action(arm, tick):
    need(arm in ARMS and type(tick) is int and 0 <= tick < STEPS, "invalid fixed action")
    return None if arm == "WAIT" else 0 if arm == "G0" else 1 if arm == "G1" else (tick // 64) % 2


def step(net, mode, arm, tick, np):
    if tick in SCHEDULE:
        physical = parent.physical_state_digest(net, np)
        mode = SCHEDULE[tick]
        set_mode(net, mode, np)
        need(parent.physical_state_digest(net, np) == physical, "switch altered physical memory")
    group = action(arm, tick)
    u = np.zeros(32, dtype=np.float64)
    u[list(d.B)] = 300.
    if group is not None:
        u[list(d.GROUPS[group])] = 500.
    net.gain = 1.
    result = net.step(external_current_pA=u)
    neural.gain.check_current(net._I_ext_buffer, u, 1., 50., np)
    return mode, {k: hex_float(v) for k, v in result.items()}


def row(data):
    return {"tick": data["tick"], "mode": data["mode"], "state_sha256": digest(data),
            "rng_sha256": digest(data["rng"]), "matrix_sha256": data["matrix_sha256"],
            "physical_sha256": data["physical_sha256"],
            "parts": {k: digest(v) for k, v in data.items() if k != "arrays"} |
                     {k: digest(v) for k, v in data["arrays"].items()}}


def episode(seed, arm, rt):
    np = rt["np"]
    net = initial(seed, rt)
    mode = 0
    traces, checkpoints = [], []
    for t in range(STEPS + 1):
        data = snapshot(net, mode, t, np)
        record = row(data)
        if t in CHECKPOINTS:
            checkpoints.append(seal(data))
        if t < STEPS:
            record["group"] = action(arm, t)
            mode, record["metrics"] = step(net, mode, arm, t, np)
        traces.append(record)
    final_before = snapshot(net, mode, STEPS, np)
    for cp in checkpoints:
        start = cp["data"]["tick"]
        clone, clone_mode = restore(cp, traces[start]["state_sha256"], seed, start, rt)
        need(clone.rng is not net.rng and not np.shares_memory(clone.state.V_mV, net.state.V_mV),
             "restored network aliases uninterrupted state")
        for t in range(start, start + SUFFIX + 1):
            record = row(snapshot(clone, clone_mode, t, np))
            if t < start + SUFFIX:
                record["group"] = action(arm, t)
                clone_mode, record["metrics"] = step(clone, clone_mode, arm, t, np)
                need(record == traces[t], "checkpoint suffix mismatch at tick " + str(t))
            else:
                need(record == {k: v for k, v in traces[t].items() if k not in ("group", "metrics")},
                     "checkpoint terminal suffix mismatch")
    need(snapshot(net, mode, STEPS, np) == final_before, "restoration mutated reference")
    return {"seed": seed, "arm": arm, "trace": traces, "checkpoints": checkpoints,
            "restored_transitions": len(CHECKPOINTS) * SUFFIX}


def optional_features(np):
    core = np._core._multiarray_umath
    return sorted(x for x in core.__cpu_dispatch__ if core.__cpu_features__.get(x, False)
                  and x not in core.__cpu_baseline__)


def fingerprint(rt, profile, install_report):
    np = rt["np"]
    core = np._core._multiarray_umath
    need(sys.version_info[:3] == (3, 12, 16) and platform.machine() == "x86_64"
         and platform.system() == "Linux", "unqualified interpreter/architecture")
    need(all(os.environ.get(k) == v for k, v in THREADS.items()), "thread/backend domain drift")
    need((profile == "BASELINE" and not optional_features(np))
         or (profile == "DEFAULT" and not os.environ.get("NPY_DISABLE_CPU_FEATURES")),
         "dispatch profile not realized")
    cpu = {}
    for line in Path("/proc/cpuinfo").read_text().split("\n\n", 1)[0].splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip() in ("vendor_id", "model name", "cpu family", "model", "stepping", "microcode", "flags"):
            cpu[key.strip()] = value.strip()
    need("flags" in cpu and "model name" in cpu, "missing CPU provenance")
    mapped = set()
    for line in Path("/proc/self/maps").read_text().splitlines():
        fields = line.split(maxsplit=5)
        if len(fields) == 6 and fields[5].startswith("/") and ".so" in Path(fields[5]).name:
            path = Path(fields[5])
            need(path.is_file(), "unreadable mapped numerical library")
            mapped.add(str(path.resolve()))
    binaries = {p: file_sha(p) for p in sorted(mapped)}
    names = [Path(p).name.lower() for p in binaries]
    need(all(any(key in n for n in names) for key in ("libm.so", "libc.so", "openblas", "_multiarray_umath")),
         "required loaded library provenance missing")
    executable = Path(sys.executable).resolve()
    probes = (-40., -10., -2., -.5, 0., .5, 2., 10., 20.)
    x = np.arange(32 * 32, dtype=np.float64).reshape(32, 32) / 127. - 3.
    return {"python": sys.version, "executable": str(executable), "executable_sha256": file_sha(executable),
            "platform": platform.platform(), "libc": list(platform.libc_ver()), "cpu": cpu,
            "numpy": np.__version__, "features": {k: bool(v) for k, v in sorted(core.__cpu_features__.items())},
            "baseline": list(core.__cpu_baseline__), "dispatch": list(core.__cpu_dispatch__),
            "disabled": os.environ.get("NPY_DISABLE_CPU_FEATURES", ""),
            "image_os": os.environ.get("ImageOS", ""), "image_version": os.environ.get("ImageVersion", ""),
            "thread_environment": THREADS, "native_binaries": binaries,
            "lock_sha256": file_sha(LOCK), "requirements_sha256": file_sha(REQUIREMENTS),
            "install_report_sha256": file_sha(install_report),
            "math_exp": [hex_float(math.exp(v)) for v in probes],
            "numpy_exp": [hex_float(v) for v in np.exp(np.array(probes))],
            "dot_sha256": sha(np.dot(x, x.T.copy()).astype(">f8").tobytes()),
            "normal_sha256": sha(np.random.default_rng(17).normal(size=32).astype(">f8").tobytes())}


def validate_panel(episodes):
    expected = list(itertools.product(SEEDS, ARMS))
    need([(x["seed"], x["arm"]) for x in episodes] == expected, "panel episode roster")
    for ep in episodes:
        rows = ep["trace"]
        need([r["tick"] for r in rows] == list(range(STEPS + 1)), "panel tick roster")
        need([c["data"]["tick"] for c in ep["checkpoints"]] == list(CHECKPOINTS)
             and ep["restored_transitions"] == len(CHECKPOINTS) * SUFFIX, "checkpoint roster")
        for cp in ep["checkpoints"]:
            t = cp["data"]["tick"]
            data = authenticated(cp, rows[t]["state_sha256"], t)
            need(row(data) == {k: v for k, v in rows[t].items() if k not in ("group", "metrics")},
                 "checkpoint-to-trace binding")
    for seed in SEEDS:
        panel = [x["trace"] for x in episodes if x["seed"] == seed]
        need(len({x[0]["state_sha256"] for x in panel}) == 1, "unpaired initial state")
        need(all([r["rng_sha256"] for r in x] == [r["rng_sha256"] for r in panel[0]]
                 for x in panel), "unpaired exogenous stream")


def execute(source, worker, profile, attempt, install_report):
    need(worker in WORKERS and profile in PROFILES and attempt in ATTEMPTS, "invalid execution roster")
    lock = pinned.strict_json(LOCK.read_bytes())
    source_before = pinned.validate_source(source, lock)
    rt = pinned.load_runtime(source, lock)
    episodes = [episode(seed, arm, rt) for seed, arm in itertools.product(SEEDS, ARMS)]
    validate_panel(episodes)
    fp = fingerprint(rt, profile, install_report)
    need(pinned.validate_source(source, lock) == source_before, "source changed")
    return {"worker": worker, "profile": profile, "attempt": attempt, "fingerprint": fp,
            "source": lock["source"], "episodes": episodes, "panel_sha256": digest(episodes)}


def difference(left, right):
    if left == right:
        return None
    for a, b in zip(left, right, strict=True):
        for x, y in zip(a["trace"], b["trace"], strict=True):
            if x != y:
                return {"seed": a["seed"], "arm": a["arm"], "tick": x["tick"],
                        "fields": sorted(k for k in set(x) | set(y) if x.get(k) != y.get(k)),
                        "parts": sorted(k for k in set(x["parts"]) | set(y["parts"])
                                        if x["parts"].get(k) != y["parts"].get(k))}
    return {"scope": "checkpoint_or_panel_metadata"}


def aggregate(root):
    records = {}
    for worker, profile in itertools.product(WORKERS, PROFILES):
        folder = root / ("cneh-exp-05n-" + worker + "-" + profile)
        expected_names = {"run-1.json", "run-2.json", "install.json", "SHA256SUMS"}
        need(folder.is_dir() and {p.name for p in folder.iterdir()} == expected_names, "artifact roster")
        manifest = "".join(file_sha(folder / name) + "  " + name + "\n"
                           for name in sorted(expected_names - {"SHA256SUMS"}))
        need((folder / "SHA256SUMS").read_text() == manifest, "profile artifact manifest mismatch")
        for attempt in ATTEMPTS:
            value = pinned.strict_json((folder / ("run-" + str(attempt) + ".json")).read_bytes())
            need((value["worker"], value["profile"], value["attempt"]) == (worker, profile, attempt),
                 "profile identity mismatch")
            validate_panel(value["episodes"])
            need(value["panel_sha256"] == digest(value["episodes"])
                 and value["fingerprint"]["install_report_sha256"] == file_sha(folder / "install.json"),
                 "profile digest binding")
            records[worker, profile, attempt] = value
    reference = records["A", "DEFAULT", 1]["episodes"]
    comparisons = [{"worker": w, "profile": p, "attempt": a,
                    "panel_sha256": value["panel_sha256"],
                    "fingerprint": value["fingerprint"],
                    "first_difference": difference(reference, value["episodes"])}
                   for (w, p, a), value in sorted(records.items())]
    passed = all(x["first_difference"] is None for x in comparisons)
    return {"experiment": EXPERIMENT, "scientific_promotion_authorized": False,
            "scientific_promotion": "BLOCKED", "scope": "PINNED_FINITE_NATIVE_ENGINEERING_PANEL_ONLY",
            "historical_native_replay": "FAIL_PRESERVED", "native_panel_status": "PASS_PANEL_ONLY" if passed else "FAIL_PANEL",
            "reports": len(records), "episodes_per_report": len(reference),
            "samples_per_episode": STEPS + 1, "checkpoints_per_episode": len(CHECKPOINTS),
            "restored_transitions_per_checkpoint": SUFFIX, "comparisons": comparisons}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--source", type=Path, required=True)
    run.add_argument("--worker", choices=WORKERS, required=True)
    run.add_argument("--profile", choices=PROFILES, required=True)
    run.add_argument("--attempt", type=int, choices=ATTEMPTS, required=True)
    run.add_argument("--install-report", type=Path, required=True)
    agg = sub.add_parser("aggregate")
    agg.add_argument("--profiles", type=Path, required=True)
    agg.add_argument("--verify", action="store_true")
    for parser in (run, agg):
        parser.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    if args.command == "run":
        result = execute(args.source, args.worker, args.profile, args.attempt, args.install_report)
    else:
        result = aggregate(args.profiles)
    raw = canonical(result)
    if getattr(args, "verify", False):
        need(args.out.is_file() and args.out.read_bytes() == raw, "exact aggregate replay mismatch")
    else:
        with args.out.open("xb") as handle:
            handle.write(raw)
    if args.command == "aggregate":
        print(json.dumps({k: v for k, v in result.items() if k != "comparisons"}, sort_keys=True))
        print(json.dumps([{k: v for k, v in x.items() if k != "fingerprint"} for x in result["comparisons"]], sort_keys=True))
        return 0 if result["native_panel_status"] == "PASS_PANEL_ONLY" else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
