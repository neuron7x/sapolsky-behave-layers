"""EXP03B: new gain-intervention cohort, no scientific promotion."""
from __future__ import annotations

import argparse
import copy
import importlib
import math
from pathlib import Path
from typing import Any

from experiments.cneh_exp_03 import post_primary_audit as temporal
from experiments.cneh_exp_03 import run as parent

HERE = Path(__file__).resolve().parent
pinned = parent.pinned
POLICIES = ("ENDOGENOUS", "PRE_INTERVENTION_CLAMP")
ARMS = parent.ARMS


def protocol() -> dict[str, Any]:
    p = pinned.strict_json((HERE / "gain_protocol.json").read_bytes())
    if (p["experiment"] != "CNEH-EXP-03B"
        or p["seeds"] != list(range(83001, 83009))
        or tuple(p["gain_policies"]) != POLICIES
        or tuple(p["structural_probe_arms"]) != ARMS
        or p["scientific_promotion_authorized"] is not False):
        raise ValueError("unregistered experiment or cohort")
    n = p["network"]
    if n["neurons"] != 32 or n["steps"] != 1000 or n["intervention_tick"] != 400:
        raise ValueError("unregistered network envelope")
    if sorted(p["populations"]["A"] + p["populations"]["B"]) != list(range(32)):
        raise ValueError("invalid population partition")
    return p


def probe(p: dict[str, Any]) -> list[float]:
    n, stim = p["network"], p["input"]
    original = [stim["amplitude_pA"] * math.sin(2 * math.pi * i / stim["period_ticks"])
                for i in range(n["steps"] - n["intervention_tick"])]
    temporal.probe_diagnostics(original, stim["base_pA"], stim["bound_pA"], n["dt_ms"])
    return temporal.mean_free_reference(original)


def arrival_oracle(net: Any, np: Any, network: Any, a: list[int], b: list[int]) -> dict[str, Any]:
    """Independent reconstruction of the pinned reference step's conductances."""
    e = net.W_exc.to_dense()
    i = net.W_inh.to_dense()
    sp = net.state.spiked
    ae = [j for j in a if j < net.nE]
    ai = [j - net.nE for j in a if j >= net.nE]
    se, si = sp[:net.nE], sp[net.nE:]
    # Independent scalar sums: do not delegate to the simulator's apply().
    exc = np.array([math.fsum(float(e[k, j]) for j in range(net.nE) if se[j])
                    for k in range(net.np.N)], dtype=np.float64)
    inh = np.array([math.fsum(float(i[k, j]) for j in range(net.nI) if si[j])
                    for k in range(net.np.N)], dtype=np.float64)
    ab_e = math.fsum(float(e[k, j]) for k in b for j in ae if se[j])
    ab_i = math.fsum(float(i[k, j]) for k in b for j in ai if si[j])
    rng = copy.deepcopy(net.rng)
    ext = (rng.random(net.np.N) < net.np.ext_rate_hz * net.dt_ms / 1000.).astype(float) * net.np.ext_w_nS
    dt = net.dt_ms
    ampa = (net.g_ampa + network.AMPA_FRACTION * exc + network.AMPA_FRACTION * ext) * math.exp(-dt / net.syn.tau_AMPA_ms)
    nmda = (net.g_nmda + network.NMDA_FRACTION * exc + network.NMDA_FRACTION * ext) * math.exp(-dt / net.syn.tau_NMDA_ms)
    gabaa = (net.g_gabaa + inh) * math.exp(-dt / net.syn.tau_GABAA_ms)
    return {"conductances": (ampa, nmda, gabaa), "rng": pinned.sha(pinned.canonical(rng.bit_generator.state)),
            "ab_e": ab_e, "ab_i": ab_i}


