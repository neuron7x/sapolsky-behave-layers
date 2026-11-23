"""EXP04D: repeated OOD recovery with bounded-noise/erased-spike support.

The instantaneous support is sound under the frozen assumptions. Accumulated
epoch support is conditional on mode persistence and can be stale after a
hidden change. This distinction is recorded, never silently collapsed.
"""
from __future__ import annotations

import argparse
import gzip
import importlib
import math
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from experiments.cneh_exp_04b import run as neural
from experiments.cneh_exp_04c import qualification as filt

HERE = Path(__file__).resolve().parent
pinned = neural.pinned
parent = neural.parent
B, GROUPS, MODES, ARMS = neural.B, neural.GROUPS, neural.MODES, neural.ARMS
STEPS = 3200
SEEDS = tuple(range(87001, 87009)) + tuple(range(87101, 87105))
WINDOWS = ((650,750), (1450,1550), (2250,2350))
SEQUENCES = ((1,3,2), (2,3,0), (3,1,2), (3,2,0))
ALL = tuple(range(4))
ADAPTIVE = ARMS[:3]
GOAL = .5
LEASE = 400
EPS = .01
ERASE = .25
RENEWAL = "SCHEDULED_RENEWAL"
CONTRADICTION = "CONTRADICTION"


@dataclass(frozen=True)
class Observation:
    tick: int
    gaba: tuple[float, ...]
    bits: tuple[int | None, ...]

    def __post_init__(self) -> None:
        if type(self.tick) is not int or not 0 <= self.tick <= STEPS:
            raise ValueError("invalid observation tick")
        if len(self.gaba) != 16 or any(not math.isfinite(v) for v in self.gaba):
            raise ValueError("invalid receiver observation")
        filt.count_range(self.bits[:4])
        filt.count_range(self.bits[4:])
        if len(self.bits) != 8:
            raise ValueError("invalid source roster")


def known_action(mode: int, obs: Observation) -> tuple[int | None, str]:
    scheduled = neural.sentinel(obs.tick)
    if scheduled is not None:
        return scheduled, "SENTINEL"
    connected = [i for i, bit in enumerate(MODES[mode]) if bit]
    if not connected:
        return None, "DISCONNECTED_ABSTAIN"
    if math.fsum(obs.gaba) / len(B) < GOAL:
        return connected[0], "TRACK"
    return None, "TRACK_IDLE"


class Policy:
    """Observation-only epoch filter; no hidden mode or change schedule."""
    def __init__(self, arm: str):
        if arm not in ARMS[:-1]:
            raise ValueError("unregistered policy")
        self.arm = arm
        self.previous: Observation | None = None
        self.instant = ALL
        self.candidates = (0,)
        self.event = "INITIAL"
        self.epoch = 0

    def observe(self, obs: Observation) -> None:
        self.event = "INITIAL" if self.previous is None else "NONE"
        if self.previous is None:
            if obs.tick != 0:
                raise ValueError("missing initial observation")
        else:
            if obs.tick != self.previous.tick + 1:
                raise ValueError("nonconsecutive observation")
            r = filt.observed_residual(self.previous.gaba, obs.gaba)
            self.instant = filt.support(ALL, self.previous.bits, r)
            if not self.instant:
                raise ValueError("MODEL_SET_VIOLATION: instantaneous support empty")
            if self.arm != "STATIC_NOMINAL":
                if obs.tick % LEASE == 0:
                    self.candidates = self.instant
                    self.epoch += 1
                    self.event = RENEWAL
                else:
                    intersection = tuple(i for i in self.candidates if i in self.instant)
                    if not intersection:
                        self.candidates = self.instant
                        self.epoch += 1
                        self.event = CONTRADICTION
                    else:
                        self.candidates = intersection
        self.previous = obs

    def act(self) -> tuple[int | None, str]:
        if self.previous is None or self.previous.tick == STEPS:
            raise ValueError("control without current observation")
        if len(self.candidates) == 1:
            return known_action(self.candidates[0], self.previous)
        if self.arm in ARMS[:2]:
            return neural.distinguishing_group(self.candidates), "ACTIVE_PROBE"
        scheduled = neural.sentinel(self.previous.tick)
        return (scheduled, "SENTINEL") if scheduled is not None else (None, "AMBIGUOUS_ABSTAIN")


