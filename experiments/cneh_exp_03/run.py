"""CNEH-EXP-03: prospective paired structural intervention in BN-Syn.

A bounded mechanistic simulator pilot. Not a learned controller, external
replication, proof of synaptic mediation, or scientific promotion.
"""
from __future__ import annotations

import argparse
import csv
import importlib
import io
import math
import struct
from pathlib import Path
from typing import Any

from experiments.cneh_exp_01 import bnsyn_adapter as pinned

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "cneh_exp_01"
ARMS = ("SHAM_BASE", "SHAM_PROBE_A", "CUT_AB_BASE", "CUT_AB_PROBE_A")
ENDPOINTS = ("B_post_spikes_per_neuron", "B_post_mean_voltage_mV")


def read_protocol() -> dict[str, Any]:
    value = pinned.strict_json((HERE / "protocol.json").read_bytes())
    if (
        value["experiment"] != "CNEH-EXP-03"
        or value["scientific_promotion_authorized"] is not False
        or value["hypothesis_status"] != "FORMALIZED / EMPIRICAL VALIDATION PENDING"
        or [a["name"] for a in value["arms"]] != list(ARMS)
    ):
        raise ValueError("frozen experiment identity or scientific authority changed")
    seeds = value["seeds"]
    n = value["network"]
    a, b = n["population_A"], n["population_B"]
    if (
        len(seeds) != 8 or len(set(seeds)) != len(seeds)
        or any(type(s) is not int for s in seeds)
        or sorted(a + b) != list(range(n["neurons"]))
        or len(a) != len(b)
        or n["neurons"] > value["limits"]["max_neurons"]
        or n["steps"] > value["limits"]["max_steps_per_episode"]
        or not 0 < n["intervention_tick"] < n["steps"]
        or len(seeds) * len(ARMS) > value["limits"]["max_episodes"]
    ):
        raise ValueError("invalid cohort, partitions or execution envelope")
    return value


def cut_weights(
    exc: Any, inh: Any, a: list[int], b: list[int], n_e: int, np: Any, *, cut: bool
) -> tuple[Any, Any, dict[str, Any]]:
    """Rows are postsynaptic, columns are local presynaptic E or I indices."""
    n = len(a) + len(b)
    if exc.shape != (n, n_e) or inh.shape != (n, n - n_e):
        raise ValueError("unexpected BN-Syn synaptic matrix orientation")
    if not (np.isfinite(exc).all() and np.isfinite(inh).all()):
        raise ValueError("nonfinite connectivity")
    if sorted(a + b) != list(range(n)) or not 0 < n_e < n:
        raise ValueError("invalid partition")
    e_a = [i for i in a if i < n_e]
    i_a = [i - n_e for i in a if i >= n_e]
    if not e_a or not i_a:
        raise ValueError("intervention must include both presynaptic cell types")
    em = np.zeros(exc.shape, dtype=bool)
    im = np.zeros(inh.shape, dtype=bool)
    em[np.ix_(b, e_a)] = True
    im[np.ix_(b, i_a)] = True
    available = int(np.count_nonzero(exc[em]) + np.count_nonzero(inh[im]))
    if available == 0:
        raise ValueError("no A-to-B edge in frozen world; cannot qualify intervention")
    new_e, new_i = exc.copy(), inh.copy()
    if cut:
        new_e[em], new_i[im] = 0.0, 0.0
    if not np.array_equal(new_e[~em], exc[~em]) or not np.array_equal(new_i[~im], inh[~im]):
        raise ValueError("off-target weight change")
    changed = int(np.count_nonzero(new_e != exc) + np.count_nonzero(new_i != inh))
    if cut and (changed != available or np.any(new_e[em]) or np.any(new_i[im])):
        raise ValueError("incomplete structural intervention")
    if not cut and (changed or new_e.tobytes() != exc.tobytes() or new_i.tobytes() != inh.tobytes()):
        raise ValueError("sham mutated connectivity")
    witness = {"available_AB_edges": available, "removed_AB_edges": changed,
               "off_target_unchanged": True, "cut": cut}
    return new_e, new_i, witness


def matrix_digest(e: Any, i: Any) -> str:
    return pinned.sha(e.astype(">f8").tobytes(order="C") + i.astype(">f8").tobytes(order="C"))