def check_delivery(actual: tuple[Any, ...], expected: tuple[Any, ...], np: Any,
                   atol: float, rtol: float) -> float:
    if len(actual) != 3 or len(expected) != 3:
        raise ValueError("conductance roster mismatch")
    residual = 0.
    for x, y in zip(actual, expected, strict=True):
        if x.shape != y.shape or not np.isfinite(x).all() or not np.isfinite(y).all():
            raise ValueError("invalid conductance")
        if not np.allclose(x, y, atol=atol, rtol=rtol):
            raise ValueError("actual synaptic conductance update disagrees with independent oracle")
        residual = max(residual, float(np.max(np.abs(x - y))))
    return residual


def check_current(actual: Any, external: Any, gain: float, scale: float, np: Any) -> None:
    if not math.isfinite(gain) or not np.array_equal(actual, scale * (gain - 1.) + external):
        raise ValueError("applied current does not match gain intervention")


def episode(seed: int, arm: str, policy: str, p: dict[str, Any],
            wave: list[float], rt: dict[str, Any]) -> dict[str, Any]:
    np, network, config = (rt[k] for k in ("np", "network", "config"))
    n, stim = p["network"], p["input"]
    a, b = p["populations"]["A"], p["populations"]["B"]
    t0 = n["intervention_tick"]
    net = network.Network(network.NetworkParams(N=32, frac_inhib=.25, p_conn=n["p_conn"]),
                          config.AdExParams(), config.SynapseParams(), config.CriticalityParams(),
                          dt_ms=n["dt_ms"], rng=np.random.default_rng(seed), backend="reference")
    if net.nE != 24 or net._use_torch:
        raise ValueError("incorrect reference network")
    connectivity = importlib.import_module("bnsyn.connectivity").SparseConnectivity
    trace = []
    clamp_gain = None
    witness = None
    max_residual = 0.
    for tick in range(n["steps"]):
        if tick == t0:
            clamp_gain = float(net.gain)
            e0, i0 = net.W_exc.to_dense(), net.W_inh.to_dense()
            e, i, witness = parent.cut_weights(e0, i0, a, b, net.nE, np, cut=arm.startswith("CUT_"))
            witness["before"] = parent.matrix_digest(e0, i0)
            net.W_exc, net.W_inh = connectivity(e, force_format="dense"), connectivity(i, force_format="dense")
            witness["after"] = parent.matrix_digest(net.W_exc.to_dense(), net.W_inh.to_dense())
            if (witness["before"] != witness["after"]) != arm.startswith("CUT_"):
                raise ValueError("structural assignment not realized")
        if tick >= t0 and policy == "PRE_INTERVENTION_CLAMP":
            net.gain = clamp_gain
        applied = float(net.gain)
        u = np.full(32, float(stim["base_pA"]), dtype=np.float64)
        if tick >= t0 and arm.endswith("PROBE_A"):
            u[a] += wave[tick - t0]
        if not np.isfinite(u).all() or np.any(u < 0) or np.any(u > stim["bound_pA"]):
            raise ValueError("invalid external input")
        oracle = arrival_oracle(net, np, network, a, b)
        if tick >= t0 and arm.startswith("CUT_") and (oracle["ab_e"] or oracle["ab_i"]):
            raise ValueError("direct post-cut arrival")
        metrics = net.step(external_current_pA=u)
        if not all(math.isfinite(float(v)) for v in metrics.values()):
            raise ValueError("nonfinite metrics")
        check_current(net._I_ext_buffer, u, applied, network.GAIN_CURRENT_SCALE_PA, np)
        residual = check_delivery((net.g_ampa, net.g_nmda, net.g_gabaa), oracle["conductances"], np,
                                  p["verification"]["conductance_atol_nS"], p["verification"]["conductance_rtol"])
        max_residual = max(max_residual, residual)
        rng = pinned.sha(pinned.canonical(net.rng.bit_generator.state))
        if rng != oracle["rng"]:
            raise ValueError("unexpected exogenous random draw")
        bits = [int(v) for v in net.state.spiked]
        trace.append({"tick": tick, "spike_bits": bits,
                      "spikes_A": sum(bits[j] for j in a), "spikes_B": sum(bits[j] for j in b),
                      "mean_voltage_B_mV": float(np.mean(net.state.V_mV[b])).hex(),
                      "direct_A_pA": float(u[a[0]]).hex(), "direct_B_pA": float(u[b[0]]).hex(),
                      "applied_gain": applied.hex(), "proposed_gain": float(net.gain).hex(),
                      "AB_exc_arrival_nS": oracle["ab_e"], "AB_inh_arrival_nS": oracle["ab_i"],
                      "state_sha256": parent.physical_state_digest(net, np), "rng_sha256": rng})
    if witness is None or clamp_gain is None or parent.matrix_digest(net.W_exc.to_dense(), net.W_inh.to_dense()) != witness["after"]:
        raise ValueError("missing or drifting structural intervention")
    return {"seed": seed, "arm": arm, "gain_policy": policy, "clamp_gain": clamp_gain.hex(),
            "structure": witness, "max_conductance_oracle_residual_nS": max_residual,
            "trace": trace, "trace_sha256": pinned.sha(pinned.canonical(trace))}