def world(seed: int) -> dict[str, Any]:
    if seed not in SEEDS:
        raise ValueError("unregistered world")
    rng = random.Random(seed)
    schedule = []
    if seed < 87101:
        seq = SEQUENCES[(seed-87001) % len(SEQUENCES)]
        schedule = [(rng.randint(lo,hi),mode) for (lo,hi),mode in zip(WINDOWS,seq,strict=True)]
    return {"seed":seed,"schedule":schedule}


def sensor_tape(seed: int) -> list[tuple[tuple[float,...], tuple[bool,...]]]:
    rng = random.Random(seed+1000000)
    rows = []
    for t in range(STEPS+1):
        noise = tuple(rng.uniform(-EPS,EPS) for _ in B)
        masks = tuple(rng.random() < ERASE for _ in range(8))
        if 1000 <= t < 1100 or 2000 <= t < 2100:
            masks = (True,)*8
        rows.append((noise,masks))
    return rows


def public_observation(t: int, gaba: tuple[float,...], bits: tuple[int,...],
                       noise: tuple[float,...], mask: tuple[bool,...]) -> Observation:
    if len(noise)!=16 or len(mask)!=8 or len(bits)!=8 or len(gaba)!=16:
        raise ValueError("invalid sensor tape dimensions")
    if any(not math.isfinite(v) or abs(v)>EPS for v in noise):
        raise ValueError("unregistered sensor corruption")
    if any(type(v) is not bool for v in mask):
        raise ValueError("invalid erasure mask")
    if any(type(v) is not int or v not in (0,1) for v in bits):
        raise ValueError("invalid true spike vector")
    y = tuple(x+e for x,e in zip(gaba,noise,strict=True))
    observed = tuple(None if m else v for v,m in zip(bits,mask,strict=True))
    if any(abs(x-z)>EPS+1e-12 for x,z in zip(gaba,y,strict=True)):
        raise ValueError("observation exceeds frozen bound")
    return Observation(t,y,observed)


def obs_record(obs: Observation) -> dict:
    return {"tick":obs.tick,"observed_gaba":[v.hex() for v in obs.gaba],
            "observed_bits":list(obs.bits)}


def parse_obs(row: dict) -> Observation:
    return Observation(row["tick"],tuple(float.fromhex(v) for v in row["observed_gaba"]),
                       tuple(row["observed_bits"]))


def audit_policy_tape(rows: list[dict], arm: str) -> None:
    if len(rows)!=STEPS+1 or [r["tick"] for r in rows]!=list(range(STEPS+1)):
        raise ValueError("incomplete policy observation tape")
    p = Policy(arm)
    for row in rows:
        p.observe(parse_obs(row))
        if (row["instant"]!=list(p.instant) or row["candidates"]!=list(p.candidates)
            or row["event"]!=p.event or row["epoch"]!=p.epoch):
            raise ValueError("policy evidence differs from observation-only replay")
        if row["tick"]<STEPS and (row["group"],row["kind"])!=p.act():
            raise ValueError("policy action differs from observation-only replay")


def first_run(flags: list[bool], ticks: list[int], length: int) -> int | None:
    """Return the qualification-completion tick, not a future-informed onset."""
    if len(flags)!=len(ticks) or length<=0:
        raise ValueError("invalid recovery window")
    streak = 0
    for i, (flag,tick) in enumerate(zip(flags,ticks,strict=True)):
        if i and tick!=ticks[i-1]+1:
            raise ValueError("nonconsecutive recovery window")
        streak = streak+1 if flag else 0
        if streak==length:
            return tick
    return None


