"""Native one-transition numerical-causality diagnostic on sealed common states."""
from __future__ import annotations

import argparse
import inspect
import json
import math
import os
from pathlib import Path
import struct
from unittest.mock import patch

from experiments.cneh_exp_05n import run as n
from experiments.cneh_exp_05t import admission as a

WORKERS = ("A", "B")
PROFILES = ("BASELINE", "DEFAULT", "NO_ICL")
SITES = ("nmda_mg_block", "adex_step")
SUBSTITUTIONS = (("NMDA_ONLY", (SITES[0],)), ("ADEX_ONLY", (SITES[1],)), ("BOTH", SITES))


def raw_array(x, np):
    v = np.asarray(x)
    a.need(v.dtype == np.float64 and np.isfinite(v).all(), "nonfinite or non-binary64 operation")
    return {"shape": list(v.shape), "dtype": str(v.dtype), "values": [float(y).hex() for y in v.ravel()]}


def decode_array(x, np):
    return np.array([a.exact_float(v) for v in x["values"]], dtype=np.float64).reshape(x["shape"])


def cases(root):
    results = {}
    for key in (("A", "DEFAULT"), ("B", "DEFAULT")):
        aid = a.ARTIFACTS[key][0]
        raw = a.read_archive(root / (str(aid) + ".zip"), key)
        v = a.strict_json(raw["run-1.json"])
        a.validate_panel(v, *key, 1)
        results[key[0]] = {(x["seed"], x["arm"]): x for x in v["episodes"]}
    for seed, arm, tick in a.ONSETS:
        x, y = (results[k][seed, arm] for k in ("A", "B"))
        pre = x["trace"][tick-1]
        a.need(pre == y["trace"][tick-1] and x["trace"][tick] != y["trace"][tick], "sealed onset changed")
        cp = max((c for c in x["checkpoints"] if c["data"]["tick"] <= tick-1), key=lambda c: c["data"]["tick"])
        yield {"seed": seed, "arm": arm, "tick": tick, "checkpoint": cp,
               "checkpoint_anchor": x["trace"][cp["data"]["tick"]]["state_sha256"],
               "pre_expected": pre["state_sha256"],
               "A_expected": x["trace"][tick]["state_sha256"], "B_expected": y["trace"][tick]["state_sha256"]}


def from_anchor(case, rt):
    np = rt["np"]
    cp = case["checkpoint"]
    start = cp["data"]["tick"]
    net, mode = n.restore(cp, case["checkpoint_anchor"], case["seed"], start, rt)
    for t in range(start, case["tick"]-1):
        mode, _ = n.step(net, mode, case["arm"], t, np)
    state = n.snapshot(net, mode, case["tick"]-1, np)
    return n.seal(state)


def native_step(case, pre, rt, capture=False, replacements=None):
    np, module = rt["np"], rt["network"]
    t = case["tick"] - 1
    net, mode = n.restore(pre, case["pre_expected"], case["seed"], t, rt)
    exp_calls, adex_calls = [], []
    original_exp, original_adex = np.exp, module.adex_step
    targets = {} if replacements is None else replacements

    def logged_exp(x, *args, **kwargs):
        frame = inspect.currentframe().f_back
        site = frame.f_code.co_name
        origin = frame.f_globals.get("__name__", "")
        del frame
        result = original_exp(x, *args, **kwargs)
        if site in SITES and origin.startswith("bnsyn."):
            a.need(not args and not kwargs, "unexpected native exp signature")
            before = raw_array(x, np)
            native = raw_array(result, np)
            replacement = targets.get(site)
            if replacement is not None:
                a.need(replacement["input"] == before, "counterfactual exp argument mismatch")
                result = decode_array(replacement["output"], np)
            exp_calls.append({"site": site, "module": origin, "input": before, "native_output": native,
                              "output": raw_array(result, np), "substituted": replacement is not None})
        return result

    def logged_adex(state, params, dt_ms, I_syn_pA, I_ext_pA):
        result = original_adex(state, params, dt_ms, I_syn_pA, I_ext_pA)
        adex_calls.append({"V": raw_array(state.V_mV, np), "w": raw_array(state.w_pA, np),
                           "I_syn": raw_array(I_syn_pA, np), "I_ext": raw_array(I_ext_pA, np),
                           "V_next": raw_array(result.V_mV, np), "w_next": raw_array(result.w_pA, np),
                           "spikes_next": [bool(v) for v in result.spiked]})
        return result

    if capture:
        with patch.object(np, "exp", logged_exp), patch.object(module, "adex_step", logged_adex):
            mode, metrics = n.step(net, mode, case["arm"], t, np)
        a.need(tuple(c["site"] for c in exp_calls) == SITES and len(adex_calls) == 1, "unexpected operation roster")
        a.need({c["site"] for c in exp_calls if c["substituted"]} == set(targets), "replacement roster")
    else:
        mode, metrics = n.step(net, mode, case["arm"], t, np)
    post = n.seal(n.snapshot(net, mode, t+1, np))
    return {"post": post, "metrics": metrics, "exp": exp_calls, "adex": adex_calls}


