"""Independent event-boundary audit and cross-domain comparison."""
from __future__ import annotations

from bisect import bisect_right
import math
import re

import numpy as np

from experiments.cneh_exp_05j import verify as root
from experiments.cneh_exp_05x import worlds as w

FIELDS=("V","w","g_ampa","g_nmda","g_gabaa")
TIMES=np.arange(513,dtype=np.float64)/10.
LIMITS=(1e-3,1e-5,1e-6,1e-6,1e-6)


def is_hash(x):
    return type(x) is str and re.fullmatch("[0-9a-f]{64}",x) is not None


def exact_list(xs,n):
    w.need(type(xs) is list and len(xs)==n,"encoded array roster")
    return [w.f(x) for x in xs]


def arrivals(world,events):
    mode_order=world["mode_order"]
    switches=list(map(w.f,world["switches"]))
    out=[]
    for i in range(24,32):
        for e in events[i]:
            t=w.f(e["t_ms"])
            if t<w.END:
                mode=bisect_right(switches,t)
                if w.MODES[mode_order[mode]][(i-24)//4]:
                    # J records schedule index, not mode identity.
                    out.append({"t_ms":e["t_ms"],"source":i,"mode":mode,"increment_nS":.5})
    return sorted(out,key=lambda x:(w.f(x["t_ms"]),x["source"]))


def scalar_g(initial,impulses,t,tau,inclusive):
    return math.fsum([initial*math.exp(-t/tau)]+
                    [q*math.exp(-(t-at)/tau) for at,q in impulses if at<t or inclusive and at==t])


def sampled_g(initial,impulses,tau):
    out=initial*np.exp(-TIMES/tau)
    for at,q in impulses:
        mask=TIMES>at
        out[mask]+=q*np.exp(-(TIMES[mask]-at)/tau)
    return out


def audit(world,result):
    w.need(set(result)=={"physical","physical_sha256","ledgers","trace_sha256"},"result roster")
    physical=result["physical"]
    w.need(result["physical_sha256"]==w.digest(physical) and result["trace_sha256"]==w.digest(result["ledgers"]),
           "raw hash binding")
    w.need(set(physical)=={"samples","events","arrivals","accepted_steps"},"physical roster")
    samples=root.sample_array(physical["samples"])
    initial=np.array([exact_list(row,32) for row in world["initial"]])
    w.need(np.array_equal(samples[0],initial),"initial mismatch")
    events=physical["events"]
    ledgers=result["ledgers"]
    w.need(len(events)==len(ledgers)==len(physical["accepted_steps"])==32,"neuron roster")
    times=root.event_times(physical)
    expected_arrivals=arrivals(world,events)
    w.need(physical["arrivals"]==expected_arrivals,"routed event roster")
    gaba=[(w.f(a["t_ms"]),.5) for a in expected_arrivals]
    switched=list(map(w.f,world["switches"]))
    current=list(map(w.f,world["current_switches"])) if world["arm"]=="ALTERNATE" else []
    count_syn=count_external=count_routed=count_forcing=steps=trials=rejects=rhs=certs=0
    max_residual=0.
    fields={"start","bound","Vw_start","g_start","rhs_count","rhs_min","rhs_max","trials","rejected",
            "accepted","chunks","end","accepted_end","Vw_end","sample_end","g_end","reset","trace_sha256","schedule_sha256"}
    for i in range(32):
        ext=list(map(w.f,world["external"][i]))
        inc=gaba if i<16 else []
        impulses=([(t,.7*.3) for t in ext],[(t,.3*.3) for t in ext],inc)
        syn=set(ext)|{t for t,q in inc}
        boundaries=sorted({0.,w.END,*switched,*current,*syn})
        count_external+=len(ext)
        count_routed+=len(inc)
        count_syn+=len(syn)
        count_forcing+=len(boundaries)-2
        for k,tau in enumerate((2.5,100.,6.)):
            residual=float(np.max(np.abs(samples[:,k+2,i]-sampled_g(initial[k+2,i],impulses[k],tau))))
            max_residual=max(max_residual,residual)
        previous_t=0.
        previous_vw=[w.hx(v) for v in initial[:2,i]]
        target=1
        index=0
        total_steps=0
        for row in ledgers[i]:
            w.need(type(row) is dict and set(row)==fields,"step ledger roster")
            start,bound,end,accepted_end,lo,hi=map(w.f,[row[k] for k in ("start","bound","end","accepted_end","rhs_min","rhs_max")])
            w.need(target<len(boundaries) and start==previous_t<end<=accepted_end<=bound==boundaries[target],
                   "missing/duplicate/crossed forcing boundary")
            w.need(start<=lo<=hi<=bound,"RHS stage crosses forcing boundary")
            w.need(row["Vw_start"]==previous_vw,"V/w discontinuity outside certified reset")
            exact_list(row["Vw_end"],2)
            exact_list(row["sample_end"],2)
            ix=int(round(end*10.))
            if 0<=ix<len(TIMES) and float(TIMES[ix])==end:
                w.need(row["sample_end"]==[w.hx(v) for v in samples[ix,:2,i]],"dense sample boundary binding")
            gstart,g_end=exact_list(row["g_start"],3),exact_list(row["g_end"],3)
            for k,tau in enumerate((2.5,100.,6.)):
                max_residual=max(max_residual,
                   abs(gstart[k]-scalar_g(initial[k+2,i],impulses[k],start,tau,True)),
                   abs(g_end[k]-scalar_g(initial[k+2,i],impulses[k],end,tau,False)))
            for k in ("accepted","trials","rejected","rhs_count"):
                w.need(type(row[k]) is int and row[k]>=0,"trial count type")
            w.need(row["accepted"]>0 and row["rhs_count"]>0 and row["trials"]==row["accepted"]+row["rejected"]
                   and is_hash(row["trace_sha256"]) and is_hash(row["schedule_sha256"]) and len(row["chunks"])==(row["accepted"]+63)//64
                   and all(is_hash(x) for x in row["chunks"]),"step digest/count roster")
            steps+=row["accepted"];total_steps+=row["accepted"];trials+=row["trials"]
            rejects+=row["rejected"];rhs+=row["rhs_count"]
            w.need(type(row["reset"]) is bool,"reset encoding")
            if row["reset"]:
                w.need(index<len(events[i]),"unbound reset")
                event=events[i][index]
                v=root.verify_event(event,"TIGHT")
                w.need(v["time"]==end and row["Vw_end"]==event["post"]
                       and event["forcing_interval_ms"]==[w.hx(boundaries[target-1]),w.hx(bound)]
                       and start<=w.f(event["t_old_ms"])<end<bound,"root/forcing ledger binding")
                index+=1;certs+=1
            else:
                w.need(end==accepted_end==bound,"solver did not stop at forcing boundary")
                target+=1
            previous_t=end;previous_vw=row["Vw_end"]
        w.need(previous_t==w.END and target==len(boundaries) and index==len(events[i])
               and total_steps==physical["accepted_steps"][i],"incomplete event/forcing coverage")
        w.need(ledgers[i][-1]["sample_end"]==[w.hx(v) for v in samples[-1,:2,i]],"final physical sample binding")
    w.need(max_residual<=1e-10,"analytic synaptic jump/decay mismatch")
    return {"status":"PASS","synaptic_stops":count_syn,"external_impulses":count_external,
            "receiver_arrivals":count_routed,"forcing_stops":count_forcing,
            "accepted_steps":steps,"trials":trials,"rejected_trials":rejects,"rhs_evaluations":rhs,
            "root_certificates":certs,"max_conductance_residual_nS":max_residual}


def first_difference(a,b):
    for i,(aa,bb) in enumerate(zip(a["ledgers"],b["ledgers"],strict=True)):
        for k,(x,y) in enumerate(zip(aa,bb)):
            if x!=y:
                chunk=next((n for n,(u,v) in enumerate(zip(x["chunks"],y["chunks"])) if u!=v),None)
                if chunk is None and len(x["chunks"])!=len(y["chunks"]):
                    chunk=min(len(x["chunks"]),len(y["chunks"]))
                return {"neuron":i,"segment":k,"chunk64":chunk,
                        "fields":sorted(key for key in set(x)|set(y) if x.get(key)!=y.get(key)),
                        "x86_start":x["start"],"arm64_start":y["start"],
                        "x86_end":x["end"],"arm64_end":y["end"],
                        "x86_trace_sha256":x["trace_sha256"],"arm64_trace_sha256":y["trace_sha256"]}
        if len(aa)!=len(bb):
            return {"neuron":i,"segment":min(len(aa),len(bb)),"fields":["segment_count"]}
    if a["physical"]!=b["physical"]:
        p,q=a["physical"],b["physical"]
        return {"fields":sorted(k for k in p if p[k]!=q[k])}
    return {"fields":["canonical_binary64_encoding"]}


def compare(a,b):
    x,y=a["physical"],b["physical"]
    sa,sb=root.sample_array(x["samples"]),root.sample_array(y["samples"])
    times_a,times_b=root.event_times(x),root.event_times(y)
    counts=[len(t) for t in times_a]==[len(t) for t in times_b]
    event_error=max((abs(t-u) for ta,tb in zip(times_a,times_b,strict=True)
                     for t,u in zip(ta,tb,strict=True)),default=0.) if counts else None
    errors={k:float(np.max(np.abs(sa[:,i,:]-sb[:,i,:]))) for i,k in enumerate(FIELDS)}
    routing=[(r["source"],r["mode"]) for r in x["arrivals"]]==[(r["source"],r["mode"]) for r in y["arrivals"]]
    band_a,band_b=root.band_count(sa),root.band_count(sb)
    close=(counts and event_error<=1e-6 and routing and band_a==band_b
           and all(errors[k]<=limit for k,limit in zip(FIELDS,LIMITS,strict=True)))
    exact=(w.canonical(a)==w.canonical(b))
    schedule=lambda q:[[tuple(s[k] for k in ("start","bound","end","schedule_sha256")) for s in rows] for rows in q["ledgers"]]
    return {"exact":exact,"step_schedule_exact":schedule(a)==schedule(b),
            "event_tape_exact":w.canonical(x["events"])==w.canonical(y["events"]),
            "raw_samples_exact":w.canonical(x["samples"])==w.canonical(y["samples"]),
            "numerical_close":close,"spike_counts_equal":counts,"routing_order_equal":routing,
            "max_event_time_error_ms":event_error,"max_full_errors":errors,
            "physical_band_count_x86":band_a,"physical_band_count_arm64":band_b,
            "first_difference":None if exact else first_difference(a,b)}
