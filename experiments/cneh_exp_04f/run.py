"""EXP04F: fixed-budget prospective paired neural control experiment."""
from __future__ import annotations

import argparse
import gzip
import importlib
import math
import random
from collections import Counter
from pathlib import Path

from experiments.cneh_exp_04c import qualification as q
from experiments.cneh_exp_04d import run as d
from experiments.cneh_exp_04e import audit as e
from experiments.cneh_exp_04f import policy as f

HERE = Path(__file__).resolve().parent
SEEDS = tuple(range(88001,88013))+tuple(range(88101,88105))
pinned, parent, neural = d.pinned,d.parent,d.neural


def world(seed: int) -> dict:
    if seed not in SEEDS:
        raise ValueError("unregistered seed")
    rng = random.Random(seed)
    schedule = []
    if seed<88101:
        seq=d.SEQUENCES[(seed-88001)%len(d.SEQUENCES)]
        schedule=[(rng.randint(lo,hi),m) for (lo,hi),m in zip(d.WINDOWS,seq,strict=True)]
    return {"seed":seed,"schedule":schedule}


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise ValueError(reason)


def segment(rows: list[dict], start: int, end: int, mode: int) -> dict:
    acts,obs=rows[start:end],rows[start+1:end+1]
    require(len(acts)==len(obs)==end-start and end>start,"segment boundary")
    require(all(r["transition_mode"]==mode for r in obs) and all(r["next_mode"]==mode for r in acts),"mode boundary")
    ticks=list(range(start+1,end+1))
    correct=[r["policy"]["candidates"]==[mode] for r in obs]
    band=[]
    error=[]
    stale=ambiguous=retained=expiries=renewals=contradictions=reexpansions=0
    history=set(d.ALL)
    counts=Counter({k:0 for k in e.CLASSES})
    groups=[{"stimulated_ticks":0,"true_spikes_after_stimulation":0,"observed_ones_after_stimulation":0,
             "observed_bits_after_stimulation":0,"true_spikes_before_transition":0} for _ in range(2)]
    source_spike_ticks=0
    for old,row in zip(acts,obs,strict=True):
        previous,current=old["policy"],row["policy"]
        actual=math.fsum(float.fromhex(x) for x in row["true_gaba"])/len(d.B)
        band.append(.4<=actual<=.6)
        error.append(abs(actual-d.GOAL))
        candidate=set(current["candidates"])
        instant=set(current["instant"])
        history.intersection_update(instant)
        require(mode in history,"privileged history lost truth")
        stale+=mode not in candidate
        ambiguous+=len(candidate)>1
        retained+=bool((candidate-history)-{mode})
        expiries+=len(current["expired"])
        renewals+=current["event"]==d.RENEWAL
        contradictions+=current["event"]==d.CONTRADICTION
        reexpansions+=bool(candidate-set(previous["candidates"]))
        bits=tuple(old["true_bits"])
        n=(sum(bits[:4]),sum(bits[4:]))
        source_spike_ticks+=any(n)
        full=set(q.support(d.ALL,bits,q.observed_residual(d.parse_obs(old).gaba,d.parse_obs(row).gaba)))
        require(full=={i for i in d.ALL if sum(a*b for a,b in zip(q.MODES[i],n,strict=True))==
                        sum(a*b for a,b in zip(q.MODES[mode],n,strict=True))} and full<=instant,"full-spike support mismatch")
        for other in d.ALL:
            if other!=mode:
                counts[e.classify(mode,other,n,instant)]+=1
        for g,stat in enumerate(groups):
            stat["true_spikes_before_transition"]+=n[g]
            if old["group"]==g:
                stat["stimulated_ticks"]+=1
                stat["true_spikes_after_stimulation"]+=sum(row["true_bits"][4*g:4*g+4])
                observed=row["observed_bits"][4*g:4*g+4]
                stat["observed_ones_after_stimulation"]+=observed.count(1)
                stat["observed_bits_after_stimulation"]+=sum(x is not None for x in observed)
    require(sum(counts.values())==3*(end-start),"incomplete pair attribution")
    ident=d.first_run(correct,ticks,20)
    joint=d.first_run([c and b for c,b in zip(correct,band,strict=True)],ticks,10) if mode!=3 else None
    return {"start":start,"end":end,"mode":mode,"reachable":mode!=3,"ticks":end-start,
            "identified":ident is not None,"identification_latency":None if ident is None else ident-start,
            "recovered":None if mode==3 else joint is not None,"recovery_latency":None if joint is None else joint-start,
            "correct_fraction":sum(correct)/len(obs),"ambiguous_fraction":ambiguous/len(obs),"stale_fraction":stale/len(obs),
            "retained_false_ticks":retained,"evidence_expiries":expiries,"scheduled_renewals":renewals,
            "contradictions":contradictions,"reexpansions":reexpansions,"mean_abs_error_nS":math.fsum(error)/len(obs),
            "band_fraction":sum(band)/len(obs),"longest_band_run":e.longest(band),
            "tracking_ticks":sum(r["kind"]=="TRACK" for r in acts),
            "continuation_ticks":sum(r["kind"]=="PACKET_CONTINUATION" for r in acts),
            "stimulated_ticks":sum(r["group"] is not None for r in acts),
            "source_spike_ticks":source_spike_ticks,"pair_partition":dict(counts),
            "silence_fraction":counts["NO_SPIKES"]/sum(counts.values()),"groups":groups}