def physical_state_digest(net: Any, np: Any) -> str:
    """Exact bytes of named physical state arrays, not every simulator internal."""
    blocks = []
    for arr in (net.state.V_mV, net.state.w_pA, net.g_ampa, net.g_nmda, net.g_gabaa):
        arr = np.asarray(arr, dtype=np.float64)
        if not np.isfinite(arr).all():
            raise ValueError("nonfinite physical state")
        blocks.append(arr.astype(">f8").tobytes(order="C"))
    blocks.append(np.asarray(net.state.spiked, dtype=np.uint8).tobytes())
    if not math.isfinite(float(net.gain)):
        raise ValueError("nonfinite global gain")
    blocks.append(struct.pack(">d", float(net.gain)))
    return pinned.sha(b"".join(blocks))


def direct_currents(tick: int, arm: dict[str, Any], p: dict[str, Any]) -> tuple[float, float]:
    n, s = p["network"], p["stimulus"]
    base = float(s["base_current_pA"])
    a = base
    if arm["probe"] and tick >= n["intervention_tick"]:
        t = tick - n["intervention_tick"]
        a += float(s["probe_amplitude_pA"]) * math.sin(2 * math.pi * t / s["probe_period_ticks"])
    if not math.isfinite(a) or not 0 <= a <= s["max_current_pA"]:
        raise ValueError("unqualified direct current")
    return a, base