def paired_world(rows: list[dict[str, Any]], p: dict[str, Any]) -> dict[str, Any]:
    n, stim = p["network"], p["input"]
    t0 = n["intervention_tick"]
    b = p["populations"]["B"]
    by = {(e["gain_policy"], e["arm"]): e for e in rows}
    if len(rows) != 8 or set(by) != {(g, a) for g in POLICIES for a in ARMS} or len({r["seed"] for r in rows}) != 1:
        raise ValueError("incomplete factorial world")
    ref = by[(POLICIES[0], ARMS[0])]
    clamp = ref["clamp_gain"]
    wave = probe(p)
    for (policy, arm), e in by.items():
        tr = e["trace"]
        if [x["tick"] for x in tr] != list(range(n["steps"])) or e["trace_sha256"] != pinned.sha(pinned.canonical(tr)):
            raise ValueError("invalid trace")
        if tr[:t0] != ref["trace"][:t0] or e["clamp_gain"] != clamp:
            raise ValueError("pre-intervention divergence")
        if [x["rng_sha256"] for x in tr] != [x["rng_sha256"] for x in ref["trace"]]:
            raise ValueError("exogenous RNG divergence")
        for tick, x in enumerate(tr):
            bits = x["spike_bits"]
            if len(bits) != 32 or any(type(v) is not int or v not in (0, 1) for v in bits):
                raise ValueError("invalid individual spike vector")
            if x["spikes_B"] != sum(bits[j] for j in b) or x["spikes_A"] != sum(bits[j] for j in p["populations"]["A"]):
                raise ValueError("population count differs from individual spike vector")
            a_expected = float(stim["base_pA"])
            if tick >= t0 and arm.endswith("PROBE_A"):
                a_expected += wave[tick - t0]
            if x["direct_A_pA"] != a_expected.hex() or x["direct_B_pA"] != float(stim["base_pA"]).hex():
                raise ValueError("direct input mismatch")
            if tick >= t0:
                if policy == POLICIES[1] and x["applied_gain"] != clamp:
                    raise ValueError("gain clamp mismatch")
                if arm.startswith("CUT_") and (x["AB_exc_arrival_nS"] != 0 or x["AB_inh_arrival_nS"] != 0):
                    raise ValueError("cut path carries new arrivals")
        if e["structure"]["cut"] != arm.startswith("CUT_") or not e["structure"]["off_target_unchanged"]:
            raise ValueError("invalid structure witness")
    out = {}
    for policy in POLICIES:
        traces = {arm: by[(policy, arm)]["trace"][t0:] for arm in ARMS}
        counts = temporal.temporal_contrast({arm: [x["spikes_B"] for x in tr] for arm, tr in traces.items()})
        neurons = {str(j): temporal.temporal_contrast({arm: [x["spike_bits"][j] for x in tr]
                                                     for arm, tr in traces.items()}) for j in b}
        d = counts["instantaneous_factorial_counts"]
        if d != [sum(v["instantaneous_factorial_counts"][t] for v in neurons.values()) for t in range(len(d))]:
            raise ValueError("neuron-to-population contrast mismatch")
        voltage = parent.interaction({arm: math.fsum(float.fromhex(x["mean_voltage_B_mV"]) for x in tr) / len(tr)
                                      for arm, tr in traces.items()})
        out[policy] = {"counts": counts, "neurons": neurons, "mean_voltage_factorial_mV": voltage,
                       "intact_arrival_positive": {arm: any(x["AB_exc_arrival_nS"] or x["AB_inh_arrival_nS"] for x in traces[arm])
                                                   for arm in ARMS[:2]},
                       "max_oracle_residual_nS": max(by[(policy, arm)]["max_conductance_oracle_residual_nS"] for arm in ARMS)}
    contrast = [x - y for x, y in zip(out[POLICIES[0]]["counts"]["instantaneous_factorial_counts"],
                                      out[POLICIES[1]]["counts"]["instantaneous_factorial_counts"], strict=True)]
    return {"seed": ref["seed"], "policies": out, "gain_policy_difference": contrast,
            "gain_policy_difference_l1": sum(abs(x) for x in contrast),
            "gain_policy_difference_nonzero": any(contrast)}