def episode(w: dict, arm: str, rt: dict, tape: list) -> dict:
    np,network,config=(rt[k] for k in ("np","network","config"))
    seed=w["seed"]
    schedule=dict(w["schedule"])
    net=network.Network(network.NetworkParams(N=32,frac_inhib=.25,p_conn=0.),
                        config.AdExParams(),config.SynapseParams(),config.CriticalityParams(),
                        dt_ms=.1,rng=np.random.default_rng(seed),backend="reference")
    require(net.nE==24 and net.nI==8 and not net._use_torch and net.syn.tau_GABAA_ms==6.,"wrong runtime")
    connectivity=importlib.import_module("bnsyn.connectivity").SparseConnectivity
    mode=0
    matrix_sha=neural.apply_mode(net,mode,np,connectivity)
    policy=f.Policy(arm)
    rows=[]
    previous_gaba=previous_bits=previous_mode=None
    maximum=0.
    used=0
    t=0
    try:
        for t in range(d.STEPS+1):
            gaba=tuple(float(net.g_gabaa[j]) for j in d.B)
            bits=tuple(int(net.state.spiked[j]) for group in d.GROUPS for j in group)
            require(all(math.isfinite(v) and v>=0 for v in gaba),"invalid latent conductance")
            if t:
                count=sum(q.MODES[previous_mode][g]*sum(previous_bits[4*g:4*g+4]) for g in range(2))
                expected=[math.exp(-.1/6.)*(v+.5*count) for v in previous_gaba]
                err=max(abs(x-y) for x,y in zip(gaba,expected,strict=True))
                maximum=max(maximum,err)
                require(err<=1e-9,"true recurrence mismatch")
            noise,erased=tape[t]
            observed=d.public_observation(t,gaba,bits,noise,erased)
            policy.observe(observed)
            if t:
                require(previous_mode in policy.instant,"instantaneous false exclusion")
            if not schedule:
                require(policy.event!=d.CONTRADICTION and 0 in policy.candidates,"false contradiction/exclusion without change")
            if t in schedule:
                before=parent.physical_state_digest(net,np)
                mode=schedule[t]
                matrix_sha=neural.apply_mode(net,mode,np,connectivity)
                require(parent.physical_state_digest(net,np)==before,"topology changed physical memory")
            row={**d.obs_record(observed),"policy":policy.snapshot(),"true_gaba":[x.hex() for x in gaba],
                 "true_bits":list(bits),"noise":[x.hex() for x in noise],"erasures":list(erased),
                 "transition_mode":previous_mode,"next_mode":mode,
                 "B_voltage_mV":[float(net.state.V_mV[j]).hex() for j in d.B],
                 "state_sha256":parent.physical_state_digest(net,np),
                 "rng_sha256":pinned.sha(pinned.canonical(net.rng.bit_generator.state))}
            if t==d.STEPS:
                rows.append(row)
                break
            group,kind,decision=policy.act()
            require(group is None or type(group) is int and group in (0,1),"invalid source group")
            require((group is not None)==f.is_on(t),"source budget violation")
            used+=group is not None
            require(used==f.ON*(t//f.PACKET)+min(t%f.PACKET+1,f.ON),"prefix effort violation")
            if kind=="TRACK":
                require(len(policy.candidates)==1 and q.MODES[policy.candidates[0]][group] and policy.below_goal(),"unsafe conditional tracking")
            u=np.zeros(32,dtype=np.float64)
            u[list(d.B)]=300.
            if group is not None:
                u[list(d.GROUPS[group])]=500.
            net.gain=1.
            row.update(group=group,kind=kind,packet_decision=decision,applied_gain=1.,
                       topology_sha256=matrix_sha,direct_B_pA=300.,
                       source_inputs_pA=[500. if group==g else 0. for g in range(2)])
            rows.append(row)
            metrics=net.step(external_current_pA=u)
            require(all(math.isfinite(float(v)) for v in metrics.values()),"nonfinite metrics")
            require(np.isfinite(net.state.V_mV).all() and not np.any(net.state.V_mV<net.np.V_min_mV) and not np.any(net.state.V_mV>net.np.V_max_mV),"voltage envelope")
            neural.gain.check_current(net._I_ext_buffer,u,1.,network.GAIN_CURRENT_SCALE_PA,np)
            require(parent.matrix_digest(net.W_exc.to_dense(),net.W_inh.to_dense())==matrix_sha,"unexpected recurrent route")
            previous_gaba,previous_bits,previous_mode=gaba,bits,mode
        require(used==1600,"inexact total current budget")
        f.audit_tape(rows,arm)
        switches=w["schedule"]
        segments=[segment(rows,tau,switches[i+1][0] if i+1<len(switches) else d.STEPS,m)
                  for i,(tau,m) in enumerate(switches)]
        return {"seed":seed,"arm":arm,"valid":True,"trace":rows,"segments":segments,
                "max_recurrence_residual_nS":maximum,"source_current_l1_pA_ticks":2000*used,
                "contradictions":sum(r["policy"]["event"]==d.CONTRADICTION for r in rows)}
    except (ValueError,RuntimeError,ArithmeticError) as exc:
        return {"seed":seed,"arm":arm,"valid":False,"failure":str(exc),"failure_tick":t,"trace":rows}


def pair(w: dict, episodes: list[dict]) -> dict:
    by={x["arm"]:x for x in episodes}
    require(len(episodes)==len(f.ARMS) and set(by)==set(f.ARMS),"incomplete arm roster")
    if any(not x["valid"] for x in episodes):
        return {**w,"valid":False,"reason":"episode invalid"}
    def no_arm(x):
        return {k:v for k,v in x.items() if k!="arm"}
    if no_arm(by[f.ARMS[0]])!=no_arm(by[f.ARMS[1]]):
        return {**w,"valid":False,"reason":"exact emulator divergence"}
    def exogenous(x):
        return [(r["rng_sha256"],r["noise"],r["erasures"],r.get("group") is not None) for r in x["trace"]]
    ref=exogenous(by[f.ARMS[0]])
    if any(exogenous(x)!=ref or x["trace"][0]["state_sha256"]!=by[f.ARMS[0]]["trace"][0]["state_sha256"] or x["source_current_l1_pA_ticks"]!=3200000 for x in episodes):
        return {**w,"valid":False,"reason":"initial/tape/prefix budget mismatch"}
    return {**w,"valid":True,"exact_emulator_equal":True,
            "endpoints":{a:{k:v for k,v in x.items() if k not in ("trace","seed","arm")} for a,x in by.items()}}


def endpoints(segs: list[dict]) -> dict:
    reachable=[s for s in segs if s["reachable"]]
    disconnected=[s for s in segs if not s["reachable"]]
    counts={k:sum(s["pair_partition"][k] for s in segs) for k in e.CLASSES}
    return {"segments":len(segs),"reachable_segments":len(reachable),"disconnected_segments":len(disconnected),
            "identified":sum(s["identified"] for s in segs),"identified_disconnects":sum(s["identified"] for s in disconnected),
            "recovered":sum(s["recovered"] for s in reachable),
            "pair_partition":counts,"silence_fraction":counts["NO_SPIKES"]/sum(counts.values()),
            "source_spike_ticks":sum(s["source_spike_ticks"] for s in segs),
            "mean_stale_fraction":math.fsum(s["stale_fraction"] for s in segs)/len(segs),
            "mean_ambiguous_fraction":math.fsum(s["ambiguous_fraction"] for s in segs)/len(segs),
            "mean_reachable_abs_error_nS":math.fsum(s["mean_abs_error_nS"] for s in reachable)/len(reachable),
            "mean_reachable_band_fraction":math.fsum(s["band_fraction"] for s in reachable)/len(reachable),
            "retained_false_ticks":sum(s["retained_false_ticks"] for s in segs),
            "evidence_expiries":sum(s["evidence_expiries"] for s in segs),
            "scheduled_renewals":sum(s["scheduled_renewals"] for s in segs),
            "reexpansions":sum(s["reexpansions"] for s in segs),
            "contradictions":sum(s["contradictions"] for s in segs),
            "disconnected_tracking_ticks":sum(s["tracking_ticks"] for s in disconnected),
            "disconnected_stimulated_ticks":sum(s["stimulated_ticks"] for s in disconnected)}


def summarize(worlds: list[dict],episodes: list[dict]) -> dict:
    passed=len(worlds)==len(SEEDS) and len(episodes)==len(SEEDS)*len(f.ARMS) and all(w["valid"] for w in worlds)
    report={"experiment":"CNEH-EXP-04F","authority":"PROSPECTIVE_INTERNAL_ENGINEERED_PILOT",
            "worlds":len(worlds),"episodes":len(episodes),"valid_worlds":sum(w["valid"] for w in worlds),
            "all_instrument_checks_passed":passed,"scientific_promotion_authorized":False,
            "external_replication":"NOT_TESTED","physical_energy":"NOT_VALIDATED",
            "invalid_worlds":[{"seed":w["seed"],"reason":w.get("reason")} for w in worlds if not w["valid"]]}
    if not passed:
        report["aggregate_status"]="BLOCKED_NO_SURVIVOR_AVERAGING"
        return report
    ood=[w for w in worlds if w["schedule"]]
    controls=[w for w in worlds if not w["schedule"]]
    report["exact_emulator_equal_worlds"]=sum(w["exact_emulator_equal"] for w in worlds)
    report["max_recurrence_residual_nS"]=max(x["max_recurrence_residual_nS"] for x in episodes)
    report["source_current_l1_pA_ticks_per_episode"]=3200000
    report["no_change_contradictions"]={a:sum(w["endpoints"][a]["contradictions"] for w in controls) for a in f.ARMS}
    metrics={a:endpoints([s for w in ood for s in w["endpoints"][a]["segments"]]) for a in f.ARMS}
    require(all(x["segments"]==36 and x["reachable_segments"]==24 and x["disconnected_segments"]==12 for x in metrics.values()),"segment roster")
    report["arm_metrics"]=metrics
    fields=("identified","recovered","silence_fraction","mean_stale_fraction","mean_ambiguous_fraction",
            "mean_reachable_abs_error_nS","mean_reachable_band_fraction","retained_false_ticks","disconnected_tracking_ticks")
    contrasts={}
    for a,b in ((f.ARMS[0],f.ARMS[2]),(f.ARMS[0],f.ARMS[3]),(f.ARMS[3],f.ARMS[4]),(f.ARMS[2],f.ARMS[4])):
        per=[]
        for w in ood:
            x,y=(endpoints(w["endpoints"][arm]["segments"]) for arm in (a,b))
            per.append({"seed":w["seed"],"difference":{k:x[k]-y[k] for k in fields}})
        contrasts[f"{a}_MINUS_{b}"]={"per_world":per,"mean_paired_difference":{k:math.fsum(v["difference"][k] for v in per)/len(per) for k in fields}}
    report["paired_contrasts"]=contrasts
    return report


def payload(source: Path) -> tuple[dict[str,bytes],bool]:
    require(d.MODES==q.MODES and neural.DECAY==q.DECAY and d.EPS==q.EPS and neural.WEIGHT==.5,"parent analytic contract drift")
    lock_path=HERE.parent/"cneh_exp_01"/"bnsyn_integration_contract.json"
    lock=pinned.strict_json(lock_path.read_bytes())
    require(lock["source"]["commit"]=="c1de425ce4ece362e7f2feb2d9f24da5d3231014","source drift")
    before=pinned.validate_source(source,lock)
    rt=pinned.load_runtime(source,lock)
    episodes,worlds=[],[]
    for seed in SEEDS:
        w=world(seed)
        tape=d.sensor_tape(seed)
        es=[episode(w,a,rt,tape) for a in f.ARMS]
        worlds.append(pair(w,es))
        episodes.extend(es)
    require(pinned.validate_source(source,lock)==before,"simulator source changed")
    report=summarize(worlds,episodes)
    files={"preregistration.md":(HERE/"PREREGISTRATION.md").read_bytes(),
           "implementation.json":pinned.canonical({"runner_sha256":pinned.sha(Path(__file__).read_bytes()),
              "policy_sha256":pinned.sha(Path(f.__file__).read_bytes()),
              "parent_runner_sha256":pinned.sha(Path(d.__file__).read_bytes()),
              "support_filter_sha256":pinned.sha(Path(q.__file__).read_bytes()),
              "attribution_sha256":pinned.sha(Path(e.__file__).read_bytes()),
              "runtime_lock_sha256":pinned.sha(lock_path.read_bytes()),"source":lock["source"]}),
           "episodes.json.gz":gzip.compress(pinned.canonical(episodes),mtime=0),
           "worlds.json":pinned.canonical(worlds),"verdict.json":pinned.canonical(report)}
    return files,report["all_instrument_checks_passed"]


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--verify",action="store_true")
    args=parser.parse_args()
    if not args.verify and (args.out.exists() or args.out.is_symlink()):
        raise FileExistsError("immutable evidence output")
    files,passed=payload(args.source)
    if not args.verify:
        parent.write_bundle(args.out,files)
    parent.verify_payload(args.out,files)
    print(files["verdict.json"].decode().strip())
    raise SystemExit(0 if passed else 2)


if __name__=="__main__":
    main()