def episode(seed: int, arm: dict[str, Any], p: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
    np, network, config = (runtime[k] for k in ("np", "network", "config"))
    n = p["network"]
    a, b = n["population_A"], n["population_B"]
    net = network.Network(
        network.NetworkParams(N=n["neurons"], frac_inhib=n["frac_inhib"], p_conn=n["p_conn"]),
        config.AdExParams(), config.SynapseParams(), config.CriticalityParams(),
        dt_ms=n["dt_ms"], rng=np.random.default_rng(seed), backend=n["backend"],
    )
    if net.nE != 24 or len([i for i in a if i < net.nE]) != 12 or len([i for i in b if i < net.nE]) != 12:
        raise ValueError("unexpected E/I partition in frozen model")
    connectivity = importlib.import_module("bnsyn.connectivity").SparseConnectivity
    initial_e, initial_i = net.W_exc.to_dense().copy(), net.W_inh.to_dense().copy()
    initial_matrix = matrix_digest(initial_e, initial_i)
    initial_state = physical_state_digest(net, np)
    rows: list[dict[str, Any]] = []
    witness = None
    pre_a = pre_b = post_b = 0
    post_v: list[float] = []
    for tick in range(n["steps"]):
        if tick == n["intervention_tick"]:
            e, i, witness = cut_weights(net.W_exc.to_dense(), net.W_inh.to_dense(), a, b, net.nE, np, cut=arm["cut"])
            before = physical_state_digest(net, np)
            net.W_exc = connectivity(e, force_format="dense")
            net.W_inh = connectivity(i, force_format="dense")
            if physical_state_digest(net, np) != before:
                raise ValueError("intervention mutated physical state instead of weights only")
            witness.update(before_matrix_sha256=initial_matrix,
                           after_matrix_sha256=matrix_digest(net.W_exc.to_dense(), net.W_inh.to_dense()))
            if (witness["after_matrix_sha256"] != initial_matrix) != arm["cut"]:
                raise ValueError("structural digest does not match intervention assignment")
        u_a, u_b = direct_currents(tick, arm, p)
        current = np.full(n["neurons"], u_b, dtype=np.float64)
        current[a] = u_a
        metrics = net.step(external_current_pA=current)
        if any(not math.isfinite(float(v)) for v in metrics.values()):
            raise ValueError("nonfinite BN-Syn metric")
        a_spikes = int(np.sum(net.state.spiked[a]))
        b_spikes = int(np.sum(net.state.spiked[b]))
        voltage_b = float(np.mean(net.state.V_mV[b]))
        if tick < n["intervention_tick"]:
            pre_a += a_spikes
            pre_b += b_spikes
        else:
            post_b += b_spikes
            post_v.append(voltage_b)
        rows.append({"tick": tick, "u_A_pA": u_a.hex(), "u_B_pA": u_b.hex(),
                     "spikes_A": a_spikes, "spikes_B": b_spikes,
                     "mean_voltage_B_mV": voltage_b.hex(),
                     "state_sha256": physical_state_digest(net, np),
                     "rng_sha256": pinned.sha(pinned.canonical(net.rng.bit_generator.state))})
    if witness is None:
        raise ValueError("missing structural intervention")
    if matrix_digest(net.W_exc.to_dense(), net.W_inh.to_dense()) != witness["after_matrix_sha256"]:
        raise ValueError("unexpected connectivity drift after intervention")
    return {
        "seed": seed, "arm": arm["name"], "initial_state_sha256": initial_state,
        "initial_matrix_sha256": initial_matrix, "structure": witness,
        "pre_spikes_A": pre_a, "pre_spikes_B": pre_b,
        "B_post_spikes_per_neuron": post_b / len(b),
        "B_post_mean_voltage_mV": math.fsum(post_v) / len(post_v),
        "trace": rows, "trace_sha256": pinned.sha(pinned.canonical(rows)),
    }


def interaction(outcomes: dict[str, float]) -> float:
    if set(outcomes) != set(ARMS) or any(not math.isfinite(x) for x in outcomes.values()):
        raise ValueError("incomplete/nonfinite factorial observations")
    return (outcomes["SHAM_PROBE_A"] - outcomes["SHAM_BASE"]) - (
        outcomes["CUT_AB_PROBE_A"] - outcomes["CUT_AB_BASE"]
    )


def verify_world(episodes: list[dict[str, Any]], p: dict[str, Any]) -> dict[str, Any]:
    by_arm = {e["arm"]: e for e in episodes}
    if len(episodes) != 4 or set(by_arm) != set(ARMS) or len({e["seed"] for e in episodes}) != 1:
        raise ValueError("incomplete paired world")
    n = p["network"]
    pre = n["intervention_tick"]
    base = by_arm["SHAM_BASE"]
    for name, ep in by_arm.items():
        rows = ep["trace"]
        if len(rows) != n["steps"] or [r["tick"] for r in rows] != list(range(n["steps"])):
            raise ValueError("incomplete time grid")
        if ep["initial_state_sha256"] != base["initial_state_sha256"] or ep["initial_matrix_sha256"] != base["initial_matrix_sha256"]:
            raise ValueError("different initial world across arms")
        if rows[:pre] != base["trace"][:pre]:
            raise ValueError("pre-intervention leakage or state divergence")
        if [r["rng_sha256"] for r in rows] != [r["rng_sha256"] for r in base["trace"]]:
            raise ValueError("exogenous random tape mismatch")
        if [r["u_B_pA"] for r in rows] != [r["u_B_pA"] for r in base["trace"]]:
            raise ValueError("direct receiver input confound")
        declared_arm = next(a for a in p["arms"] if a["name"] == name)
        for tick, row in enumerate(rows):
            ua, ub = direct_currents(tick, declared_arm, p)
            if row["u_A_pA"] != ua.hex() or row["u_B_pA"] != ub.hex():
                raise ValueError("input differs from frozen intervention")
        if ep["trace_sha256"] != pinned.sha(pinned.canonical(rows)):
            raise ValueError("trace digest mismatch")
        observed_spikes = sum(row["spikes_B"] for row in rows[pre:]) / len(n["population_B"])
        observed_voltage = math.fsum(float.fromhex(row["mean_voltage_B_mV"]) for row in rows[pre:]) / (n["steps"] - pre)
        if ep[ENDPOINTS[0]] != observed_spikes or ep[ENDPOINTS[1]] != observed_voltage:
            raise ValueError("derived endpoint does not agree with raw trace")
        if ep["pre_spikes_A"] != sum(row["spikes_A"] for row in rows[:pre]) or ep["pre_spikes_B"] != sum(row["spikes_B"] for row in rows[:pre]):
            raise ValueError("pre-intervention spike summary mismatch")
        expected_cut = name.startswith("CUT_")
        w = ep["structure"]
        if w["cut"] is not expected_cut or w["off_target_unchanged"] is not True or w["available_AB_edges"] <= 0:
            raise ValueError("invalid intervention witness")
        if w["removed_AB_edges"] != (w["available_AB_edges"] if expected_cut else 0):
            raise ValueError("wrong number of removed edges")
    active = base["pre_spikes_A"] > 0 and base["pre_spikes_B"] > 0
    return {
        "seed": base["seed"], "pre_spiking_qualified": active,
        "pre_spikes_A": base["pre_spikes_A"], "pre_spikes_B": base["pre_spikes_B"],
        "pre_intervention_parity": True, "rng_parity": True,
        "direct_receiver_input_parity": True, "intervention_witness_valid": True,
        "contrasts": {k: interaction({arm: e[k] for arm, e in by_arm.items()}) for k in ENDPOINTS},
        "arm_endpoints": {arm: {k: e[k] for k in ENDPOINTS} for arm, e in by_arm.items()},
    }


def payload(source: Path) -> dict[str, bytes]:
    p = read_protocol()
    contract = pinned.strict_json((PARENT / "bnsyn_integration_contract.json").read_bytes())
    if contract["source"]["commit"] != p["bnsyn_source_commit"]:
        raise ValueError("BN-Syn source contract drift")
    source_before = pinned.validate_source(source, contract)
    runtime = pinned.load_runtime(source, contract)
    all_episodes = []
    worlds = []
    for seed in p["seeds"]:
        eps = [episode(seed, arm, p, runtime) for arm in p["arms"]]
        worlds.append(verify_world(eps, p))
        all_episodes.extend(eps)
    if pinned.validate_source(source, contract) != source_before:
        raise ValueError("external simulator source drift during execution")
    active = all(w["pre_spiking_qualified"] for w in worlds)
    report = {
        "experiment": p["experiment"], "n_worlds": len(worlds), "n_episodes": len(all_episodes),
        "worlds": worlds,
        "mean_factorial_contrasts": {k: math.fsum(w["contrasts"][k] for w in worlds) / len(worlds) for k in ENDPOINTS},
        "all_pre_spiking_qualified": active,
        "authority": "INTERNAL_SIMULATOR_MECHANISM_ONLY",
        "scientific_promotion_authorized": False,
        "direct_synaptic_mediation_established": False,
        "global_criticality_feedback_retained": True,
    }
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["seed", "pre_spiking_qualified", *ENDPOINTS])
    for w in worlds:
        writer.writerow([w["seed"], w["pre_spiking_qualified"], *(w["contrasts"][k] for k in ENDPOINTS)])
    return {
        "protocol.json": (HERE / "protocol.json").read_bytes(),
        "preregistration.md": (HERE / "PREREGISTRATION.md").read_bytes(),
        "implementation.json": pinned.canonical({
            "runner_sha256": pinned.sha(Path(__file__).read_bytes()),
            "parent_adapter_sha256": pinned.sha((PARENT / "bnsyn_adapter.py").read_bytes()),
            "parent_runtime_contract_sha256": pinned.sha((PARENT / "bnsyn_integration_contract.json").read_bytes()),
            "bnsyn_source": contract["source"], "dependencies": contract["dependencies"],
        }),
        "episodes.json": pinned.canonical(all_episodes),
        "paired_contrasts.csv": buffer.getvalue().encode(),
        "diagnostics.json": pinned.canonical(report),
        "verdict.json": pinned.canonical({
            "experiment": p["experiment"], "verdict": "STRUCTURAL_INTERVENTION_PILOT_EXECUTED"
            if active else "SPIKING_REGIME_UNQUALIFIED",
            "scientific_status": p["hypothesis_status"],
            "independent_replication": "REPLICATION_NOT_TESTED",
            "physical_energy": "INSTRUMENT_INVALID",
            "scientific_promotion_authorized": False,
        }),
    }