def segment_metrics(rows: list[dict], arm: str, tau: int, end: int, mode: int) -> dict:
    # Observation t describes transition t-1; actions at tau..end-1
    # belong to the new mode even when detection is still pending.
    obs = rows[tau+1:end+1]
    acts = rows[tau:end]
    if not obs or [r["tick"] for r in obs]!=list(range(tau+1,end+1)):
        raise ValueError("incomplete segment")
    if any(r["transition_mode"]!=mode for r in obs) or any(r["next_mode"]!=mode for r in acts):
        raise ValueError("wrong evaluator segment boundary")
    eligible = arm in ADAPTIVE
    correct = [eligible and r["candidates"]==[mode] for r in obs]
    stale = [eligible and mode not in r["candidates"] for r in obs]
    ambiguous = [eligible and len(r["candidates"])>1 for r in obs]
    actual = [math.fsum(float.fromhex(v) for v in r["true_gaba"])/len(B) for r in obs]
    band = [.4<=v<=.6 for v in actual]
    ticks = [r["tick"] for r in obs]
    ident = first_run(correct,ticks,20) if eligible else None
    recovery = first_run([c and b for c,b in zip(correct,band,strict=True)],ticks,10) if eligible and mode!=3 else None
    return {"start_transition":tau,"end_transition_exclusive":end,"mode":mode,"reachable":mode!=3,
            "identification_status":("NOT_APPLICABLE" if not eligible else
                                     "RECOVERED" if ident is not None else "UNRESOLVED"),
            "identification_latency":None if ident is None else ident-tau,
            "control_recovery_status":("DISCONNECTED_NOT_APPLICABLE" if mode==3 else "NOT_APPLICABLE" if not eligible
                                        else "RECOVERED" if recovery is not None else "UNRESOLVED"),
            "control_recovery_latency":None if recovery is None else recovery-tau,
            "ambiguous_fraction":sum(ambiguous)/len(obs) if eligible else None,
            "stale_fraction":sum(stale)/len(obs) if eligible else None,
            "correct_singleton_fraction":sum(correct)/len(obs) if eligible else None,
            "contradictions":sum(r["event"]==CONTRADICTION for r in obs) if eligible else None,
            "renewals":sum(r["event"]==RENEWAL for r in obs) if eligible else None,
            "mean_abs_error_nS":math.fsum(abs(v-GOAL) for v in actual)/len(actual),
            "in_band_fraction":sum(band)/len(band),
            "tracking_ticks":sum(r["kind"]=="TRACK" for r in acts),
            "abstention_ticks":sum(r["kind"]=="DISCONNECTED_ABSTAIN" for r in acts),
            "source_current_l1_pA_ticks":4*500*sum(r["group"] is not None for r in acts)}


