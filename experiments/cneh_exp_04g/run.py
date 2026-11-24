"""Prospective source-excitability and known-model actuator qualification."""
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
from experiments.cneh_exp_04f import policy as f, run as prior

HERE=Path(__file__).resolve().parent
pinned,parent,neural=d.pinned,d.parent,d.neural
require=prior.require
SOURCES=tuple(x for g in d.GROUPS for x in g)
B_SEEDS=tuple(range(89001,89009))
C_SEEDS=tuple(range(89201,89209))+tuple(range(89301,89305))
WIDTHS=(80,160,400)
B_ARMS=tuple(f"P{w}_{a}" for w in WIDTHS for a in ("NATIVE","CLAMP"))+("P160_NATIVE_EMULATOR",)
C_ARMS=("RESPONSE_ROLLING","EXACT_EMULATOR","MODEL_ORACLE","ROUTE_ORACLE")
CURRENTS=(0,100,130,160,200,300,400,500)


def hx(values) -> list[str]:
    out=[float(v) for v in values]
    require(all(math.isfinite(v) for v in out),"nonfinite physical value")
    return [v.hex() for v in out]


def geometry(t: int,width: int) -> int | None:
    require(type(t) is int and 0<=t<d.STEPS and width in WIDTHS,"invalid packet coordinates")
    return (t//(2*width))%2 if t%(2*width)<width else None


def b_config(arm: str) -> tuple[int,bool]:
    require(arm in B_ARMS,"unknown source arm")
    return int(arm.split("_")[0][1:]),arm.endswith("CLAMP")


def c_world(seed: int) -> dict:
    require(seed in C_SEEDS,"unknown OOD seed")
    rng=random.Random(seed)
    sequence=d.SEQUENCES[(seed-89201)%len(d.SEQUENCES)]
    schedule=[(rng.randint(lo,hi),m) for (lo,hi),m in zip(d.WINDOWS,sequence,strict=True)] if seed<89301 else []
    return {"seed":seed,"schedule":schedule}


def route_action(t: int,mode: int,held: int | None) -> tuple[int | None,int | None]:
    require(0<=t<d.STEPS and mode in d.ALL,"invalid route coordinates")
    if not f.is_on(t):
        return None,held
    if t%f.PACKET==0:
        connected=[g for g in range(2) if q.MODES[mode][g]]
        held=connected[0] if len(connected)==1 else (t//f.PACKET)%2
    require(held in (0,1),"missing held route")
    return held,held


def model_oracle_act(policy: f.Policy,mode: int):
    require(mode in d.ALL,"invalid oracle mode")
    saved=policy.candidates
    try:
        policy.candidates=(mode,)
        return policy.act()
    finally:
        policy.candidates=saved


def clamp_source(net,np,enabled: bool) -> tuple[list[str],list[str]]:
    targets=list(SOURCES)
    before=net.state.w_pA.copy()
    if enabled:
        other=[net.state.V_mV.copy(),net.state.spiked.copy(),net.g_ampa.copy(),net.g_nmda.copy(),net.g_gabaa.copy()]
        gain=net.gain
        net.state.w_pA[targets]=0.
        expected=before.copy()
        expected[targets]=0.
        require(np.array_equal(net.state.w_pA,expected),"clamp scope violated")
        require(all(np.array_equal(x,y) for x,y in zip(other,(net.state.V_mV,net.state.spiked,net.g_ampa,net.g_nmda,net.g_gabaa),strict=True)) and net.gain==gain,"clamp mutated non-target state")
    else:
        require(np.array_equal(net.state.w_pA,before),"native source state changed")
    return hx(before[targets]),hx(net.state.w_pA[targets])


def calibrate(rt: dict) -> list[dict]:
    np,config=rt["np"],rt["config"]
    adex=importlib.import_module("bnsyn.neuron.adex")
    p=config.AdExParams()
    require((p.gL_nS,p.EL_mV,p.VT_mV,p.DeltaT_mV,p.tauw_ms,p.b_pA)==(10.,-70.,-55.,2.,200.,80.),"native parameters drifted")
    result=[]
    for current in CURRENTS:
        for clamp in (False,True):
            state=adex.AdExState(V_mV=np.array([p.EL_mV]),w_pA=np.zeros(1),spiked=np.zeros(1,dtype=bool))
            rows=[]
            for t in range(d.STEPS):
                before=float(state.w_pA[0])
                voltage=float(state.V_mV[0])
                if clamp:
                    state.w_pA[0]=0.
                applied=float(state.w_pA[0])
                require(applied==(0. if clamp else before),"single-cell intervention")
                state=adex.adex_step(state,p,.1,np.zeros(1),np.full(1,float(current)))
                v,w=float(state.V_mV[0]),float(state.w_pA[0])
                require(all(math.isfinite(x) for x in (v,w,voltage,before,applied)) and -100<=v<=50,"calibration state envelope")
                rows.append({"tick":t+1,"V_before":voltage.hex(),"V_after":v.hex(),"w_before":before.hex(),"w_applied":applied.hex(),"w_after":w.hex(),"spike":int(state.spiked[0])})
            spikes=[row["tick"] for row in rows if row["spike"]]
            result.append({"current_pA":current,"clamp":clamp,"first_spike_ticks":spikes[0] if spikes else None,"spikes":len(spikes),"second_half_spikes":sum(t>1600 for t in spikes),"trace":rows})
    return result


def replay(rows: list[dict],stage: str,arm: str) -> None:
    require(len(rows)==d.STEPS+1 and [r["tick"] for r in rows]==list(range(d.STEPS+1)),"trace roster")
    if stage=="B":
        width,clamp=b_config(arm)
        for t,row in enumerate(rows[:-1]):
            require(row["group"]==geometry(t,width),"source action replay")
            require(row["w_applied"]==(["0x0.0p+0"]*8 if clamp else row["source_w"]),"clamp evidence mismatch")
        return
    if arm in C_ARMS[:2]:
        f.audit_tape(rows,f.ARMS[0])
        return
    policy=f.Policy(f.ARMS[0]) if arm=="MODEL_ORACLE" else None
    held=None
    for t,row in enumerate(rows):
        if policy is not None:
            policy.observe(d.parse_obs(row))
            require(row["policy"]==policy.snapshot(),"oracle filter replay")
        else:
            require(row["policy"] is None,"route oracle has inferred state")
        if t==d.STEPS:
            break
        if policy is not None:
            action=model_oracle_act(policy,row["next_mode"])
        else:
            group,held=route_action(t,row["next_mode"],held)
            action=(group,"ORACLE_ROUTE" if group is not None else "REST",None)
        require((row["group"],row["kind"],row["packet_decision"])==action,"oracle action replay")


def physical(rows: list[dict],start: int,end: int,mode: int,width: int,score_ident: bool) -> dict:
    acts,obs=rows[start:end],rows[start+1:end+1]
    require(len(acts)==len(obs)==end-start>0 and all(r["next_mode"]==mode for r in acts) and all(r["transition_mode"]==mode for r in obs),"segment roster")
    vals=[math.fsum(float.fromhex(v) for v in row["true_gaba"])/len(d.B) for row in obs]
    band=[.4<=v<=.6 for v in vals]
    arrivals=[]
    spike_events=spike_ticks=connected_below=disconnected_stim=0
    for old,row in zip(acts,obs,strict=True):
        n=(sum(old["true_bits"][:4]),sum(old["true_bits"][4:]))
        spike_events+=sum(n)
        spike_ticks+=bool(sum(n))
        arrivals.append(sum(q.MODES[mode][g]*n[g] for g in range(2)))
        group=old["group"]
        if group is not None:
            disconnected_stim+=mode==3
            connected_below+=bool(q.MODES[mode][group]) and math.fsum(float.fromhex(v) for v in old["true_gaba"])/len(d.B)<.4
    packets=[]
    period=2*width
    for t in range(((start+period-1)//period)*period,end,period):
        if t+width>end:
            continue
        g=rows[t]["group"]
        require(g in (0,1) and all(rows[j]["group"]==g for j in range(t,t+width)),"packet changed group")
        counts=[sum(rows[j+1]["true_bits"][g*4:g*4+4]) for j in range(t,t+width)]
        first=next((j+1 for j,n in enumerate(counts) if n),None)
        packets.append({"start":t,"group":g,"connected":bool(q.MODES[mode][g]),"first_spike_ticks":first,"spikes":sum(counts)})
    result={"start":start,"end":end,"mode":mode,"reachable":mode!=3,"ticks":end-start,
            "B10":e.longest(band)>=10 if mode!=3 else None,
            "band_fraction":sum(band)/len(band),"mean_abs_error_nS":math.fsum(abs(x-.5) for x in vals)/len(vals),
            "spike_events":spike_events,"spike_ticks":spike_ticks,"connected_arrival_events":sum(arrivals),
            "arrival_ticks":sum(bool(n) for n in arrivals),"longest_arrival_gap":e.longest([n==0 for n in arrivals]),
            "connected_stim_below_ticks":connected_below,"disconnected_stim_ticks":disconnected_stim,
            "packets":packets,"silent_packets":sum(p["spikes"]==0 for p in packets)}
    if score_ident:
        correct=[row["policy"]["candidates"]==[mode] for row in obs]
        result["I20"]=e.longest(correct)>=20
        result["J10"]=e.longest([i and b for i,b in zip(correct,band,strict=True)])>=10 if mode!=3 else None
    return result


def episode(stage: str,w: dict,arm: str,rt: dict,tape: list | None) -> dict:
    np,network,config=(rt[k] for k in ("np","network","config"))
    seed=w["seed"]
    schedule=dict(w["schedule"])
    width,clamp=b_config(arm) if stage=="B" else (160,False)
    net=network.Network(network.NetworkParams(N=32,frac_inhib=.25,p_conn=0.),
                        config.AdExParams(),config.SynapseParams(),config.CriticalityParams(),
                        dt_ms=.1,rng=np.random.default_rng(seed),backend="reference")
    require(net.nE==24 and net.nI==8 and not net._use_torch and net.syn.tau_GABAA_ms==6.,"runtime boundary")
    connectivity=importlib.import_module("bnsyn.connectivity").SparseConnectivity
    mode=2 if stage=="B" else 0
    matrix=neural.apply_mode(net,mode,np,connectivity)
    require(not np.any(net.W_exc.to_dense()[list(SOURCES)]) and not np.any(net.W_inh.to_dense()[list(SOURCES)]),"source recurrent input")
    policy=f.Policy(f.ARMS[0]) if stage=="C" and arm!="ROUTE_ORACLE" else None
    rows=[]
    used=[0,0]
    held=None
    prev_gaba=prev_bits=prev_mode=None
    max_residual=0.
    t=0
    try:
        for t in range(d.STEPS+1):
            gaba=tuple(float(net.g_gabaa[j]) for j in d.B)
            bits=tuple(int(net.state.spiked[j]) for j in SOURCES)
            require(all(math.isfinite(v) and v>=0 for v in gaba),"invalid conductance")
            if t:
                count=sum(q.MODES[prev_mode][g]*sum(prev_bits[g*4:g*4+4]) for g in range(2))
                residual=max(abs(x-q.DECAY*(y+.5*count)) for x,y in zip(gaba,prev_gaba,strict=True))
                max_residual=max(max_residual,residual)
                require(residual<=1e-9,"actual recurrence mismatch")
            if stage=="C":
                noise,mask=tape[t]
                obs=d.public_observation(t,gaba,bits,noise,mask)
                public={**d.obs_record(obs),"noise":hx(noise),"erasures":list(mask)}
                if policy is not None:
                    policy.observe(obs)
                    if t:
                        require(prev_mode in policy.instant,"instantaneous false exclusion")
                    if not schedule:
                        require(policy.event!=d.CONTRADICTION and 0 in policy.candidates,"no-change contradiction")
            else:
                public={"tick":t}
            if t in schedule:
                before=parent.physical_state_digest(net,np)
                mode=schedule[t]
                matrix=neural.apply_mode(net,mode,np,connectivity)
                require(parent.physical_state_digest(net,np)==before,"topology changed physical state")
            row={**public,"policy":None if policy is None else policy.snapshot(),
                 "true_gaba":hx(gaba),"true_bits":list(bits),
                 "source_V":hx(net.state.V_mV[list(SOURCES)]),"source_w":hx(net.state.w_pA[list(SOURCES)]),
                 "source_g_ampa":hx(net.g_ampa[list(SOURCES)]),"source_g_nmda":hx(net.g_nmda[list(SOURCES)]),
                 "B_voltage_mV":hx(net.state.V_mV[list(d.B)]),"transition_mode":prev_mode,"next_mode":mode,
                 "state_sha256":parent.physical_state_digest(net,np),
                 "rng_sha256":pinned.sha(pinned.canonical(net.rng.bit_generator.state))}
            if t==d.STEPS:
                rows.append(row)
                break
            if stage=="B":
                group=geometry(t,width)
                kind,decision=("PULSE" if group is not None else "REST"),None
            elif arm in C_ARMS[:2]:
                group,kind,decision=policy.act()
            elif arm=="MODEL_ORACLE":
                group,kind,decision=model_oracle_act(policy,mode)
            else:
                group,held=route_action(t,mode,held)
                kind,decision=("ORACLE_ROUTE" if group is not None else "REST"),None
            require(group is None or type(group) is int and group in (0,1),"invalid actuator")
            require((group is not None)==(t%(2*width)<width),"budget slots")
            if group is not None:
                used[group]+=1
            require(sum(used)==width*(t//(2*width))+min(t%(2*width)+1,width),"prefix effort")
            before,applied=clamp_source(net,np,clamp)
            require(before==row["source_w"],"clamp state boundary")
            u=np.zeros(32,dtype=np.float64)
            u[list(d.B)]=300.
            if group is not None:
                u[list(d.GROUPS[group])]=500.
            net.gain=1.
            row.update(group=group,kind=kind,packet_decision=decision,w_applied=applied,topology_sha256=matrix,
                       source_inputs_pA=[500. if group==g else 0. for g in range(2)],applied_gain=1.,direct_B_pA=300.)
            rows.append(row)
            metrics=net.step(external_current_pA=u)
            require(all(math.isfinite(float(v)) for v in metrics.values()),"nonfinite metrics")
            require(np.isfinite(net.state.V_mV).all() and not np.any(net.state.V_mV<net.np.V_min_mV) and not np.any(net.state.V_mV>net.np.V_max_mV),"voltage envelope")
            neural.gain.check_current(net._I_ext_buffer,u,1.,network.GAIN_CURRENT_SCALE_PA,np)
            require(parent.matrix_digest(net.W_exc.to_dense(),net.W_inh.to_dense())==matrix,"unexpected topology")
            prev_gaba,prev_bits,prev_mode=gaba,bits,mode
        require(sum(used)==1600 and (stage!="B" or used==[800,800]),"total/group effort")
        replay(rows,stage,arm)
        switches=w["schedule"]
        segments=[physical(rows,0,d.STEPS,2,width,False)] if stage=="B" else [
            physical(rows,tau,switches[i+1][0] if i+1<len(switches) else d.STEPS,m,width,arm in C_ARMS[:2])
            for i,(tau,m) in enumerate(switches)]
        if stage=="C" and not switches:
            segments=[physical(rows,0,d.STEPS,0,width,arm in C_ARMS[:2])]
        return {"stage":stage,"seed":seed,"arm":arm,"valid":True,"trace":rows,"segments":segments,
                "group_stim_ticks":used,"source_current_l1_pA_ticks":2000*sum(used),"max_recurrence_residual_nS":max_residual}
    except (ValueError,RuntimeError,ArithmeticError) as exc:
        return {"stage":stage,"seed":seed,"arm":arm,"valid":False,"failure":str(exc),"failure_tick":t,"trace":rows}


def pair(stage: str,w: dict,episodes: list[dict]) -> dict:
    arms=B_ARMS if stage=="B" else C_ARMS
    by={x["arm"]:x for x in episodes}
    require(len(episodes)==len(arms) and set(by)==set(arms),"arm roster")
    base={**w,"stage":stage}
    if any(not x["valid"] for x in episodes):
        return {**base,"valid":False,"reason":"invalid episode"}
    reference=by["P160_NATIVE" if stage=="B" else C_ARMS[0]]
    emulator=by["P160_NATIVE_EMULATOR" if stage=="B" else C_ARMS[1]]
    if {k:v for k,v in reference.items() if k!="arm"}!={k:v for k,v in emulator.items() if k!="arm"}:
        return {**base,"valid":False,"reason":"emulator divergence"}
    def tape(x):
        return [(r["rng_sha256"],r.get("noise"),r.get("erasures")) for r in x["trace"]]
    ref=tape(reference)
    if any(tape(x)!=ref or x["trace"][0]["state_sha256"]!=reference["trace"][0]["state_sha256"] or x["source_current_l1_pA_ticks"]!=3200000 for x in episodes):
        return {**base,"valid":False,"reason":"initial/exogenous/effort mismatch"}
    def actions(x):
        return [r.get("group") for r in x["trace"][:-1]]
    if stage=="B":
        if any(actions(by[f"P{width}_NATIVE"])!=actions(by[f"P{width}_CLAMP"]) for width in WIDTHS):
            return {**base,"valid":False,"reason":"adaptation pair prefix mismatch"}
        if any(x["group_stim_ticks"]!=[800,800] for x in episodes):
            return {**base,"valid":False,"reason":"group effort mismatch"}
    else:
        slots=[g is not None for g in actions(reference)]
        if any([g is not None for g in actions(x)]!=slots for x in episodes):
            return {**base,"valid":False,"reason":"oracle prefix mismatch"}
    return {**base,"valid":True,"exact_emulator_equal":True,
            "endpoints":{a:{k:v for k,v in x.items() if k not in ("trace","arm","stage","seed")} for a,x in by.items()}}


def endpoints(segs: list[dict]) -> dict:
    reach=[s for s in segs if s["reachable"]]
    require(bool(reach),"missing reachable segments")
    packets=[p for s in segs for p in s["packets"]]
    lat=[p["first_spike_ticks"] for p in packets if p["first_spike_ticks"] is not None]
    out={"segments":len(segs),"reachable_segments":len(reach),"B10":sum(s["B10"] for s in reach),
         "mean_reachable_band_fraction":math.fsum(s["band_fraction"] for s in reach)/len(reach),
         "mean_reachable_mae_nS":math.fsum(s["mean_abs_error_nS"] for s in reach)/len(reach),
         "spike_events":sum(s["spike_events"] for s in segs),"spike_ticks":sum(s["spike_ticks"] for s in segs),
         "connected_arrival_events":sum(s["connected_arrival_events"] for s in segs),
         "arrival_ticks":sum(s["arrival_ticks"] for s in segs),
         "max_arrival_gap":max(s["longest_arrival_gap"] for s in segs),
         "connected_stim_below_ticks":sum(s["connected_stim_below_ticks"] for s in reach),
         "disconnected_stim_ticks":sum(s["disconnected_stim_ticks"] for s in segs),
         "packets":len(packets),"silent_packets":sum(s["silent_packets"] for s in segs),
         "mean_packet_latency_given_response_ticks":math.fsum(lat)/len(lat) if lat else None}
    if all("I20" in s for s in segs):
        out.update(I20=sum(s["I20"] for s in segs),J10=sum(s["J10"] for s in reach))
    return out


FIELDS=("B10","mean_reachable_band_fraction","mean_reachable_mae_nS","spike_events","spike_ticks",
        "connected_arrival_events","arrival_ticks","connected_stim_below_ticks","silent_packets")


def contrast(worlds: list[dict],a: str,b: str) -> dict:
    per=[]
    for w in worlds:
        x,y=(endpoints(w["endpoints"][arm]["segments"]) for arm in (a,b))
        per.append({"seed":w["seed"],"difference":{k:x[k]-y[k] for k in FIELDS}})
    return {"per_world":per,"mean_difference":{k:math.fsum(x["difference"][k] for x in per)/len(per) for k in FIELDS}}


def summarize(cal: list[dict],worlds: list[dict],episodes: list[dict]) -> dict:
    passed=len(worlds)==len(B_SEEDS)+len(C_SEEDS) and len(episodes)==len(B_SEEDS)*len(B_ARMS)+len(C_SEEDS)*len(C_ARMS) and all(w["valid"] for w in worlds)
    report={"experiment":"CNEH-EXP-04G","authority":"PROSPECTIVE_SIMULATOR_MECHANISTIC_QUALIFICATION",
            "scientific_promotion_authorized":False,"external_replication":"NOT_TESTED","physical_energy":"NOT_VALIDATED",
            "all_instrument_checks_passed":passed,"worlds":len(worlds),"episodes":len(episodes),
            "valid_worlds":sum(w["valid"] for w in worlds),"invalid_worlds":[{"stage":w["stage"],"seed":w["seed"],"reason":w.get("reason")} for w in worlds if not w["valid"]],
            "calibration":[{k:v for k,v in row.items() if k!="trace"} for row in cal]}
    for clamp in (False,True):
        rows=[x for x in cal if x["clamp"]==clamp]
        first=[x["current_pA"] for x in rows if x["spikes"]]
        sustained=[x["current_pA"] for x in rows if x["second_half_spikes"]]
        report["CLAMP" if clamp else "NATIVE"]={"lowest_grid_eliciting_pA":min(first) if first else None,
            "lowest_grid_second_half_spike_pA":min(sustained) if sustained else None}
    if not passed:
        report["aggregate_status"]="BLOCKED_NO_SURVIVOR_AVERAGING"
        return report
    bw=[w for w in worlds if w["stage"]=="B"]
    cw=[w for w in worlds if w["stage"]=="C" and w["schedule"]]
    controls=[w for w in worlds if w["stage"]=="C" and not w["schedule"]]
    report["max_recurrence_residual_nS"]=max(x["max_recurrence_residual_nS"] for x in episodes)
    report["exact_emulator_equal_worlds"]=sum(w["exact_emulator_equal"] for w in worlds)
    report["B_metrics"]={a:endpoints([s for w in bw for s in w["endpoints"][a]["segments"]]) for a in B_ARMS}
    report["C_metrics"]={a:endpoints([s for w in cw for s in w["endpoints"][a]["segments"]]) for a in C_ARMS}
    report["C_no_change_metrics"]={a:endpoints([s for w in controls for s in w["endpoints"][a]["segments"]]) for a in C_ARMS}
    contrasts={f"P{width}_CLAMP_MINUS_NATIVE":contrast(bw,f"P{width}_CLAMP",f"P{width}_NATIVE") for width in WIDTHS}
    for width in (80,400):
        contrasts[f"P{width}_NATIVE_MINUS_P160_NATIVE"]=contrast(bw,f"P{width}_NATIVE","P160_NATIVE")
        a=contrasts[f"P{width}_CLAMP_MINUS_NATIVE"]
        b=contrasts["P160_CLAMP_MINUS_NATIVE"]
        require([x["seed"] for x in a["per_world"]]==[x["seed"] for x in b["per_world"]],"factorial pairing")
        per=[{"seed":x["seed"],"difference":{k:x["difference"][k]-y["difference"][k] for k in FIELDS}} for x,y in zip(a["per_world"],b["per_world"],strict=True)]
        contrasts[f"P{width}_X_CLAMP_INTERACTION"]={"per_world":per,"mean_difference":{k:math.fsum(x["difference"][k] for x in per)/len(per) for k in FIELDS}}
    report["B_contrasts"]=contrasts
    report["C_contrasts"]={"MODEL_ORACLE_MINUS_RESPONSE":contrast(cw,"MODEL_ORACLE","RESPONSE_ROLLING"),
                            "ROUTE_ORACLE_MINUS_MODEL_ORACLE":contrast(cw,"ROUTE_ORACLE","MODEL_ORACLE")}
    return report


def payload(source: Path) -> tuple[dict[str,bytes],bool]:
    require(d.MODES==q.MODES and neural.DECAY==q.DECAY and d.EPS==q.EPS and neural.WEIGHT==.5,"parent analytic contract drift")
    lock_path=HERE.parent/"cneh_exp_01"/"bnsyn_integration_contract.json"
    lock=pinned.strict_json(lock_path.read_bytes())
    require(lock["source"]["commit"]=="c1de425ce4ece362e7f2feb2d9f24da5d3231014","source drift")
    before=pinned.validate_source(source,lock)
    rt=pinned.load_runtime(source,lock)
    cal=calibrate(rt)
    episodes,worlds=[],[]
    for stage,seeds,arms in (("B",B_SEEDS,B_ARMS),("C",C_SEEDS,C_ARMS)):
        for seed in seeds:
            w={"seed":seed,"schedule":[]} if stage=="B" else c_world(seed)
            tape=None if stage=="B" else d.sensor_tape(seed)
            es=[episode(stage,w,a,rt,tape) for a in arms]
            worlds.append(pair(stage,w,es))
            episodes.extend(es)
    require(pinned.validate_source(source,lock)==before,"simulator source changed")
    report=summarize(cal,worlds,episodes)
    files={"preregistration.md":(HERE/"PREREGISTRATION.md").read_bytes(),
           "implementation.json":pinned.canonical({"runner_sha256":pinned.sha(Path(__file__).read_bytes()),
            "parent_policy_sha256":pinned.sha(Path(f.__file__).read_bytes()),"runtime_lock_sha256":pinned.sha(lock_path.read_bytes()),"source":lock["source"]}),
           "calibration.json.gz":gzip.compress(pinned.canonical(cal),mtime=0),
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
