"""EXP04B: observation-only neural pathway reidentification in pinned BN-Syn."""
from __future__ import annotations

import argparse
import gzip
import importlib
import itertools
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from experiments.cneh_exp_03 import gain_intervention as gain
from experiments.cneh_exp_03 import run as parent

HERE = Path(__file__).resolve().parent
pinned = parent.pinned
B = tuple(range(16))
GROUPS = (tuple(range(24, 28)), tuple(range(28, 32)))
MODES = ((1, 0), (0, 1), (1, 1), (0, 0))
ARMS = ("ACTIVE_REID", "EXACT_EMULATOR", "PERIODIC_REID", "STATIC_NOMINAL", "ORACLE")
SEEDS = tuple(range(86001, 86013)) + tuple(range(86101, 86105))
STEPS = 1600
DT = .1
DECAY = math.exp(-DT / 6.)
WEIGHT = .5
TOL = 1e-9
GOAL = .5


@dataclass(frozen=True)
class Observation:
    tick: int
    gaba: tuple[float, ...]
    source_bits: tuple[int, ...]

    def __post_init__(self) -> None:
        if type(self.tick) is not int or not 0 <= self.tick <= STEPS:
            raise ValueError("invalid observation tick")
        if len(self.gaba) != len(B) or any(not math.isfinite(x) or x < 0 for x in self.gaba):
            raise ValueError("invalid receiver conductance observation")
        if len(self.source_bits) != 8 or any(type(x) is not int or x not in (0, 1) for x in self.source_bits):
            raise ValueError("invalid source spike observation")

    @property
    def counts(self) -> tuple[int, int]:
        return sum(self.source_bits[:4]), sum(self.source_bits[4:])


def residual(previous: Observation, current: Observation) -> tuple[float, ...]:
    if current.tick != previous.tick + 1:
        raise ValueError("nonconsecutive observation")
    return tuple(y - DECAY * x for x, y in zip(previous.gaba, current.gaba, strict=True))


def prediction(mode: int, counts: tuple[int, int]) -> float:
    c = MODES[mode]
    return DECAY * WEIGHT * (c[0] * counts[0] + c[1] * counts[1])


def compatible(candidates: tuple[int, ...], previous: Observation, current: Observation) -> tuple[int, ...]:
    if not candidates or len(set(candidates)) != len(candidates) or any(type(i) is not int or not 0 <= i < 4 for i in candidates):
        raise ValueError("invalid model set")
    r = residual(previous, current)
    return tuple(i for i in candidates if all(abs(x - prediction(i, previous.counts)) <= TOL for x in r))


def distinguishing_group(candidates: tuple[int, ...]) -> int:
    if len(candidates) < 2:
        raise ValueError("no ambiguity to resolve")
    scores = [sum(MODES[i][g] != MODES[j][g] for i, j in itertools.combinations(candidates, 2))
              for g in range(2)]
    if max(scores) == 0:
        raise ValueError("unidentifiable candidate family")
    return 0 if scores[0] >= scores[1] else 1


