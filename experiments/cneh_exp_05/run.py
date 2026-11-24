"""Prospective reachability-constrained dual-control native neural pilot."""
from __future__ import annotations

import argparse
import gzip
import importlib
import math
import random
from pathlib import Path

from experiments.cneh_exp_04c import qualification as q
from experiments.cneh_exp_04d import run as d
from experiments.cneh_exp_04e import audit as e
from experiments.cneh_exp_04g import run as g
from experiments.cneh_exp_05 import policy as p

HERE=Path(__file__).resolve().parent
pinned,parent,neural=d.pinned,d.parent,d.neural
require=p.require
SEEDS=tuple(range(90001,90013))+tuple(range(90101,90105))


def world(seed: int) -> dict:
    require(seed in SEEDS,"unknown seed")
    rng=random.Random(seed)
    sequence=d.SEQUENCES[(seed-90001)%len(d.SEQUENCES)]
    schedule=[(rng.randint(lo,hi),m) for (lo,hi),m in zip(d.WINDOWS,sequence,strict=True)] if seed<90101 else []
    return {"seed":seed,"schedule":schedule}


def segment(rows: list[dict],start: int,end: int,mode: int) -> dict:
    acts,obs=rows[start:end],rows[start+1:end+1]
    require(len(acts)==len(obs)==end-start>0 and all(r["next_mode"]==mode for r in acts)
            and all(r["transition_mode"]==mode for r in obs),"segment truth")
    values=[math.fsum(float.fromhex(v) for v in row["true_gaba"])/len(d.B) for row in obs]
    band=[.4<=v<=.6 for v in values]
    occupancy=p.certify_band(band)
    correct=[row["policy"]["filter"]["candidates"]==[mode] for row in obs]
    stale=[mode not in row["policy"]["filter"]["candidates"] for row in obs]
    ambiguous=[len(row["policy"]["filter"]["candidates"])>1 for row in obs]
    arrivals=[]
    spikes=source_ticks=connected_below=disconnected_stim=0
    for row in acts:
        n=(sum(row["true_bits"][:4]),sum(row["true_bits"][4:]))
        spikes+=sum(n)
        source_ticks+=bool(sum(n))
        arrivals.append(sum(q.MODES[mode][j]*n[j] for j in range(2)))
        group=row["group"]
        if group is not None:
            disconnected_stim+=mode==3
            connected_below+=bool(q.MODES[mode][group]) and math.fsum(float.fromhex(v) for v in row["true_gaba"])/len(d.B)<.4
    ticks=list(range(start+1,end+1))
    ident=d.first_run(correct,ticks,20)
    joint=d.first_run([a and b for a,b in zip(correct,band,strict=True)],ticks,10) if mode!=3 else None
    return {"start":start,"end":end,"mode":mode,"reachable":mode!=3,"ticks":len(obs),
            "I20":ident is not None,"I20_latency":None if ident is None else ident-start,
            "J10":None if mode==3 else joint is not None,"J10_latency":None if joint is None else joint-start,
            "B10":None if mode==3 else e.longest(band)>=10,"longest_band_run":e.longest(band),
            "correct_fraction":sum(correct)/len(obs),"stale_fraction":sum(stale)/len(obs),
            "ambiguous_fraction":sum(ambiguous)/len(obs),"band_fraction":occupancy/len(obs),
            "relaxed_occupancy_upper_count":p.upper_count(len(obs)),
            "normalized_occupancy":occupancy/p.upper_count(len(obs)),
            "mean_abs_error_nS":math.fsum(abs(v-.5) for v in values)/len(values),
            "source_spike_events":spikes,"source_spike_ticks":source_ticks,
            "connected_arrivals":sum(arrivals),"arrival_ticks":sum(bool(n) for n in arrivals),
            "longest_arrival_gap":e.longest([n==0 for n in arrivals]),
            "connected_stim_below_ticks":connected_below,"disconnected_stim_ticks":disconnected_stim}