def native_case(case, rt, baseline=None):
    identity = {k: case[k] for k in ("seed", "arm", "tick", "pre_expected", "A_expected", "B_expected")}
    pre = from_anchor(case, rt)
    if pre["sha256"] != case["pre_expected"]:
        return {**identity, "status": "COMMON_PRESTATE_UNREPRODUCED", "observed_pre": pre}
    raw = native_step(case, pre, rt)
    repeat = native_step(case, pre, rt)
    passive = native_step(case, pre, rt, capture=True)
    a.need(raw == repeat, "native same-step repeat mismatch")
    a.need(raw["post"] == passive["post"] and raw["metrics"] == passive["metrics"],
           "passive instrumentation altered native step")
    out = {**identity, "status": "CAPTURED", "pre": pre, "native": passive, "substitutions": []}
    if baseline is not None and baseline["status"] == "CAPTURED":
        a.need(baseline["pre"] == pre, "baseline prestate differs")
        base_calls = {x["site"]: x for x in baseline["native"]["exp"]}
        for name, sites in SUBSTITUTIONS:
            try:
                observed = native_step(case, pre, rt, capture=True,
                                       replacements={k: base_calls[k] for k in sites})
            except ValueError as exc:
                out["substitutions"].append({"name": name, "status": "UNSUPPORTED", "reason": str(exc)})
                continue
            out["substitutions"].append({"name": name, "status": "EXECUTED", "result": observed})
    return out


def profile_fingerprint(rt, profile, install_report):
    np = rt["np"]
    if profile != "NO_ICL":
        return n.fingerprint(rt, profile, install_report)
    core = np._core._multiarray_umath
    a.need(os.environ.get("NPY_DISABLE_CPU_FEATURES") == "AVX512_ICL" and
           not core.__cpu_features__.get("AVX512_ICL", False), "NO_ICL intervention not realized")
    # Same-process identity and realized dispatch; not equivalent to baseline.
    return {"cpuinfo_sha256": a.file_sha(Path("/proc/cpuinfo")),
            "executable_sha256": a.file_sha(Path(os.sys.executable).resolve()),
            "features": {k: bool(v) for k, v in sorted(core.__cpu_features__.items())},
            "disabled": os.environ["NPY_DISABLE_CPU_FEATURES"], "numpy": np.__version__,
            "install_report_sha256": a.file_sha(install_report)}


def execute(args):
    lock = n.pinned.strict_json(n.LOCK.read_bytes())
    before = n.pinned.validate_source(args.source, lock)
    rt = n.pinned.load_runtime(args.source, lock)
    if args.profile == "NO_ICL" and args.unavailable:
        a.need(not rt["np"]._core._multiarray_umath.__cpu_features__.get("AVX512_ICL", False),
               "false NO_ICL unavailable")
        return {"worker": args.worker, "profile": args.profile, "status": "NOT_AVAILABLE", "cases": []}
    baseline = None
    if args.profile == "DEFAULT":
        a.need(args.baseline is not None, "default needs paired baseline")
        b = a.strict_json(args.baseline.read_bytes())
        a.need((b["worker"], b["profile"]) == (args.worker, "BASELINE"), "wrong paired baseline")
        baseline = {(x["seed"], x["arm"], x["tick"]): x for x in b["cases"]}
        a.need(set(baseline) == set(a.ONSETS), "paired baseline roster")
    result = [native_case(c, rt, None if baseline is None else baseline[c["seed"], c["arm"], c["tick"]])
              for c in cases(args.archives)]
    a.need(n.pinned.validate_source(args.source, lock) == before, "native source changed")
    return {"worker": args.worker, "profile": args.profile, "status": "EXECUTED",
            "fingerprint": profile_fingerprint(rt, args.profile, args.install_report), "cases": result}


def ordered_int(x):
    u = struct.unpack(">Q", struct.pack(">d", a.exact_float(x)))[0]
    return (~u & ((1 << 64)-1)) if u >> 63 else u | (1 << 63)


def diff_array(x, y):
    a.need(len(x) == len(y), "array difference roster")
    result = []
    for i, (p, q) in enumerate(zip(x, y, strict=True)):
        if p != q:
            delta = a.exact_float(q) - a.exact_float(p)
            a.need(math.isfinite(delta), "nonfinite difference")
            result.append({"index": i, "baseline": p, "default": q,
                           "signed_delta_hex": delta.hex(), "ulp_distance": abs(ordered_int(q)-ordered_int(p))})
    return result