def episode(w: dict, arm: str, rt: dict, tape: list) -> dict:
    np, network, config = (rt[k] for k in ("np","network","config"))
    if arm not in ARMS:
        raise ValueError("unknown arm")
    seed = w["seed"]
    schedule = dict(w["schedule"])
    net = network.Network(network.NetworkParams(N=32,frac_inhib=.25,p_conn=0.),
                          config.AdExParams(),config.SynapseParams(),config.CriticalityParams(),
                          dt_ms=.1,rng=np.random.default_rng(seed),backend="reference")
    if net.nE!=24 or net.nI!=8 or net._use_torch or net.syn.tau_GABAA_ms!=6.:
        raise ValueError("wrong source/runtime boundary")
    connectivity = importlib.import_module("bnsyn.connectivity").SparseConnectivity
    mode = 0
    matrix_sha = neural.apply_mode(net,mode,np,connectivity)
    policy = None if arm=="ORACLE" else Policy(arm)
    rows = []
    previous_gaba = None
    previous_bits = None
    previous_mode = None
    max_residual = 0.
    try:
        for t in range(STEPS+1):
            gaba = tuple(float(net.g_gabaa[j]) for j in B)
            bits = tuple(int(net.state.spiked[j]) for group in GROUPS for j in group)
            if any(not math.isfinite(x) or x<0 for x in gaba):
                raise ValueError("invalid latent conductance")
            if previous_gaba is not None:
                if previous_mode is None or previous_bits is None:
                    raise ValueError("missing previous transition")
                m = MODES[previous_mode]
                count = m[0]*sum(previous_bits[:4])+m[1]*sum(previous_bits[4:])
                # Independent scalar recurrence, not the support filter.
                expected = [math.exp(-.1/6.)*(v+.5*count) for v in previous_gaba]
                err = max(abs(x-y) for x,y in zip(gaba,expected,strict=True))
                max_residual = max(max_residual,err)
                if err>1e-9:
                    raise ValueError("actual GABAA recurrence mismatch")
            noise, erased = tape[t]
            obs = public_observation(t,gaba,bits,noise,erased)
            if policy is not None:
                policy.observe(obs)
                if t and previous_mode not in policy.instant:
                    raise ValueError("instantaneous support falsely excludes true mode")
                if not schedule and policy.event==CONTRADICTION:
                    raise ValueError("false contradiction in unchanged world")
                if not schedule and arm in ADAPTIVE and 0 not in policy.candidates:
                    raise ValueError("nominal model lost without switch")
            if t in schedule:
                next_mode = schedule[t]
                before = parent.physical_state_digest(net,np)
                matrix_sha = neural.apply_mode(net,next_mode,np,connectivity)
                if parent.physical_state_digest(net,np)!=before:
                    raise ValueError("intervention changed physical memory")
                mode = next_mode
            row = {**obs_record(obs),"true_gaba":[v.hex() for v in gaba],
                   "true_bits":list(bits),"noise":[v.hex() for v in noise],"erasures":list(erased),
                   "transition_mode":previous_mode,"next_mode":mode,
                   "B_voltage_mV":[float(net.state.V_mV[j]).hex() for j in B],
                   "state_sha256":parent.physical_state_digest(net,np),
                   "rng_sha256":pinned.sha(pinned.canonical(net.rng.bit_generator.state)),
                   "instant":None if policy is None else list(policy.instant),
                   "candidates":None if policy is None else list(policy.candidates),
                   "event":None if policy is None else policy.event,
                   "epoch":None if policy is None else policy.epoch}
            if t==STEPS:
                rows.append(row)
                break
            group,kind = known_action(mode,obs) if policy is None else policy.act()
            if group is not None and (type(group) is not int or group not in (0,1)):
                raise ValueError("invalid actuator")
            if policy is not None and kind=="TRACK" and (len(policy.candidates)!=1 or policy.candidates==(3,)):
                raise ValueError("unauthorized tracking under ambiguity/disconnection")
            u = np.zeros(32,dtype=np.float64)
            u[list(B)] = 300.
            if group is not None:
                u[list(GROUPS[group])] = 500.
            net.gain = 1.
            row.update(group=group,kind=kind,applied_gain=1.,topology_sha256=matrix_sha,
                       direct_B_pA=300.,source_inputs_pA=[500. if group==j else 0. for j in range(2)])
            rows.append(row)
            metrics = net.step(external_current_pA=u)
            if any(not math.isfinite(float(v)) for v in metrics.values()):
                raise ValueError("nonfinite metric")
            if not np.isfinite(net.state.V_mV).all() or np.any(net.state.V_mV<net.np.V_min_mV) or np.any(net.state.V_mV>net.np.V_max_mV):
                raise ValueError("voltage envelope violated")
            neural.gain.check_current(net._I_ext_buffer,u,1.,network.GAIN_CURRENT_SCALE_PA,np)
            if parent.matrix_digest(net.W_exc.to_dense(),net.W_inh.to_dense())!=matrix_sha:
                raise ValueError("unexpected recurrent route")
            previous_gaba,previous_bits,previous_mode = gaba,bits,mode
        if policy is not None:
            audit_policy_tape(rows,arm)
        schedule_list = w["schedule"]
        segments = [segment_metrics(rows,arm,tau,schedule_list[i+1][0] if i+1<len(schedule_list) else STEPS,m)
                    for i,(tau,m) in enumerate(schedule_list)]
        return {"seed":seed,"arm":arm,"valid":True,"segments":segments,
                "max_recurrence_residual_nS":max_residual,
                "contradictions":sum(r["event"]==CONTRADICTION for r in rows),
                "renewals":sum(r["event"]==RENEWAL for r in rows),
                "source_current_l1_pA_ticks":4*500*sum(r.get("group") is not None for r in rows),
                "trace":rows}
    except (ValueError,RuntimeError,ArithmeticError) as exc:
        return {"seed":seed,"arm":arm,"valid":False,"failure":str(exc),
                "failure_tick":t,"trace":rows}


