"""Strict BN-Syn receiver noninterference test; distinct prospective cohort."""
from __future__ import annotations

import argparse
import importlib
import math
from pathlib import Path
from typing import Any

from experiments.cneh_exp_03 import gain_intervention as gain
from experiments.cneh_exp_03 import run as parent

HERE = Path(__file__).resolve().parent
pinned = parent.pinned
SEEDS = tuple(range(84001, 84009))
ARMS = ("CUT_CLAMP_BASE", "CUT_CLAMP_PROBE_A", "CUT_CLAMP_B_POSITIVE_CONTROL")
T0 = 400
STEPS = 1000
FIELDS = ("V_mV", "w_pA", "g_ampa", "g_nmda", "g_gabaa", "spikes")


def local_state(net: Any, indices: list[int]) -> dict[str, list]:
    values = {"V_mV": net.state.V_mV, "w_pA": net.state.w_pA,
              "g_ampa": net.g_ampa, "g_nmda": net.g_nmda, "g_gabaa": net.g_gabaa}
    result = {}
    for key, arr in values.items():
        row = [float(arr[j]) for j in indices]
        if not all(math.isfinite(x) for x in row):
            raise ValueError("nonfinite local physical state")
        result[key] = [x.hex() for x in row]
    result["spikes"] = [int(net.state.spiked[j]) for j in indices]
    return result


def compare_states(a: dict, b: dict) -> dict:
    """Exact binary64 hex comparison, not approximate equality or summary hash."""
    if set(a) != set(FIELDS) or set(b) != set(FIELDS):
        raise ValueError("incomplete local state roster")
    differences = 0
    first = None
    max_abs = {k: 0.0 for k in FIELDS[:-1]}
    for k in FIELDS:
        if len(a[k]) != 16 or len(b[k]) != 16:
            raise ValueError("incomplete receiver state")
        for j, (x, y) in enumerate(zip(a[k], b[k], strict=True)):
            if k == "spikes":
                if type(x) is not int or type(y) is not int or x not in (0, 1) or y not in (0, 1):
                    raise ValueError("invalid spike bit")
            else:
                fx, fy = float.fromhex(x), float.fromhex(y)
                if not math.isfinite(fx) or not math.isfinite(fy) or fx.hex() != x or fy.hex() != y:
                    raise ValueError("invalid canonical binary64 state")
                max_abs[k] = max(max_abs[k], abs(fx - fy))
            if x != y:
                differences += 1
                if first is None:
                    first = {"field": k, "local_index": j, "base": x, "probe": y}
    return {"differences": differences, "first": first, "max_abs": max_abs}


def episode(seed: int, arm: str, p: dict, wave: list[float], rt: dict) -> dict:
    if seed not in SEEDS or arm not in ARMS:
        raise ValueError("unregistered world or arm")
    np, network, config = (rt[k] for k in ("np", "network", "config"))
    a, b = p["populations"]["A"], p["populations"]["B"]
    net = network.Network(network.NetworkParams(N=32, frac_inhib=.25, p_conn=.2),
                          config.AdExParams(), config.SynapseParams(), config.CriticalityParams(),
                          dt_ms=.1, rng=np.random.default_rng(seed), backend="reference")
    if net.nE != 24 or net._use_torch:
        raise ValueError("unregistered simulator backend or partition")
    connectivity = importlib.import_module("bnsyn.connectivity").SparseConnectivity
    init = {"A": local_state(net, a), "B": local_state(net, b),
            "weights": parent.matrix_digest(net.W_exc.to_dense(), net.W_inh.to_dense()),
            "rng": pinned.sha(pinned.canonical(net.rng.bit_generator.state))}
    records = []
    witness = None
    clamped = None
    maximum_residual = 0.
    for tick in range(STEPS):
        if tick == T0:
            clamped = float(net.gain)
            old = parent.physical_state_digest(net, np)
            e0, i0 = net.W_exc.to_dense(), net.W_inh.to_dense()
            e, i, witness = parent.cut_weights(e0, i0, a, b, net.nE, np, cut=True)
            # Explicitly test every directed A-to-B column, even if silent.
            ae = [j for j in a if j < net.nE]
            ai = [j-net.nE for j in a if j >= net.nE]
            if np.any(e[np.ix_(b, ae)]) or np.any(i[np.ix_(b, ai)]):
                raise ValueError("incomplete directed cut")
            net.W_exc, net.W_inh = connectivity(e, force_format="dense"), connectivity(i, force_format="dense")
            witness["matrix_sha256"] = parent.matrix_digest(net.W_exc.to_dense(), net.W_inh.to_dense())
            if parent.physical_state_digest(net, np) != old:
                raise ValueError("intervention modified local physical memory")
        if tick >= T0:
            net.gain = clamped
        applied = float(net.gain)
        u = np.full(32, 300., dtype=np.float64)
        if tick >= T0 and arm == ARMS[1]:
            u[a] += wave[tick-T0]
        if tick >= T0 and arm == ARMS[2]:
            u[b] += 20.
        if np.any(u < 0) or np.any(u > 500) or not np.isfinite(u).all():
            raise ValueError("invalid applied input envelope")
        oracle = gain.arrival_oracle(net, np, network, a, b)
        if tick >= T0 and (oracle["ab_e"] or oracle["ab_i"]):
            raise ValueError("post-cut directed arrival")
        metrics = net.step(external_current_pA=u)
        if not all(math.isfinite(float(v)) for v in metrics.values()):
            raise ValueError("nonfinite network metrics")
        gain.check_current(net._I_ext_buffer, u, applied, network.GAIN_CURRENT_SCALE_PA, np)
        maximum_residual = max(maximum_residual, gain.check_delivery(
            (net.g_ampa, net.g_nmda, net.g_gabaa), oracle["conductances"], np, 1e-10, 1e-12))
        rng = pinned.sha(pinned.canonical(net.rng.bit_generator.state))
        if rng != oracle["rng"]:
            raise ValueError("unexpected random tape advancement")
        records.append({"tick": tick, "A": local_state(net, a), "B": local_state(net, b),
                        "rng": rng, "gain": applied.hex(),
                        "B_current": [float(net._I_ext_buffer[j]).hex() for j in b]})
    if witness is None or clamped is None or parent.matrix_digest(net.W_exc.to_dense(), net.W_inh.to_dense()) != witness["matrix_sha256"]:
        raise ValueError("structural witness lost")
    return {"seed": seed, "arm": arm, "initial": init, "clamp": clamped.hex(),
            "cut": witness, "max_conductance_residual_nS": maximum_residual, "trace": records}


