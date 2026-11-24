"""Read-only decomposition of sealed EXP04F model/control failure."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import itertools
import json
import math
import zipfile
from collections import Counter
from pathlib import Path

from experiments.cneh_exp_04c import qualification as q
from experiments.cneh_exp_04d import run as d
from experiments.cneh_exp_04e import audit as e
from experiments.cneh_exp_04f import policy as f, run as run

HERE = Path(__file__).resolve().parent
ARCHIVE_SHA = "0605472076bf67b86dc3db804a2d05dd1866e0f7652f0949ef72e51df7b749ae"
NAMES = {"episodes.json.gz","implementation.json","preregistration.md","verdict.json","worlds.json"}
CLASSES = ("JOINT","IDENTIFICATION_LIMITED","CONTROL_LIMITED","BOTH_LIMITED","TEMPORAL_MISMATCH")
require = run.require


def classify(correct: list[bool], band: list[bool]) -> str:
    require(len(correct)==len(band) and bool(correct),"invalid streak vectors")
    i,b=e.longest(correct)>=10,e.longest(band)>=10
    joint=e.longest([a and z for a,z in zip(correct,band,strict=True)])>=10
    if joint:
        return "JOINT"
    if i and b:
        return "TEMPORAL_MISMATCH"
    if i:
        return "CONTROL_LIMITED"
    if b:
        return "IDENTIFICATION_LIMITED"
    return "BOTH_LIMITED"


def segment(rows: list[dict], start: int, end: int, mode: int) -> dict:
    acts,obs=rows[start:end],rows[start+1:end+1]
    require(len(acts)==len(obs)==end-start>0,"segment roster")
    require(all(r["transition_mode"]==mode for r in obs) and all(r["next_mode"]==mode for r in acts),"segment truth")
    correct=[r["policy"]["candidates"]==[mode] for r in obs]
    actual=[math.fsum(float.fromhex(v) for v in r["true_gaba"])/len(d.B) for r in obs]
    band=[.4<=g<=.6 for g in actual]
    joint=[i and b for i,b in zip(correct,band,strict=True)]
    ticks=list(range(start+1,end+1))
    contingency=Counter({k:0 for k in ("CORRECT_IN","CORRECT_OUT","OTHER_IN","OTHER_OUT")})
    errors={"CORRECT":[],"OTHER":[]}
    arrival_counts=Counter({str(i):0 for i in range(9)})
    act_counts=Counter({k:0 for k in ("REST","CONNECTED","UNCONNECTED")})
    correct_below_actions=Counter(act_counts)
    post_spikes=Counter({k:0 for k in ("CONNECTED","UNCONNECTED")})
    post_spike_ticks=Counter(post_spikes)
    source_ticks=0
    source_events=0
    full,observed=set(d.ALL),set(d.ALL)
    full_flags,obs_flags=[],[]
    arrivals=[]
    for old,row,i,b,g in zip(acts,obs,correct,band,actual,strict=True):
        label="CORRECT" if i else "OTHER"
        contingency[label+("_IN" if b else "_OUT")]+=1
        errors[label].append(abs(g-d.GOAL))
        bits=tuple(old["true_bits"])
        n=(sum(bits[:4]),sum(bits[4:]))
        source_ticks+=any(n)
        source_events+=sum(n)
        k=sum(q.MODES[mode][j]*n[j] for j in range(2))
        arrivals.append(k)
        arrival_counts[str(k)]+=1
        expected=[q.DECAY*(float.fromhex(v)+.5*k) for v in old["true_gaba"]]
        require(max(abs(float.fromhex(v)-x) for v,x in zip(row["true_gaba"],expected,strict=True))<=1e-9,"arrival recurrence")
        previous,current=d.parse_obs(old),d.parse_obs(row)
        residual=q.observed_residual(previous.gaba,current.gaba)
        sup=set(q.support(d.ALL,previous.bits,residual))
        complete=set(q.support(d.ALL,bits,residual))
        require(mode in complete and complete<=sup and sup==set(row["policy"]["instant"]),"instant support")
        full.intersection_update(complete)
        observed.intersection_update(sup)
        full_flags.append(full=={mode})
        obs_flags.append(observed=={mode})
        group=old["group"]
        a="REST" if group is None else "CONNECTED" if q.MODES[mode][group] else "UNCONNECTED"
        act_counts[a]+=1
        if old["policy"]["candidates"]==[mode] and math.fsum(float.fromhex(v) for v in old["true_gaba"])/len(d.B)<.4:
            correct_below_actions[a]+=1
        if group is not None:
            response=sum(row["true_bits"][group*4:group*4+4])
            post_spikes[a]+=response
            post_spike_ticks[a]+=bool(response)
    packets=[]
    for t in range(((start+f.PACKET-1)//f.PACKET)*f.PACKET,end,f.PACKET):
        if t+f.ON>end:
            continue
        group=rows[t]["group"]
        require(group in (0,1) and all(rows[j]["group"]==group for j in range(t,t+f.ON)),"packet identity")
        counts=[sum(rows[j+1]["true_bits"][group*4:group*4+4]) for j in range(t,t+f.ON)]
        first=next((j+1 for j,n in enumerate(counts) if n),None)
        packets.append({"start":t,"group":group,"connected":bool(q.MODES[mode][group]),
                        "purpose":rows[t]["packet_decision"]["purpose"],"first_spike_latency_ticks":first,
                        "spike_events":sum(counts),"spike_ticks":sum(bool(n) for n in counts)})
    no_response_by_group=[]
    for g in range(2):
        selected=[x["first_spike_latency_ticks"] is None for x in packets if x["group"]==g]
        no_response_by_group.append({"packets":len(selected),"silent":sum(selected),"longest_silent_streak":e.longest(selected)})
    result={"start":start,"end":end,"mode":mode,"reachable":mode!=3,"ticks":end-start,
            "I10":e.longest(correct)>=10,"I20":e.longest(correct)>=20,"B10":e.longest(band)>=10,"J10":e.longest(joint)>=10 if mode!=3 else None,
            "status":classify(correct,band) if mode!=3 else "DISCONNECTED_NOT_APPLICABLE",
            "longest_ident":e.longest(correct),"longest_band":e.longest(band),"longest_joint":e.longest(joint),
            "I20_tick":d.first_run(correct,ticks,20),"B10_tick":d.first_run(band,ticks,10),
            "J10_tick":d.first_run(joint,ticks,10) if mode!=3 else None,
            "full_ceiling_I20":e.longest(full_flags)>=20,"observed_ceiling_I20":e.longest(obs_flags)>=20,
            "contingency":dict(contingency),"abs_error_sum":{k:math.fsum(v) for k,v in errors.items()},
            "below":sum(v<.4 for v in actual),"above":sum(v>.6 for v in actual),"in_band":sum(band),
            "source_spike_ticks":source_ticks,"source_spike_events":source_events,
            "arrival_multiplicity":dict(arrival_counts),"longest_arrival_free_run":e.longest([n==0 for n in arrivals]),
            "actions":dict(act_counts),"correct_below_actions":dict(correct_below_actions),
            "post_stim_spikes":dict(post_spikes),"post_stim_spike_ticks":dict(post_spike_ticks),
            "packets":packets,"no_response_by_group":no_response_by_group}
    require(sum(contingency.values())==sum(arrival_counts.values())==sum(act_counts.values())==end-start,"incomplete partition")
    return result


def load(path: Path) -> tuple[list,list,dict]:
    require(path.is_file() and not path.is_symlink() and e.sha_file(path)==ARCHIVE_SHA,"archive digest")
    with zipfile.ZipFile(path) as z:
        prefix="cneh04f/"
        names=[i.filename for i in z.infolist() if not i.is_dir()]
        require(len(names)==len(set(names)) and set(names)=={prefix+x for x in NAMES|{"SHA256SUMS"}}|{"cneh04f-install.json"},"archive roster")
        hashes={}
        for name in sorted(NAMES):
            with z.open(prefix+name) as stream:
                hashes[name]=hashlib.file_digest(stream,"sha256").hexdigest()
        manifest="".join(f"{hashes[k]}  {k}\n" for k in sorted(hashes)).encode("ascii")
        require(z.read(prefix+"SHA256SUMS")==manifest,"inner SHA256")
        impl=json.loads(z.read(prefix+"implementation.json"))
        paths={"runner_sha256":Path(run.__file__),"policy_sha256":Path(f.__file__),
               "parent_runner_sha256":Path(d.__file__),"support_filter_sha256":Path(q.__file__),
               "attribution_sha256":Path(e.__file__),
               "runtime_lock_sha256":HERE.parent/"cneh_exp_01"/"bnsyn_integration_contract.json"}
        require(all(impl[k]==e.sha_file(p) for k,p in paths.items()),"original implementation mismatch")
        require(hashes["preregistration.md"]==e.sha_file(Path(run.__file__).parent/"PREREGISTRATION.md"),"original protocol drift")
        with z.open(prefix+"episodes.json.gz") as compressed,gzip.GzipFile(fileobj=compressed) as raw:
            episodes=json.load(raw)
        return episodes,json.loads(z.read(prefix+"worlds.json")),json.loads(z.read(prefix+"verdict.json"))


def summarize(segs: list[dict]) -> dict:
    reachable=[s for s in segs if s["reachable"]]
    disconnected=[s for s in segs if not s["reachable"]]
    counts={k:sum(s["contingency"][k] for s in reachable) for k in ("CORRECT_IN","CORRECT_OUT","OTHER_IN","OTHER_OUT")}
    packets=[p for s in reachable for p in s["packets"]]
    stim=[p for s in reachable for p in s["packets"] if p["connected"]]
    def sum_dict(key,fields):
        return {k:sum(s[key][k] for s in reachable) for k in fields}
    status={k:sum(s["status"]==k for s in reachable) for k in CLASSES}
    require(sum(status.values())==len(reachable),"incomplete failure partition")
    return {"reachable":len(reachable),"disconnected":len(disconnected),"status":status,
            "I10":sum(s["I10"] for s in reachable),"I20":sum(s["I20"] for s in reachable),
            "B10":sum(s["B10"] for s in reachable),"J10":sum(s["J10"] for s in reachable),
            "J10_without_I20":sum(s["J10"] and not s["I20"] for s in reachable),
            "I20_without_J10":sum(s["I20"] and not s["J10"] for s in reachable),
            "observed_ceiling_I20":sum(s["observed_ceiling_I20"] for s in reachable),
            "full_ceiling_I20":sum(s["full_ceiling_I20"] for s in reachable),
            "disconnect_I20":sum(s["I20"] for s in disconnected),
            "disconnect_full_ceiling_I20":sum(s["full_ceiling_I20"] for s in disconnected),
            "contingency":counts,"conditional_mae_nS":{
                "CORRECT":None if counts["CORRECT_IN"]+counts["CORRECT_OUT"]==0 else math.fsum(s["abs_error_sum"]["CORRECT"] for s in reachable)/(counts["CORRECT_IN"]+counts["CORRECT_OUT"]),
                "OTHER":None if counts["OTHER_IN"]+counts["OTHER_OUT"]==0 else math.fsum(s["abs_error_sum"]["OTHER"] for s in reachable)/(counts["OTHER_IN"]+counts["OTHER_OUT"])},
            "ticks":sum(s["ticks"] for s in reachable),"below":sum(s["below"] for s in reachable),"above":sum(s["above"] for s in reachable),
            "in_band":sum(s["in_band"] for s in reachable),"arrival_multiplicity":sum_dict("arrival_multiplicity",[str(i) for i in range(9)]),
            "longest_arrival_free_run":max(s["longest_arrival_free_run"] for s in reachable),
            "source_spike_ticks":sum(s["source_spike_ticks"] for s in reachable),
            "source_spike_events":sum(s["source_spike_events"] for s in reachable),
            "actions":sum_dict("actions",("REST","CONNECTED","UNCONNECTED")),
            "correct_below_actions":sum_dict("correct_below_actions",("REST","CONNECTED","UNCONNECTED")),
            "post_stim_spikes":sum_dict("post_stim_spikes",("CONNECTED","UNCONNECTED")),
            "post_stim_spike_ticks":sum_dict("post_stim_spike_ticks",("CONNECTED","UNCONNECTED")),
            "full_packets":len(packets),"silent_full_packets":sum(p["spike_events"]==0 for p in packets),
            "connected_full_packets":len(stim),"silent_connected_full_packets":sum(p["spike_events"]==0 for p in stim),
            "packet_purpose":{purpose:{"count":sum(p["purpose"]==purpose for p in packets),
                               "silent":sum(p["purpose"]==purpose and not p["spike_events"] for p in packets)} for purpose in ("TRACK_PACKET","VERIFY_PACKET")}}


def audit(episodes: list,worlds: list,verdict: dict) -> dict:
    require(verdict["all_instrument_checks_passed"] is True and verdict["exact_emulator_equal_worlds"]==16,"parent failed")
    require(len(worlds)==len(run.SEEDS) and {w["seed"] for w in worlds}==set(run.SEEDS),"world roster")
    require(len(episodes)==len(run.SEEDS)*len(f.ARMS) and {(x["seed"],x["arm"]) for x in episodes}==set(itertools.product(run.SEEDS,f.ARMS)),"episode roster")
    result=[]
    by={(x["seed"],x["arm"]):x for x in episodes}
    wm={w["seed"]:w for w in worlds}
    for seed in run.SEEDS:
        w=run.world(seed)
        require(wm[seed]["valid"] is True and wm[seed]["exact_emulator_equal"] is True and wm[seed]["schedule"]==[list(s) for s in w["schedule"]],"world integrity")
        require(run.pair(w,[by[seed,a] for a in f.ARMS])["valid"],"paired evidence mismatch")
    for ep in episodes:
        seed,arm,rows=ep["seed"],ep["arm"],ep["trace"]
        require(ep["valid"] is True and len(rows)==d.STEPS+1,"invalid episode")
        f.audit_tape(rows,arm)
        used=0
        for t,row in enumerate(rows[:-1]):
            group=row["group"]
            require((group is not None)==f.is_on(t) and row["source_inputs_pA"]==[500. if group==g else 0. for g in range(2)],"actuation budget mismatch")
            used+=group is not None
            require(used==f.ON*(t//f.PACKET)+min(t%f.PACKET+1,f.ON),"prefix mismatch")
        require(used==1600,"total budget")
        schedule=run.world(seed)["schedule"]
        segs=[segment(rows,tau,schedule[i+1][0] if i+1<len(schedule) else d.STEPS,m) for i,(tau,m) in enumerate(schedule)]
        for s,old in zip(segs,ep["segments"],strict=True):
            require(s["I20"]==old["identified"] and s["J10"]==old["recovered"] and s["longest_band"]==old["longest_band_run"],"original metric discrepancy")
        result.append({"seed":seed,"arm":arm,"segments":segs})
    summary={a:summarize([s for x in result if x["arm"]==a for s in x["segments"]]) for a in f.ARMS}
    for a,s in summary.items():
        require(s["reachable"]==24 and s["disconnected"]==12 and s["I20"]+s["disconnect_I20"]==verdict["arm_metrics"][a]["identified"] and s["J10"]==verdict["arm_metrics"][a]["recovered"],"aggregate mismatch")
    require(summary[f.ARMS[0]]==summary[f.ARMS[1]],"emulator summary mismatch")
    return {"experiment":"EXP04F_FAILURE_DECOMPOSITION","authority":"RETROSPECTIVE_DIAGNOSTIC_ONLY",
            "source_archive_sha256":ARCHIVE_SHA,"source_artifact":14862927917,
            "protocol_sha256":e.sha_file(HERE/"PROTOCOL.md"),"implementation_sha256":e.sha_file(Path(__file__)),
            "scientific_promotion_authorized":False,"rheobase_causality":"NOT_IDENTIFIED","summary":summary,"per_episode":result}


def main() -> None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--verify",action="store_true")
    args=p.parse_args()
    report=audit(*load(args.archive))
    data=d.pinned.canonical(report)
    if args.verify:
        require(args.out.is_file() and not args.out.is_symlink() and args.out.read_bytes()==data,"replay mismatch")
    else:
        with args.out.open("xb") as out:
            out.write(data)
    print(json.dumps(report["summary"],sort_keys=True))


if __name__=="__main__":
    main()