def pair(w: dict, episodes: list[dict]) -> dict:
    by = {e["arm"]:e for e in episodes}
    if len(episodes)!=5 or set(by)!=set(ARMS):
        raise ValueError("incomplete world roster")
    if any(not e["valid"] for e in episodes):
        return {**w,"valid":False,"reason":"episode invalid"}
    def without_arm(e: dict) -> dict:
        return {k:v for k,v in e.items() if k!="arm"}
    if without_arm(by[ARMS[0]])!=without_arm(by[ARMS[1]]):
        return {**w,"valid":False,"reason":"exact emulator divergence"}
    def exogenous(e: dict) -> list:
        return [(r["rng_sha256"],r["noise"],r["erasures"]) for r in e["trace"]]
    ref = exogenous(by[ARMS[0]])
    if any(exogenous(e)!=ref for e in episodes):
        return {**w,"valid":False,"reason":"exogenous tape mismatch"}
    if any(e["trace"][0]["state_sha256"]!=by[ARMS[0]]["trace"][0]["state_sha256"] for e in episodes):
        return {**w,"valid":False,"reason":"initial state mismatch"}
    return {**w,"valid":True,"exact_emulator_equal":True,
            "endpoints":{a:{k:v for k,v in e.items() if k not in ("trace","seed","arm")} for a,e in by.items()}}


def summarize(worlds: list[dict], episodes: list[dict]) -> dict:
    passed = len(worlds)==len(SEEDS) and all(w["valid"] for w in worlds)
    report = {"experiment":"CNEH-EXP-04D","worlds":len(worlds),"episodes":len(episodes),
              "all_instrument_checks_passed":passed,"valid_worlds":sum(w["valid"] for w in worlds),
              "authority":"REPEATED_OOD_ENGINEERED_NEURAL_PILOT_ONLY",
              "scientific_promotion_authorized":False,"independent_replication":"REPLICATION_NOT_TESTED",
              "physical_energy":"INSTRUMENT_INVALID","physical_sensor_qualification":"NOT_TESTED",
              "epoch_singletons_conditional_on_persistence":True,
              "invalid_worlds":[{"seed":w["seed"],"reason":w.get("reason")} for w in worlds if not w["valid"]]}
    if not passed:
        report["aggregate_status"]="BLOCKED_NO_SURVIVOR_AVERAGING"
        return report
    ood = [w for w in worlds if w["schedule"]]
    no_change = [w for w in worlds if not w["schedule"]]
    report["exact_emulator_equal_worlds"]=sum(w["exact_emulator_equal"] for w in worlds)
    report["max_recurrence_residual_nS"]=max(e["max_recurrence_residual_nS"] for e in episodes)
    report["no_change_contradictions"]={a:sum(w["endpoints"][a]["contradictions"] for w in no_change) for a in ADAPTIVE}
    per_arm = {}
    for arm in ARMS:
        segs = [s for w in ood for s in w["endpoints"][arm]["segments"]]
        reachable = [s for s in segs if s["reachable"]]
        disconnected = [s for s in segs if not s["reachable"]]
        per_arm[arm]={"segments":len(segs),"reachable_segments":len(reachable),
                      "disconnected_segments":len(disconnected),
                      "identified_segments":sum(s["identification_status"]=="RECOVERED" for s in segs) if arm in ADAPTIVE else None,
                      "identified_disconnects":sum(s["identification_status"]=="RECOVERED" for s in disconnected) if arm in ADAPTIVE else None,
                      "recovered_reachable_segments":sum(s["control_recovery_status"]=="RECOVERED" for s in reachable) if arm in ADAPTIVE else None,
                      "mean_reachable_abs_error_nS":math.fsum(s["mean_abs_error_nS"] for s in reachable)/len(reachable),
                      "mean_reachable_in_band_fraction":math.fsum(s["in_band_fraction"] for s in reachable)/len(reachable),
                      "mean_stale_fraction":math.fsum(s["stale_fraction"] for s in segs)/len(segs) if arm in ADAPTIVE else None,
                      "mean_ambiguous_fraction":math.fsum(s["ambiguous_fraction"] for s in segs)/len(segs) if arm in ADAPTIVE else None,
                      "disconnected_tracking_ticks":sum(s["tracking_ticks"] for s in disconnected),
                      "ood_source_current_l1_pA_ticks":sum(w["endpoints"][arm]["source_current_l1_pA_ticks"] for w in ood)}
    report["arm_metrics"]=per_arm
    report["paired_active_tracking_error_advantage_nS"]={
        a:math.fsum(s1["mean_abs_error_nS"]-s0["mean_abs_error_nS"]
                    for w in ood for s0,s1 in zip(w["endpoints"][ARMS[0]]["segments"],w["endpoints"][a]["segments"],strict=True)
                    if s0["reachable"])/per_arm[ARMS[0]]["reachable_segments"] for a in ARMS[2:4]}
    return report


