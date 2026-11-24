"""Independent admission of committed interval evidence; never executes RK."""
from __future__ import annotations

from bisect import bisect_right
import math
import re

import numpy as np

from experiments.cneh_exp_05j import verify as sturm
from experiments.cneh_exp_05x import worlds as w

MODES=((1,0),(0,1),(1,1),(0,0))
TAU=(2.5,100.,6.)
ACTIONS=("WAIT","G0","G1")
FIELDS={"start","bound","Vw_start","g_start","rhs_count","rhs_min","rhs_max","trials","rejected",
        "accepted","chunks","end","accepted_end","Vw_end","sample_end","g_end","reset",
        "trace_sha256","schedule_sha256"}


def need(c,msg):
    if not c:
        raise ValueError(msg)


def is_hash(x):
    return type(x) is str and re.fullmatch("[0-9a-f]{64}",x) is not None


def vector(raw,n):
    need(type(raw) is list and len(raw)==n,"physical vector roster")
    return [w.f(x) for x in raw]


def state(raw):
    need(type(raw) is list and len(raw)==5,"physical state roster")
    a=np.array([vector(row,32) for row in raw],dtype=np.float64)
    need(np.min(a[0])>=-100. and np.max(a[0])<30. and np.min(a[2:])>=0.,"physical state envelope")
    return a


def analytic(initial,impulses,t,tau,start,inclusive):
    return math.fsum([initial*math.exp(-(t-start)/tau)]+[
        amount*math.exp(-(t-at)/tau) for at,amount in impulses if at<t or (inclusive and at==t)])