def block_metrics(rows: list[dict]) -> list[dict]:
    result=[]
    for t in range(0,d.STEPS,p.BLOCK):
        row=rows[t]
        acts=rows[t:t+p.BLOCK]
        obs=rows[t+1:t+p.BLOCK+1]
        decision=row["decision"]
        require(decision is not None and sum(x["group"] is not None for x in acts)==p.ON,"block ledger")
        plan=tuple(decision["selected"])
        require(all(x["group"]==p.action(plan,j) for j,x in enumerate(acts)),"plan realization")
        selected=next(x for x in decision["scores"] if x["plan"]==list(plan))
        mode=acts[0]["next_mode"]
        persistent=all(x["next_mode"]==mode for x in acts)
        vals=[math.fsum(float.fromhex(v) for v in x["true_gaba"])/len(d.B) for x in obs]
        actual_mae=math.fsum(abs(x-.5) for x in vals)/p.BLOCK
        band=p.certify_band([.4<=x<=.6 for x in vals])
        forecasts=[x for x in selected["forecasts"] if x["mode"]==mode] if persistent else []
        result.append({"start":t,"plan":list(plan),"persistent_true_mode":persistent,
                       "true_mode_in_candidates":mode in row["policy"]["filter"]["candidates"],
                       "actual_mae_nS":actual_mae,"actual_band_samples":band,
                       "same_mode_forecast_endpoints":[{"forecast_mae_nS":x["mae_nS"],
                           "actual_minus_forecast_mae_nS":actual_mae-x["mae_nS"],
                           "forecast_band_samples":x["in_band_samples"],
                           "actual_minus_forecast_band_samples":band-x["in_band_samples"]} for x in forecasts]})
    return result