def manifest(files: dict[str, bytes]) -> bytes:
    return "".join(f"{pinned.sha(files[k])}  {k}\n" for k in sorted(files)).encode("ascii")


def write_bundle(out: Path, files: dict[str, bytes]) -> None:
    out.mkdir(parents=True, exist_ok=False)
    for name, data in files.items():
        (out / name).write_bytes(data)
    (out / "SHA256SUMS").write_bytes(manifest(files))


def verify_payload(out: Path, expected: dict[str, bytes]) -> None:
    if out.is_symlink() or not out.is_dir():
        raise ValueError("invalid evidence directory")
    entries = list(out.iterdir())
    if any(x.is_symlink() or not x.is_file() for x in entries):
        raise ValueError("unexpected evidence member")
    if {x.name for x in entries} != set(expected) | {"SHA256SUMS"}:
        raise ValueError("evidence roster mismatch")
    if (out / "SHA256SUMS").read_bytes() != manifest(expected):
        raise ValueError("evidence manifest differs from deterministic replay")
    for k, data in expected.items():
        if (out / k).read_bytes() != data:
            raise ValueError(f"evidence differs from deterministic replay: {k}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if not args.verify and (args.out.exists() or args.out.is_symlink()):
        raise FileExistsError("refuse to overwrite a prior evidence bundle")
    result = payload(args.source)
    if not args.verify:
        write_bundle(args.out, result)
    verify_payload(args.out, result)
    print(result["verdict.json"].decode().strip())
    print(result["diagnostics.json"].decode().strip())


if __name__ == "__main__":
    main()