def evaluate_pair(episodes: list[dict]) -> dict:
    by = {e["arm"]: e for e in episodes}
    if len(episodes) != 3 or set(by) != set(ARMS) or len({e["seed"] for e in episodes}) != 1:
        raise ValueError("incomplete paired world")
    base, probe, positive = (by[a] for a in ARMS)
    for ep in episodes:
        if ep["initial"] != base["initial"] or ep["clamp"] != base["clamp"] or ep["cut"] != base["cut"]:
            raise ValueError("initial or structural mismatch")
        if [r["tick"] for r in ep["trace"]] != list(range(STEPS)):
            raise ValueError("incomplete trace")
        if ep["trace"][:T0] != base["trace"][:T0]:
            raise ValueError("pre-intervention mismatch")
    differences, first, a_response, positive_response = 0, None, False, False
    maxima = {k: 0. for k in FIELDS[:-1]}
    for x, y, z in zip(base["trace"], probe["trace"], positive["trace"], strict=True):
        t = x["tick"]
        if x["rng"] != y["rng"] or x["rng"] != z["rng"]:
            raise ValueError("random tape divergence")
        if t >= T0 and any(r["gain"] != base["clamp"] for r in (x,y,z)):
            raise ValueError("gain clamp failed")
        if x["B_current"] != y["B_current"]:
            raise ValueError("receiver current mismatch")
        q = compare_states(x["B"], y["B"])
        differences += q["differences"]
        if first is None and q["first"] is not None:
            first = {"tick": t, **q["first"]}
        maxima = {k: max(maxima[k], q["max_abs"][k]) for k in maxima}
        if t >= T0:
            a_response |= bool(compare_states(x["A"], y["A"])["differences"])
            positive_response |= bool(compare_states(x["B"], z["B"])["differences"])
    status = ("MODEL_ISOLATION_FALSIFIED" if differences else
              "EXACT_ISOLATION_OBSERVED" if a_response and positive_response else "INSTRUMENT_UNQUALIFIED")
    return {"seed": base["seed"], "status": status, "exact_B_differences": differences,
            "first_B_counterexample": first, "max_abs_B": maxima, "A_probe_response": a_response,
            "B_positive_control_response": positive_response}


def payload(source: Path) -> tuple[dict[str, bytes], bool]:
    p = gain.protocol()
    lock_path = HERE.parent / "cneh_exp_01" / "bnsyn_integration_contract.json"
    lock = pinned.strict_json(lock_path.read_bytes())
    if lock["source"]["commit"] != "c1de425ce4ece362e7f2feb2d9f24da5d3231014":
        raise ValueError("simulator source drift")
    before = pinned.validate_source(source, lock)
    rt = pinned.load_runtime(source, lock)
    wave = gain.probe(p)
    episodes, worlds = [], []
    for seed in SEEDS:
        rows = [episode(seed, arm, p, wave, rt) for arm in ARMS]
        worlds.append(evaluate_pair(rows))
        episodes.extend(rows)
    if pinned.validate_source(source, lock) != before:
        raise ValueError("simulator source changed")
    passed = all(w["status"] == "EXACT_ISOLATION_OBSERVED" for w in worlds)
    status = ("EXACT_ISOLATION_OBSERVED" if passed else
              "MODEL_ISOLATION_FALSIFIED" if any(w["exact_B_differences"] for w in worlds)
              else "INSTRUMENT_UNQUALIFIED")
    report = {"experiment": "CNEH-EXP-03C", "status": status, "worlds": len(worlds),
              "episodes": len(episodes), "exact_B_differences": sum(w["exact_B_differences"] for w in worlds),
              "first_B_counterexamples": [w["first_B_counterexample"] for w in worlds if w["first_B_counterexample"]],
              "nonvacuous_worlds": sum(w["A_probe_response"] and w["B_positive_control_response"] for w in worlds),
              "scientific_promotion_authorized": False, "independent_replication": "REPLICATION_NOT_TESTED",
              "physical_energy": "INSTRUMENT_INVALID"}
    files = {"preregistration.md": (HERE / "PREREGISTRATION.md").read_bytes(),
             "implementation.json": pinned.canonical({"runner_sha256": pinned.sha(Path(__file__).read_bytes()),
                 "gain_runner_sha256": pinned.sha(Path(gain.__file__).read_bytes()), "source": lock["source"]}),
             "episodes.json": pinned.canonical(episodes), "worlds.json": pinned.canonical(worlds),
             "verdict.json": pinned.canonical(report)}
    return files, passed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if not args.verify and (args.out.exists() or args.out.is_symlink()):
        raise FileExistsError("immutable output")
    files, passed = payload(args.source)
    if not args.verify:
        parent.write_bundle(args.out, files)
    parent.verify_payload(args.out, files)
    print(files["verdict.json"].decode().strip())
    raise SystemExit(0 if passed else 2)


if __name__ == "__main__":
    main()