def episode(w: dict,arm: str,rt: dict,tape: list) -> dict:
    np,network,config=(rt[k] for k in ("np","network","config"))
    seed=w["seed"]
    schedule=dict(w["schedule"])
    params=config.AdExParams()
    require((params.C_pF,params.gL_nS,params.EL_mV,params.VT_mV,params.DeltaT_mV,
             params.tauw_ms,params.a_nS,params.b_pA,params.Vreset_mV,params.Vpeak_mV)==
            (150.,10.,-70.,-55.,2.,200.,2.,80.,-58.,30.),"shadow parameter assumption drift")
    net=network.Network(network.NetworkParams(N=32,frac_inhib=.25,p_conn=0.),
                        params,config.SynapseParams(),config.CriticalityParams(),
                        dt_ms=.1,rng=np.random.default_rng(seed),backend="reference")
    require(net.nE==24 and net.nI==8 and not net._use_torch and net.syn.tau_GABAA_ms==6.,"native plant boundary")
    connectivity=importlib.import_module("bnsyn.connectivity").SparseConnectivity
    mode=0
    matrix=neural.apply_mode(net,mode,np,connectivity)
    policy=p.Policy(arm)
    rows=[]
    used=0
    previous_gaba=previous_bits=previous_mode=None
    max_residual=0.
    t=0
    try:
        for t in range(d.STEPS+1):
            gaba=tuple(float(net.g_gabaa[j]) for j in d.B)
            bits=tuple(int(net.state.spiked[j]) for j in g.SOURCES)
            require(all(math.isfinite(v) and v>=0 for v in gaba),"invalid latent conductance")
            if t:
                n=sum(q.MODES[previous_mode][j]*sum(previous_bits[j*4:j*4+4]) for j in range(2))
                residual=max(abs(x-q.DECAY*(y+.5*n)) for x,y in zip(gaba,previous_gaba,strict=True))
                max_residual=max(max_residual,residual)
                require(residual<=1e-9,"actual arrival recurrence")
            noise,mask=tape[t]
            obs=d.public_observation(t,gaba,bits,noise,mask)
            policy.observe(obs)
            if t:
                require(previous_mode in policy.filter.instant,"instantaneous support exclusion")
            if not schedule:
                require(policy.filter.event!=d.CONTRADICTION and 0 in policy.filter.candidates,"false no-change contradiction")
            if t in schedule:
                before=parent.physical_state_digest(net,np)
                mode=schedule[t]
                matrix=neural.apply_mode(net,mode,np,connectivity)
                require(parent.physical_state_digest(net,np)==before,"topology altered physical memory")
            row={**d.obs_record(obs),"noise":g.hx(noise),"erasures":list(mask),"policy":policy.snapshot(),
                 "true_gaba":g.hx(gaba),"true_bits":list(bits),
                 "source_V":g.hx(net.state.V_mV[list(g.SOURCES)]),"source_w":g.hx(net.state.w_pA[list(g.SOURCES)]),
                 "transition_mode":previous_mode,"next_mode":mode,
                 "state_sha256":parent.physical_state_digest(net,np),
                 "rng_sha256":pinned.sha(pinned.canonical(net.rng.bit_generator.state))}
            if t==d.STEPS:
                rows.append(row)
                break
            group,decision=policy.act()
            require(group is None or type(group) is int and group in (0,1),"invalid group")
            require(group==p.action(policy.plan,t%p.BLOCK),"held plan violation")
            used+=group is not None
            if (t+1)%p.BLOCK==0:
                require(used==(t+1)//p.BLOCK*p.ON,"block budget violation")
            u=np.zeros(32,dtype=np.float64)
            u[list(d.B)]=300.
            if group is not None:
                u[list(d.GROUPS[group])]=500.
            net.gain=1.
            row.update(group=group,decision=decision,source_inputs_pA=[500. if group==j else 0. for j in range(2)],
                       applied_gain=1.,direct_B_pA=300.,topology_sha256=matrix,cumulative_stim_ticks=used)
            rows.append(row)
            metrics=net.step(external_current_pA=u)
            require(all(math.isfinite(float(v)) for v in metrics.values()),"nonfinite native metric")
            require(np.isfinite(net.state.V_mV).all() and not np.any(net.state.V_mV<net.np.V_min_mV)
                    and not np.any(net.state.V_mV>net.np.V_max_mV),"voltage envelope")
            neural.gain.check_current(net._I_ext_buffer,u,1.,network.GAIN_CURRENT_SCALE_PA,np)
            require(parent.matrix_digest(net.W_exc.to_dense(),net.W_inh.to_dense())==matrix,"unexpected recurrent topology")
            previous_gaba,previous_bits,previous_mode=gaba,bits,mode
        require(used==1600,"total effort")
        p.audit_tape(rows,arm)
        all_band=[.4<=math.fsum(float.fromhex(v) for v in x["true_gaba"])/len(d.B)<=.6 for x in rows[1:]]
        p.certify_band(all_band)
        switches=w["schedule"]
        segments=[segment(rows,tau,switches[i+1][0] if i+1<len(switches) else d.STEPS,m)
                  for i,(tau,m) in enumerate(switches)] if switches else [segment(rows,0,d.STEPS,0)]
        blocks=block_metrics(rows)
        return {"seed":seed,"arm":arm,"valid":True,"trace":rows,"segments":segments,"blocks":blocks,
                "source_current_l1_pA_ticks":2000*used,"max_recurrence_residual_nS":max_residual,
                "contradictions":sum(x["policy"]["filter"]["event"]==d.CONTRADICTION for x in rows)}
    except (ValueError,RuntimeError,ArithmeticError) as exc:
        return {"seed":seed,"arm":arm,"valid":False,"failure":str(exc),"failure_tick":t,"trace":rows}


def pair(w: dict,episodes: list[dict]) -> dict:
    by={x["arm"]:x for x in episodes}
    require(len(episodes)==len(p.ARMS) and set(by)==set(p.ARMS),"arm roster")
    if any(not x["valid"] for x in episodes):
        return {**w,"valid":False,"reason":"invalid episode"}
    ref,em=by[p.ARMS[0]],by[p.ARMS[1]]
    if {k:v for k,v in ref.items() if k!="arm"}!={k:v for k,v in em.items() if k!="arm"}:
        return {**w,"valid":False,"reason":"exact emulator divergence"}
    def exogenous(x):
        return [(r["rng_sha256"],r["noise"],r["erasures"]) for r in x["trace"]]
    common=exogenous(ref)
    if any(exogenous(x)!=common or x["trace"][0]["state_sha256"]!=ref["trace"][0]["state_sha256"]
           or x["source_current_l1_pA_ticks"]!=3200000 for x in episodes):
        return {**w,"valid":False,"reason":"initial/exogenous/total effort mismatch"}
    maximum=0
    for t in range(d.STEPS):
        counts=[x["trace"][t]["cumulative_stim_ticks"] for x in episodes]
        spread=max(counts)-min(counts)
        maximum=max(maximum,spread)
        if spread>p.ON or ((t+1)%p.BLOCK==0 and any(n!=(t+1)//p.BLOCK*p.ON for n in counts)):
            return {**w,"valid":False,"reason":"prefix spread or exact block parity"}
    return {**w,"valid":True,"exact_emulator_equal":True,"maximum_prefix_difference_stim_ticks":maximum,
            "endpoints":{a:{k:v for k,v in x.items() if k not in ("trace","seed","arm")} for a,x in by.items()}}


def endpoints(segs: list[dict]) -> dict:
    reach=[x for x in segs if x["reachable"]]
    disconnected=[x for x in segs if not x["reachable"]]
    require(bool(reach),"empty reachable roster")
    mean=lambda field,rows:math.fsum(x[field] for x in rows)/len(rows)
    return {"segments":len(segs),"reachable_segments":len(reach),"disconnected_segments":len(disconnected),
            "I20":sum(s["I20"] for s in segs),"disconnect_I20":sum(s["I20"] for s in disconnected),
            "J10":sum(s["J10"] for s in reach),"B10":sum(s["B10"] for s in reach),
            "mean_correct_fraction":mean("correct_fraction",segs),"mean_stale_fraction":mean("stale_fraction",segs),
            "mean_ambiguous_fraction":mean("ambiguous_fraction",segs),
            "mean_reachable_band_fraction":mean("band_fraction",reach),
            "mean_reachable_normalized_occupancy":mean("normalized_occupancy",reach),
            "mean_reachable_mae_nS":mean("mean_abs_error_nS",reach),
            "source_spike_events":sum(s["source_spike_events"] for s in segs),
            "source_spike_ticks":sum(s["source_spike_ticks"] for s in segs),
            "connected_arrivals":sum(s["connected_arrivals"] for s in segs),
            "arrival_ticks":sum(s["arrival_ticks"] for s in segs),
            "longest_arrival_gap":max(s["longest_arrival_gap"] for s in segs),
            "connected_stim_below_ticks":sum(s["connected_stim_below_ticks"] for s in reach),
            "disconnected_stim_ticks":sum(s["disconnected_stim_ticks"] for s in disconnected)}


FIELDS=("I20","J10","B10","mean_stale_fraction","mean_ambiguous_fraction","mean_reachable_band_fraction",
        "mean_reachable_normalized_occupancy","mean_reachable_mae_nS","connected_arrivals",
        "connected_stim_below_ticks","disconnected_stim_ticks")


def contrasts(worlds: list[dict]) -> dict:
    definitions={"DUAL_MINUS_CONTROL_ONLY":(1,-1,0,0),"DUAL_MINUS_INFO_ONLY":(1,0,-1,0),
                 "CONTROL_ONLY_MINUS_FIXED":(0,1,0,-1),"INFO_ONLY_MINUS_FIXED":(0,0,1,-1),
                 "DUAL_MINUS_FIXED":(1,0,0,-1),"INTERACTION":(1,-1,-1,1)}
    arms=("DUAL","CONTROL_ONLY","INFO_ONLY","FIXED_ALTERNATE")
    by=[(w["seed"],[endpoints(w["endpoints"][a]["segments"]) for a in arms]) for w in worlds]
    out={}
    for name,weights in definitions.items():
        per=[{"seed":seed,"difference":{k:math.fsum(weight*x[k] for weight,x in zip(weights,values,strict=True)) for k in FIELDS}}
             for seed,values in by]
        out[name]={"per_world":per,
                   "mean_difference":{k:math.fsum(v["difference"][k] for v in per)/len(per) for k in FIELDS},
                   "sign_counts":{k:{"positive":sum(v["difference"][k]>1e-12 for v in per),
                                      "negative":sum(v["difference"][k]<-1e-12 for v in per),
                                      "zero":sum(abs(v["difference"][k])<=1e-12 for v in per)} for k in FIELDS}}
    return out


def summarize(worlds: list[dict],episodes: list[dict],certificate: dict) -> dict:
    passed=len(worlds)==len(SEEDS) and len(episodes)==len(SEEDS)*len(p.ARMS) and all(w["valid"] for w in worlds)
    report={"experiment":"CNEH-EXP-05","authority":"PROSPECTIVE_INTERNAL_ENGINEERED_DUAL_CONTROL_PILOT",
            "all_instrument_checks_passed":passed,"scientific_promotion_authorized":False,
            "external_replication":"NOT_TESTED","physical_energy":"NOT_VALIDATED",
            "reachability_certificate":certificate,"worlds":len(worlds),"episodes":len(episodes),
            "valid_worlds":sum(w["valid"] for w in worlds),
            "invalid_worlds":[{"seed":w["seed"],"reason":w.get("reason")} for w in worlds if not w["valid"]]}
    if not passed:
        report["aggregate_status"]="BLOCKED_NO_SURVIVOR_AVERAGING"
        return report
    ood=[w for w in worlds if w["schedule"]]
    controls=[w for w in worlds if not w["schedule"]]
    report["exact_emulator_equal_worlds"]=sum(w["exact_emulator_equal"] for w in worlds)
    report["max_recurrence_residual_nS"]=max(x["max_recurrence_residual_nS"] for x in episodes)
    report["maximum_prefix_difference_stim_ticks"]=max(w["maximum_prefix_difference_stim_ticks"] for w in worlds)
    report["source_current_l1_pA_ticks_per_episode"]=3200000
    report["no_change_contradictions"]={a:sum(w["endpoints"][a]["contradictions"] for w in controls) for a in p.ARMS}
    report["arm_metrics"]={a:endpoints([s for w in ood for s in w["endpoints"][a]["segments"]]) for a in p.ARMS}
    require(all(x["segments"]==36 and x["reachable_segments"]==24 and x["disconnected_segments"]==12 for x in report["arm_metrics"].values()),"segment roster")
    report["no_change_metrics"]={a:endpoints([s for w in controls for s in w["endpoints"][a]["segments"]]) for a in p.ARMS}
    report["paired_contrasts"]=contrasts(ood)
    report["selected_plan_counts"]={a:{f"{g0}_{wave}":sum(tuple(b["plan"])==(g0,wave) for w in ood for b in w["endpoints"][a]["blocks"])
                                       for g0,wave in p.PLANS} for a in p.ARMS}
    return report


def payload(source: Path) -> tuple[dict[str,bytes],bool]:
    certificate=p.certificate()
    require(d.MODES==q.MODES and neural.DECAY==q.DECAY and d.EPS==q.EPS and neural.WEIGHT==.5,"parent contract drift")
    lock_path=HERE.parent/"cneh_exp_01"/"bnsyn_integration_contract.json"
    lock=pinned.strict_json(lock_path.read_bytes())
    require(lock["source"]["commit"]=="c1de425ce4ece362e7f2feb2d9f24da5d3231014","runtime source drift")
    before=pinned.validate_source(source,lock)
    rt=pinned.load_runtime(source,lock)
    episodes,worlds=[],[]
    for seed in SEEDS:
        w=world(seed)
        tape=d.sensor_tape(seed)
        es=[episode(w,a,rt,tape) for a in p.ARMS]
        worlds.append(pair(w,es))
        episodes.extend(es)
    require(pinned.validate_source(source,lock)==before,"source changed")
    report=summarize(worlds,episodes,certificate)
    files={"preregistration.md":(HERE/"PREREGISTRATION.md").read_bytes(),
           "implementation.json":pinned.canonical({"runner_sha256":pinned.sha(Path(__file__).read_bytes()),
             "policy_sha256":pinned.sha(Path(p.__file__).read_bytes()),
             "runtime_lock_sha256":pinned.sha(lock_path.read_bytes()),"source":lock["source"]}),
           "certificate.json":pinned.canonical(certificate),
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
        raise FileExistsError("immutable output")
    files,passed=payload(args.source)
    if not args.verify:
        parent.write_bundle(args.out,files)
    parent.verify_payload(args.out,files)
    print(files["verdict.json"].decode().strip())
    raise SystemExit(0 if passed else 2)


if __name__=="__main__":
    main()