def sentinel(tick: int) -> int | None:
    return (tick // 200) % 2 if tick % 200 < 100 else None


def known_action(mode: int, obs: Observation) -> tuple[int | None, str]:
    scheduled = sentinel(obs.tick)
    if scheduled is not None:
        return scheduled, "SENTINEL"
    connected = [i for i, bit in enumerate(MODES[mode]) if bit]
    if not connected:
        return None, "DISCONNECTED_ABSTAIN"
    if math.fsum(obs.gaba) / len(B) < GOAL:
        return connected[0], "TRACK"
    return None, "TRACK_IDLE"


class Policy:
    """No plant object, seed, true topology, future tape, or hidden change time."""
    def __init__(self, arm: str):
        if arm not in ARMS[:-1]:
            raise ValueError("unregistered observation-only policy")
        self.arm = arm
        self.candidates = (0,)
        self.detected: int | None = None
        self.identified: int | None = None
        self.prev: Observation | None = None

    def observe(self, obs: Observation) -> None:
        if self.prev is None:
            if obs.tick != 0:
                raise ValueError("missing initial observation")
        else:
            if obs.tick != self.prev.tick + 1:
                raise ValueError("nonconsecutive observation")
            if self.arm != "STATIC_NOMINAL":
                if self.detected is None:
                    if not compatible((0,), self.prev, obs):
                        self.detected = obs.tick
                        self.candidates = compatible(tuple(range(4)), self.prev, obs)
                else:
                    self.candidates = compatible(self.candidates, self.prev, obs)
                if not self.candidates:
                    raise ValueError("MODEL_SET_VIOLATION")
                if self.detected is not None and self.identified is None and len(self.candidates) == 1:
                    self.identified = obs.tick
        self.prev = obs

    def act(self) -> tuple[int | None, str]:
        if self.prev is None or self.prev.tick == STEPS:
            raise ValueError("no current control tick")
        if len(self.candidates) == 1:
            return known_action(self.candidates[0], self.prev)
        if self.arm in ARMS[:2]:
            return distinguishing_group(self.candidates), "ACTIVE_PROBE"
        scheduled = sentinel(self.prev.tick)
        return (scheduled, "SENTINEL") if scheduled is not None else (None, "AMBIGUOUS_ABSTAIN")


def world(seed: int) -> dict[str, int | None]:
    if seed not in SEEDS:
        raise ValueError("unregistered world")
    if seed >= 86101:
        return {"seed": seed, "tau": None, "mode": 0}
    return {"seed": seed, "tau": random.Random(seed).randint(550, 750),
            "mode": 1 + (seed - 86001) % 3}


def apply_mode(net: Any, mode: int, np: Any, connectivity: Any) -> str:
    e = np.zeros((32, 24), dtype=np.float64)
    i = np.zeros((32, 8), dtype=np.float64)
    for group, enabled in enumerate(MODES[mode]):
        if enabled:
            i[np.ix_(list(B), list(range(group * 4, group * 4 + 4)))] = WEIGHT
    net.W_exc = connectivity(e, force_format="dense")
    net.W_inh = connectivity(i, force_format="dense")
    if not np.array_equal(net.W_exc.to_dense(), e) or not np.array_equal(net.W_inh.to_dense(), i):
        raise ValueError("topology intervention not realized")
    return parent.matrix_digest(e, i)


def read_obs(net: Any, tick: int) -> Observation:
    return Observation(tick, tuple(float(net.g_gabaa[j]) for j in B),
                       tuple(int(net.state.spiked[j]) for group in GROUPS for j in group))


def obs_record(obs: Observation) -> dict:
    return {"tick": obs.tick, "gaba": [v.hex() for v in obs.gaba], "source_bits": list(obs.source_bits)}


def parse_obs(row: dict) -> Observation:
    return Observation(row["tick"], tuple(float.fromhex(v) for v in row["gaba"]), tuple(row["source_bits"]))


def audit_policy_tape(trace: list[dict], arm: str) -> None:
    """Reconstruct actions from the public tape only, using a fresh policy."""
    if arm == "ORACLE":
        raise ValueError("oracle not an observation-only policy")
    policy = Policy(arm)
    for row in trace:
        obs = parse_obs(row)
        policy.observe(obs)
        if row["candidates"] != list(policy.candidates) or row["detected"] != policy.detected or row["identified"] != policy.identified:
            raise ValueError("candidate history differs from observation-only replay")
        if obs.tick != STEPS:
            group, kind = policy.act()
            if row["group"] != group or row["kind"] != kind:
                raise ValueError("action differs from observation-only replay")


def episode(w: dict, arm: str, rt: dict) -> dict:
    np, network, config = (rt[k] for k in ("np", "network", "config"))
    seed, tau, changed = w["seed"], w["tau"], w["mode"]
    net = network.Network(network.NetworkParams(N=32, frac_inhib=.25, p_conn=0.),
                          config.AdExParams(), config.SynapseParams(), config.CriticalityParams(),
                          dt_ms=DT, rng=np.random.default_rng(seed), backend="reference")
    if net.nE != 24 or net.nI != 8 or net._use_torch or net.syn.tau_GABAA_ms != 6.:
        raise ValueError("unregistered simulator boundary")
    connectivity = importlib.import_module("bnsyn.connectivity").SparseConnectivity
    matrix_sha = apply_mode(net, 0, np, connectivity)
    policy = None if arm == "ORACLE" else Policy(arm)
    trace: list[dict] = []
    previous = None
    previous_mode = 0
    max_residual = 0.
    try:
        for tick in range(STEPS + 1):
            obs = read_obs(net, tick)
            if previous is not None:
                r = residual(previous, obs)
                pred = prediction(previous_mode, previous.counts)
                max_residual = max(max_residual, max(abs(x - pred) for x in r))
                if any(abs(x - pred) > TOL for x in r):
                    raise ValueError("actual receiver conductance violates evaluator oracle")
            mode = changed if tau is not None and tick >= tau else 0
            if policy is not None:
                policy.observe(obs)
                if policy.detected is not None and previous_mode not in policy.candidates:
                    raise ValueError("true mode eliminated")
                if policy.detected is not None and (tau is None or policy.detected <= tau):
                    raise ValueError("false or premature detection")
            row = {**obs_record(obs), "B_voltage_mV": [float(net.state.V_mV[j]).hex() for j in B],
                   "state_sha256": parent.physical_state_digest(net, np),
                   "rng_sha256": pinned.sha(pinned.canonical(net.rng.bit_generator.state)),
                   "evaluator_mode": mode,
                   "candidates": None if policy is None else list(policy.candidates),
                   "detected": None if policy is None else policy.detected,
                   "identified": None if policy is None else policy.identified}
            if tick == STEPS:
                trace.append(row)
                break
            if tick == tau:
                before = parent.physical_state_digest(net, np)
                matrix_sha = apply_mode(net, mode, np, connectivity)
                if parent.physical_state_digest(net, np) != before:
                    raise ValueError("structural change modified physical state")
            group, kind = known_action(mode, obs) if policy is None else policy.act()
            if group not in (None, 0, 1):
                raise ValueError("unauthorized actuator")
            u = np.zeros(32, dtype=np.float64)
            u[list(B)] = 300.
            if group is not None:
                u[list(GROUPS[group])] = 500.
            # Applied gain is exactly common; native proposed gain is not applied.
            net.gain = 1.
            row.update(group=group, kind=kind, applied_gain=(1.).hex(),
                       topology_sha256=matrix_sha, direct_B_pA=(300.).hex(),
                       source_group_inputs_pA=[500. if group == j else 0. for j in range(2)])
            trace.append(row)
            metrics = net.step(external_current_pA=u)
            if any(not math.isfinite(float(v)) for v in metrics.values()):
                raise ValueError("nonfinite metric")
            gain.check_current(net._I_ext_buffer, u, 1., network.GAIN_CURRENT_SCALE_PA, np)
            if parent.matrix_digest(net.W_exc.to_dense(), net.W_inh.to_dense()) != matrix_sha:
                raise ValueError("unexpected recurrent route drift")
            previous, previous_mode = obs, mode
        if policy is not None:
            audit_policy_tape(trace, arm)
        start = 0 if tau is None else tau + 1
        after = trace[start:]
        final = None if policy is None else list(policy.candidates)
        identified = policy is not None and policy.identified is not None
        status = ("ORACLE_DIAGNOSTIC" if policy is None else "STATIC_NOMINAL_ONLY" if arm == "STATIC_NOMINAL"
                  else "NO_CHANGE" if tau is None else "UNRESOLVED" if not identified
                  else "IDENTIFIED_DISCONNECTED" if final == [3] else "IDENTIFIED_REACHABLE")
        if identified and final != [changed]:
            raise ValueError("wrong singleton")
        return {"seed": seed, "arm": arm, "status": status, "valid": True,
                "detected": None if policy is None else policy.detected,
                "identified": None if policy is None else policy.identified,
                "final_candidates": final, "max_gaba_residual_nS": max_residual,
                "post_mean_abs_gaba_error_nS": math.fsum(abs(float.fromhex(v) - GOAL) for r in after for v in r["gaba"]) / (len(after) * len(B)),
                "source_current_l1_pA_ticks": 4 * 500 * sum(r.get("group") is not None for r in trace),
                "source_spikes": sum(sum(r["source_bits"]) for r in trace[1:]),
                "trace": trace}
    except (ValueError, RuntimeError) as exc:
        return {"seed": seed, "arm": arm, "status": "INSTRUMENT_INVALID", "valid": False,
                "failure": str(exc), "failure_tick": tick, "trace": trace}


def pair(w: dict, episodes: list[dict]) -> dict:
    if len(episodes) != len(ARMS) or {e["arm"] for e in episodes} != set(ARMS):
        raise ValueError("incomplete world arms")
    by = {e["arm"]: e for e in episodes}
    if any(not e["valid"] for e in episodes):
        return {**w, "valid": False, "reason": "episode invalid"}
    def without_arm(e: dict) -> dict:
        return {k: v for k, v in e.items() if k != "arm"}
    if without_arm(by[ARMS[0]]) != without_arm(by[ARMS[1]]):
        return {**w, "valid": False, "reason": "exact emulator divergence"}
    rng = [r["rng_sha256"] for r in by[ARMS[0]]["trace"]]
    if any([r["rng_sha256"] for r in e["trace"]] != rng for e in episodes):
        return {**w, "valid": False, "reason": "random tape mismatch"}
    return {**w, "valid": True, "exact_emulator_equal": True,
            "endpoints": {a: {k: v for k, v in e.items() if k not in ("trace", "seed", "arm")} for a, e in by.items()}}


def payload(source: Path) -> tuple[dict[str, bytes], bool]:
    lock_path = HERE.parent / "cneh_exp_01" / "bnsyn_integration_contract.json"
    lock = pinned.strict_json(lock_path.read_bytes())
    if lock["source"]["commit"] != "c1de425ce4ece362e7f2feb2d9f24da5d3231014":
        raise ValueError("simulator source drift")
    before = pinned.validate_source(source, lock)
    rt = pinned.load_runtime(source, lock)
    episodes, worlds = [], []
    for seed in SEEDS:
        w = world(seed)
        rows = [episode(w, arm, rt) for arm in ARMS]
        worlds.append(pair(w, rows))
        episodes.extend(rows)
    if pinned.validate_source(source, lock) != before:
        raise ValueError("simulator source changed")
    valid = [w for w in worlds if w["valid"]]
    ood = [w for w in valid if w["tau"] is not None]
    reachable = [w for w in ood if w["mode"] != 3]
    def counts(arm: str, status: str) -> int:
        return sum(w["endpoints"][arm]["status"] == status for w in ood)
    report = {"experiment": "CNEH-EXP-04B", "authority": "ENGINEERED_NEURAL_ROUTE_PILOT_ONLY",
              "worlds": len(worlds), "valid_worlds": len(valid), "episodes": len(episodes),
              "all_instrument_checks_passed": len(valid) == len(worlds),
              "exact_emulator_equal_worlds": len(valid),
              "arm_ood_status_counts": {a: {s: counts(a, s) for s in ("IDENTIFIED_REACHABLE", "IDENTIFIED_DISCONNECTED", "UNRESOLVED")} for a in (ARMS[0], ARMS[2])},
              "max_gaba_oracle_residual_nS": max((e["max_gaba_residual_nS"] for e in episodes if e["valid"]), default=None),
              "mean_reachable_gaba_error_nS": {a: math.fsum(w["endpoints"][a]["post_mean_abs_gaba_error_nS"] for w in reachable) / len(reachable) if reachable else None for a in ARMS},
              "no_change_false_positives": sum(w["endpoints"][ARMS[0]]["detected"] is not None for w in valid if w["tau"] is None),
              "scientific_promotion_authorized": False, "independent_replication": "REPLICATION_NOT_TESTED",
              "physical_energy": "INSTRUMENT_INVALID", "arbitrary_graph_recovery_established": False}
    files = {"preregistration.md": (HERE / "PREREGISTRATION.md").read_bytes(),
             "implementation.json": pinned.canonical({"runner_sha256": pinned.sha(Path(__file__).read_bytes()),
                                                       "runtime_lock_sha256": pinned.sha(lock_path.read_bytes()), "source": lock["source"]}),
             "episodes.json.gz": gzip.compress(pinned.canonical(episodes), mtime=0),
             "worlds.json": pinned.canonical(worlds), "verdict.json": pinned.canonical(report)}
    return files, len(valid) == len(worlds)


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