def payload(source: Path) -> tuple[dict[str,bytes],bool]:
    if MODES!=filt.MODES or neural.DECAY!=filt.DECAY or EPS!=filt.EPS or neural.WEIGHT!=.5:
        raise ValueError("parent analytic contract drift")
    lock_path = HERE.parent/"cneh_exp_01"/"bnsyn_integration_contract.json"
    lock = pinned.strict_json(lock_path.read_bytes())
    if lock["source"]["commit"]!="c1de425ce4ece362e7f2feb2d9f24da5d3231014":
        raise ValueError("simulator source drift")
    before = pinned.validate_source(source,lock)
    rt = pinned.load_runtime(source,lock)
    episodes, worlds = [],[]
    for seed in SEEDS:
        w = world(seed)
        tape = sensor_tape(seed)
        es = [episode(w,a,rt,tape) for a in ARMS]
        worlds.append(pair(w,es))
        episodes.extend(es)
    if pinned.validate_source(source,lock)!=before:
        raise ValueError("simulator source changed")
    report = summarize(worlds,episodes)
    files = {"preregistration.md":(HERE/"PREREGISTRATION.md").read_bytes(),
             "implementation.json":pinned.canonical({"runner_sha256":pinned.sha(Path(__file__).read_bytes()),
               "neural_runner_sha256":pinned.sha(Path(neural.__file__).read_bytes()),
               "support_filter_sha256":pinned.sha(Path(filt.__file__).read_bytes()),
               "runtime_lock_sha256":pinned.sha(lock_path.read_bytes()),"source":lock["source"]}),
             "episodes.json.gz":gzip.compress(pinned.canonical(episodes),mtime=0),
             "worlds.json":pinned.canonical(worlds),"verdict.json":pinned.canonical(report)}
    return files,report["all_instrument_checks_passed"]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--verify",action="store_true")
    args = p.parse_args()
    if not args.verify and (args.out.exists() or args.out.is_symlink()):
        raise FileExistsError("immutable output")
    files,passed = payload(args.source)
    if not args.verify:
        parent.write_bundle(args.out,files)
    parent.verify_payload(args.out,files)
    print(files["verdict.json"].decode().strip())
    raise SystemExit(0 if passed else 2)


if __name__=="__main__":
    main()