def audit(previous,frame,action,receipt):
    # Decode the input independently; do not call the candidate or its state
    # transition. Check expected frame and action before reading producer data.
    k=previous["tick"]
    start,end=k/10.,(k+1)/10.
    need(type(k) is int and 0<=k<512 and frame.tick==k and action in ACTIONS,"independent tick/action")
    need(type(frame.mode) is int and 0<=frame.mode<4,"independent mode")
    switch=[(w.f(t),mode) for t,mode in frame.switches]
    st=[t for t,_ in switch]
    modes=[frame.mode]+[m for _,m in switch]
    need(st==sorted(set(st)) and all(start<t<end for t in st)
         and all(type(m) is int and 0<=m<4 for m in modes)
         and all(a!=b for a,b in zip(modes[:-1],modes[1:],strict=True)),"independent switch chronology")
    ext=[[w.f(x) for x in seq] for seq in frame.external]
    need(len(ext)==32 and all(seq==sorted(set(seq)) and all(start<=t<end for t in seq) for seq in ext),"independent external interval")
    need(type(receipt) is dict and set(receipt)=={"payload","snapshot","observation"},"receipt roster")
    p=receipt["payload"];after=receipt["snapshot"]
    need(set(p)=={"frame","action","previous_sha256","events","arrivals","ledgers","steps_per_neuron","next_without_chain"},"payload roster")
    expected_frame={"tick":k,"mode":frame.mode,"switches":[list(x) for x in frame.switches],
                    "external":[list(x) for x in frame.external]}
    need(p["frame"]==expected_frame and p["action"]==action and p["previous_sha256"]==w.digest(previous),"frame/action/prestate binding")
    need(set(after)=={"tick","state","last_action","receiver_spikes","population_spikes","chain"}
         and after["chain"]==w.digest(p) and p["next_without_chain"]=={a:b for a,b in after.items() if a!="chain"}
         and after["tick"]==k+1 and after["last_action"]==action,"committed chain binding")
    a,b=state(previous["state"]),state(after["state"])
    ev=p["events"];led=p["ledgers"]
    need(type(ev) is list and type(led) is list and len(ev)==len(led)==len(p["steps_per_neuron"])==32,"cell roster")
    times=[]
    for seq in ev:
        need(type(seq) is list,"event sequence")
        ts=[w.f(e["t_ms"]) for e in seq]
        need(ts==sorted(set(ts)) and all(start<t<end for t in ts),"event time roster")
        times.append(ts)
    # Iterate over mode intervals instead of using the producer's route helper.
    expected=[]
    mode_bounds=[start]+st+[end]
    for lo,hi,m in zip(mode_bounds[:-1],mode_bounds[1:],modes,strict=True):
        for i in range(24,32):
            if MODES[m][(i-24)//4]:
                for t in times[i]:
                    if lo<=t<hi:
                        expected.append({"t_ms":t.hex(),"source":i,"mode":m,"increment_nS":.5})
    expected.sort(key=lambda x:(w.f(x["t_ms"]),x["source"]))
    need(p["arrivals"]==expected,"source route completeness")
    gaba=[(w.f(x["t_ms"]),.5) for x in expected]
    max_g=0.
    counts={"accepted_steps":0,"rejected_trials":0,"rhs_evaluations":0,"synaptic_stops":0,
            "root_certificates":0,"forcing_stops":0,"source_arrivals":len(expected)}
    for i in range(32):
        incoming=gaba if i<16 else []
        syn=set(ext[i])|{t for t,q in incoming}
        changes=sorted({start,end,*st,*syn})
        impulse=[[(t,.7*.3) for t in ext[i]],[(t,.3*.3) for t in ext[i]],incoming]
        counts["synaptic_stops"]+=len(syn)
        counts["forcing_stops"]+=len(changes)-1
        prev_t=start
        prev_vw=[w.hx(x) for x in a[:2,i]]
        segment=1;event_idx=0;step_count=0
        for row in led[i]:
            need(type(row) is dict and set(row)==FIELDS,"forcing ledger fields")
            lo,bound,stop,actual,rmin,rmax=map(w.f,[row[x] for x in ("start","bound","end","accepted_end","rhs_min","rhs_max")])
            need(segment<len(changes) and lo==prev_t<stop<=actual<=bound==changes[segment],"missing/duplicate/crossed forcing boundary")
            need(lo<=rmin<=rmax<=bound and row["Vw_start"]==prev_vw,"RHS bounds or V/w continuity")
            vector(row["Vw_end"],2);vector(row["sample_end"],2)
            gs,ge=vector(row["g_start"],3),vector(row["g_end"],3)
            for n,tau in enumerate(TAU):
                max_g=max(max_g,abs(gs[n]-analytic(a[n+2,i],impulse[n],lo,tau,start,True)),
                          abs(ge[n]-analytic(a[n+2,i],impulse[n],stop,tau,start,False)))
            for key in ("trials","accepted","rejected","rhs_count"):
                need(type(row[key]) is int and row[key]>=0,"step counts")
            need(row["accepted"]>0 and row["trials"]==row["accepted"]+row["rejected"]
                 and row["rhs_count"]==7*row["trials"] and is_hash(row["trace_sha256"])
                 and is_hash(row["schedule_sha256"]) and type(row["chunks"]) is list
                 and len(row["chunks"])==(row["accepted"]+63)//64 and all(is_hash(x) for x in row["chunks"]),"stage evidence roster")
            counts["accepted_steps"]+=row["accepted"];step_count+=row["accepted"]
            counts["rejected_trials"]+=row["rejected"];counts["rhs_evaluations"]+=row["rhs_count"]
            need(type(row["reset"]) is bool,"reset encoding")
            if row["reset"]:
                need(event_idx<len(ev[i]),"unbound reset")
                e=ev[i][event_idx]
                v=sturm.verify_event(e,"TIGHT")
                need(v["time"]==stop and row["Vw_end"]==e["post"]==row["sample_end"]
                     and e["forcing_interval_ms"]==[changes[segment-1].hex(),bound.hex()]
                     and lo<=w.f(e["t_old_ms"])<stop<bound and all(abs(stop-t)>1e-9 for t in changes),"root/reset boundary binding")
                for n,tau in enumerate(TAU):
                    max_g=max(max_g,abs(w.f(e["conductance"][n])-analytic(a[n+2,i],impulse[n],stop,tau,start,False)))
                event_idx+=1;counts["root_certificates"]+=1
            else:
                need(stop==actual==bound,"not stopped at exact forcing boundary")
                segment+=1
            prev_t=stop;prev_vw=row["Vw_end"]
        need(prev_t==end and segment==len(changes) and event_idx==len(ev[i])
             and type(p["steps_per_neuron"][i]) is int and p["steps_per_neuron"][i]==step_count,"incomplete cell interval")
        need(prev_vw==[w.hx(x) for x in b[:2,i]],"committed V/w endpoint mismatch")
        need(led[i][-1]["g_end"]==[w.hx(x) for x in b[2:,i]],"committed conductance endpoint mismatch")
        for n,tau in enumerate(TAU):
            max_g=max(max_g,abs(b[n+2,i]-analytic(a[n+2,i],impulse[n],end,tau,start,False)))
    need(max_g<=1e-10,"analytic conductance residual")
    observation={"tick":k+1,"receiver_spikes":sum(len(t) for t in times[:16]),
                 "population_spikes":sum(len(t) for t in times),"last_action":action}
    need(receipt["observation"]==observation and all(after[a]==b for a,b in observation.items()),"public observation binding")
    return {**counts,"max_conductance_residual_nS":max_g,"status":"PASS"}