def compare(base, default, no_icl):
    ident = {k: base[k] for k in ("seed", "arm", "tick")}
    if base["status"] != "CAPTURED" or default["status"] != "CAPTURED":
        return {**ident, "status": "INCONCLUSIVE_PRESTATE"}
    a.need(base["pre"] == default["pre"], "cross-profile common prestate mismatch")
    b, d = base["native"], default["native"]
    bpost, dpost = b["post"], d["post"]
    reproduced = bpost["sha256"] == base["A_expected"] and dpost["sha256"] == base["B_expected"]
    exp_diffs = []
    for x, y in zip(b["exp"], d["exp"], strict=True):
        a.need(x["site"] == y["site"], "exp callsite mismatch")
        same = x["input"] == y["input"]
        exp_diffs.append({"site": x["site"], "input_equal": same,
                          "output_differences": diff_array(x["output"]["values"], y["output"]["values"]) if same else None})
    replacements = []
    for v in default["substitutions"]:
        replacements.append({"name": v["name"], "status": v["status"],
                             "matches_baseline": v["status"] == "EXECUTED" and v["result"]["post"] == bpost
                             and v["result"]["metrics"] == b["metrics"]})
    arrays = {k: diff_array(bpost["data"]["arrays"][k], dpost["data"]["arrays"][k]) for k in n.ARRAYS}
    no_icl_match = None if no_icl is None or no_icl["status"] != "CAPTURED" else no_icl["native"]["post"] == bpost
    return {**ident, "status": "SEALED_TRANSITION_REPRODUCED" if reproduced else
            "NO_PROFILE_DIFFERENCE" if bpost == dpost else "NEW_TRANSITION_DIFFERENCE",
            "baseline_sha256": bpost["sha256"], "default_sha256": dpost["sha256"],
            "no_icl_matches_baseline": no_icl_match, "exp_differences": exp_diffs,
            "synaptic_current_differences": diff_array(b["adex"][0]["I_syn"]["values"], d["adex"][0]["I_syn"]["values"]),
            "post_array_differences": arrays, "substitutions": replacements}


def aggregate(root):
    results = []
    for worker in WORKERS:
        folder = root / ("cneh-exp-05t-" + worker)
        names = {"baseline.json", "default.json", "no-icl.json", "install.json", "SHA256SUMS"}
        a.need({p.name for p in folder.iterdir()} == names, "worker artifact roster")
        manifest = "".join(a.file_sha(folder / name) + "  " + name + "\n" for name in sorted(names - {"SHA256SUMS"}))
        a.need((folder / "SHA256SUMS").read_text() == manifest, "worker artifact manifest")
        values = [a.strict_json((folder / name).read_bytes()) for name in ("baseline.json", "default.json", "no-icl.json")]
        maps = []
        for profile, value in zip(PROFILES, values, strict=True):
            a.need((value["worker"], value["profile"]) == (worker, profile), "worker profile binding")
            by = {(x["seed"], x["arm"], x["tick"]): x for x in value["cases"]}
            a.need((profile == "NO_ICL" and value["status"] == "NOT_AVAILABLE" and not by)
                   or (len(value["cases"]) == 6 and set(by) == set(a.ONSETS)), "worker case roster")
            maps.append(by)
        for k in a.ONSETS:
            results.append({"worker": worker, **compare(maps[0][k], maps[1][k], maps[2].get(k))})
    return {"experiment": a.EXPERIMENT, "scientific_promotion_authorized": False,
            "scientific_promotion": "BLOCKED", "scope": "SIX_SEALED_LOCAL_TRANSITIONS_ONLY",
            "historical_native_panel": "FAIL_PRESERVED",
            "reproduced_onsets": sum(x["status"] == "SEALED_TRANSITION_REPRODUCED" for x in results),
            "results": results}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--source", type=Path, required=True)
    run.add_argument("--archives", type=Path, required=True)
    run.add_argument("--worker", choices=WORKERS, required=True)
    run.add_argument("--profile", choices=PROFILES, required=True)
    run.add_argument("--install-report", type=Path, required=True)
    run.add_argument("--baseline", type=Path)
    run.add_argument("--unavailable", action="store_true")
    agg = sub.add_parser("aggregate")
    agg.add_argument("--profiles", type=Path, required=True)
    agg.add_argument("--verify", action="store_true")
    for parser in (run, agg):
        parser.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    result = execute(args) if args.command == "run" else aggregate(args.profiles)
    raw = a.canonical(result)
    if getattr(args, "verify", False):
        a.need(args.out.read_bytes() == raw, "aggregate replay mismatch")
    else:
        with args.out.open("xb") as handle:
            handle.write(raw)
    if args.command == "aggregate":
        print(raw.decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