def payload(source: Path) -> dict[str, bytes]:
    p = protocol()
    contract_path = HERE.parent / "cneh_exp_01" / "bnsyn_integration_contract.json"
    lock = pinned.strict_json(contract_path.read_bytes())
    if lock["source"]["commit"] != p["bnsyn_commit"]:
        raise ValueError("pinned simulator drift")
    before = pinned.validate_source(source, lock)
    rt = pinned.load_runtime(source, lock)
    wave = probe(p)
    episodes, worlds = [], []
    for seed in p["seeds"]:
        rows = [episode(seed, arm, policy, p, wave, rt) for policy in POLICIES for arm in ARMS]
        worlds.append(paired_world(rows, p))
        episodes.extend(rows)
    if pinned.validate_source(source, lock) != before:
        raise ValueError("simulator source changed")
    summary = {"experiment": p["experiment"], "worlds": len(worlds), "episodes": len(episodes),
               "gain_policy_difference_worlds": sum(w["gain_policy_difference_nonzero"] for w in worlds),
               "mean_peak_cumulative_count": {
                   policy: math.fsum(w["policies"][policy]["counts"]["max_abs_cumulative_factorial_count"] for w in worlds) / len(worlds)
                   for policy in POLICIES},
               "max_conductance_oracle_residual_nS": max(w["policies"][g]["max_oracle_residual_nS"] for w in worlds for g in POLICIES),
               "intact_worlds_with_arrival": {g: sum(any(w["policies"][g]["intact_arrival_positive"].values()) for w in worlds)
                                               for g in POLICIES},
               "scientific_promotion_authorized": False, "independent_replication": "REPLICATION_NOT_TESTED",
               "physical_energy": "INSTRUMENT_INVALID", "authority": "DESCRIPTIVE_SIMULATOR_INTERVENTION_ONLY",
               "direct_mediation_established": False}
    return {"protocol.json": (HERE / "gain_protocol.json").read_bytes(),
            "preregistration.md": (HERE / "gain_preregistration.md").read_bytes(),
            "implementation.json": pinned.canonical({"runner_sha256": pinned.sha(Path(__file__).read_bytes()),
                                                     "parent_runner_sha256": pinned.sha(Path(parent.__file__).read_bytes()),
                                                     "parent_audit_sha256": pinned.sha(Path(temporal.__file__).read_bytes()),
                                                     "runtime_contract_sha256": pinned.sha(contract_path.read_bytes()),
                                                     "source": lock["source"], "dependencies": lock["dependencies"]}),
            "episodes.json": pinned.canonical(episodes), "diagnostics.json": pinned.canonical(worlds),
            "verdict.json": pinned.canonical(summary)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if not args.verify and args.out.exists():
        raise FileExistsError("immutable output")
    result = payload(args.source)
    if not args.verify:
        parent.write_bundle(args.out, result)
    parent.verify_payload(args.out, result)
    print(result["verdict.json"].decode().strip())


if __name__ == "__main__":
    main()
