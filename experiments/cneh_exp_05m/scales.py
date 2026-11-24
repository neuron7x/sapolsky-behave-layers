"""Independent multiscale reduction of sealed neural and evidence trajectories."""
from __future__ import annotations

import math
from collections import defaultdict

from experiments.cneh_exp_05 import policy as p

WIDTHS=(1,10,25,60,160,320,400,800,2000,3200)
HORIZONS=(10,25,60,160,320,400)
AGE_EDGES=(0,25,60,160,320,400)
ALL=15
TOL=1e-12
require=p.require


def mask(modes):
    result=0
    for mode in modes:
        require(type(mode) is int and 0<=mode<4,"invalid mode")
        result|=1<<mode
    return result


def longest(flags):
    run=maximum=0
    for flag in flags:
        run=run+1 if flag else 0
        maximum=max(run,maximum)
    return maximum


def first_streak(flags,length):
    run=0
    for j,flag in enumerate(flags,1):
        run=run+1 if flag else 0
        if run==length:
            return j
    return None


def age_bin(stamps,t):
    require(len(stamps)==3 and all(type(s) is int and 0<=s<=t and t-s<400 for s in stamps),"invalid singleton age")
    if 0 in stamps:
        return "PRIOR_INVOLVED"
    age=max(t-s for s in stamps)
    return next(f"{a}_{z}" for a,z in zip(AGE_EDGES[:-1],AGE_EDGES[1:]) if a<=age<z)


def phases(width):
    return (0,) if width==1 else (0,width//2)


def windows(rows,width,offset):
    require(width>0 and 0<=offset<width,"invalid window")
    return [rows[j:j+width] for j in range(offset,len(rows)-width+1,width)]


def window_metrics(rows):
    require(bool(rows),"empty window")
    n=len(rows)
    modes={r["mode"] for r in rows}
    observed=complete=ALL
    exclusions=0
    for r in rows:
        observed&=r["observed"]
        complete&=r["complete"]
        exclusions+=4-r["observed"].bit_count()
    require(complete&~observed==0,"full-bit support not subset")
    out={"stale_fraction":sum(r["stale"] for r in rows)/n,
         "ambiguous_fraction":sum(r["ambiguous"] for r in rows)/n,
         "correct_fraction":sum(r["correct"] for r in rows)/n,
         "source_spike_tick_fraction":sum(r["source_spike"] for r in rows)/n,
         "arrival_tick_fraction":sum(r["arrival"]>0 for r in rows)/n}
    if len(modes)>1:
        out["mixed_empty_intersection"]=int(observed==0)
        return "MIXED",out,None
    mode=next(iter(modes))
    require(observed&(1<<mode) and complete&(1<<mode),"pure window lost true model")
    distinct=4-observed.bit_count()
    require(exclusions>=distinct,"negative evidence redundancy")
    out.update(observed_remaining=observed.bit_count(),complete_remaining=complete.bit_count(),
               observed_singleton=int(observed.bit_count()==1),complete_singleton=int(complete.bit_count()==1),
               distinct_eliminated=distinct,erasure_candidate_gap=observed.bit_count()-complete.bit_count(),
               evidence_redundancy=exclusions-distinct)
    if mode==3:
        return "PURE_DISCONNECTED",out,None
    vals=[r["g"] for r in rows]
    flags=[r["band"] for r in rows]
    correct=[r["correct"] for r in rows]
    joint=[i and z for i,z in zip(correct,flags,strict=True)]
    raw=math.fsum(abs(v-.5) for v in vals)/n
    avg=math.fsum(vals)/n
    smoothed=abs(avg-.5)
    require(raw+TOL>=smoothed,"absolute-error cancellation invariant")
    out.update(raw_mae_nS=raw,smoothed_abs_error_nS=smoothed,cancellation_gap_nS=max(0.,raw-smoothed),
               raw_band_fraction=sum(flags)/n,mean_g_in_band=int(.4<=avg<=.6),
               joint_fraction=sum(joint)/n)
    if n>=10:
        out["B10"]=int(longest(flags)>=10)
        out["J10"]=int(longest(joint)>=10)
    if n>=20:
        out["I20"]=int(longest(correct)>=20)
        out["false_cooccurrence"]=int(out["I20"] and out["B10"] and not out["J10"])
    return "PURE_REACHABLE",out,(min(vals),max(vals),longest(flags))


def bucket():
    return {"windows":0,"samples":0,"metrics":{},"min_g":None,"max_g":None,"max_band_run":None}


def record(b,rows,metrics,extrema):
    b["windows"]+=1
    b["samples"]+=len(rows)
    for k,v in metrics.items():
        value=b["metrics"].setdefault(k,[0.,0])
        value[0]+=v
        value[1]+=1
    if extrema is not None:
        lo,hi,run=extrema
        b["min_g"]=lo if b["min_g"] is None else min(b["min_g"],lo)
        b["max_g"]=hi if b["max_g"] is None else max(b["max_g"],hi)
        b["max_band_run"]=run if b["max_band_run"] is None else max(b["max_band_run"],run)


def segment_windows(segments,whole):
    out={}
    coverage={}
    def add(scope,stratum,rows,w,off,whole_scope):
        key=f"{scope}/{stratum}/{w}/{off}"
        cv=coverage.setdefault(key,{"eligible_samples":0,"used_samples":0,"skipped_prefix":0,"discarded_tail":0})
        seq=windows(rows,w,off)
        prefix=min(off,len(rows))
        cv["eligible_samples"]+=len(rows)
        cv["skipped_prefix"]+=prefix
        cv["used_samples"]+=len(seq)*w
        cv["discarded_tail"]+=len(rows)-prefix-len(seq)*w
        require(cv["eligible_samples"]==cv["used_samples"]+cv["skipped_prefix"]+cv["discarded_tail"],"coverage accounting")
        for block in seq:
            kind,metrics,extrema=window_metrics(block)
            if not whole_scope:
                require(kind!="MIXED","regime segment crosses hidden switch")
            name=f"{scope}/{kind if whole_scope else stratum}/{w}/{off}"
            record(out.setdefault(name,bucket()),block,metrics,extrema)
    for w in WIDTHS:
        for off in phases(w):
            for name,rows in segments:
                add("SEGMENT",name,rows,w,off,False)
            if whole:
                add("EPISODE","ALL",whole,w,off,True)
    return out,coverage


def boundary(rows,tau,end):
    require(len(rows)==end-tau and bool(rows),"invalid switch boundary")
    mode=rows[0]["mode"]
    require(all(r["mode"]==mode for r in rows),"mixed switch segment")
    correct=[r["correct"] for r in rows]
    band=[r["band"] for r in rows]
    joint=[i and z for i,z in zip(correct,band,strict=True)]
    decision=((tau+319)//320)*320
    out={"switch_tick":tau,"end_tick":end,"mode":mode,"duration_ticks":len(rows),
         "I20_latency_ticks":first_streak(correct,20),
         "B10_latency_ticks":None if mode==3 else first_streak(band,10),
         "J10_latency_ticks":None if mode==3 else first_streak(joint,10),
         "next_block_delay_ticks":decision-tau if decision<end else None,"horizons":{}}
    for h in HORIZONS:
        part=rows[:h]
        _,metrics,_=window_metrics(part)
        out["horizons"][str(h)]={"actual_samples":len(part),"truncated":len(part)<h,**metrics}
    return out


def metric_pair(row,key,metric):
    b=row["windows"].get(key)
    if b is None or metric not in b["metrics"]:
        return None
    total,n=b["metrics"][metric]
    require(n>0,"zero denominator")
    return total,n


def mean(values):
    return math.fsum(values)/len(values) if values else None


def sign(x):
    return 1 if x>TOL else -1 if x< -TOL else 0


def summarize_arm(rows):
    keys=sorted({key for row in rows for key in row["windows"]})
    result={}
    for key in keys:
        fields=sorted({f for row in rows if key in row["windows"] for f in row["windows"][key]["metrics"]})
        metrics={}
        for f in fields:
            pairs=[pair for row in rows if (pair:=metric_pair(row,key,f)) is not None]
            metrics[f]={"equal_world_mean":mean([s/n for s,n in pairs]),
                        "pooled_window_mean":math.fsum(s for s,n in pairs)/sum(n for s,n in pairs),
                        "worlds":len(pairs),"windows":sum(n for s,n in pairs)}
        result[key]=metrics
    return result


def paired_contrasts(a,z):
    left={r["seed"]:r for r in a}
    right={r["seed"]:r for r in z}
    require(set(left)==set(right),"unpaired world roster")
    keys=sorted({key for row in a+z for key in row["windows"]})
    result={}
    for key in keys:
        fields=sorted({f for row in a+z if key in row["windows"] for f in row["windows"][key]["metrics"]})
        metrics={}
        for f in fields:
            pairs=[(x,y) for seed in sorted(left)
                   if (x:=metric_pair(left[seed],key,f)) is not None
                   and (y:=metric_pair(right[seed],key,f)) is not None]
            if not pairs:
                metrics[f]={"paired_worlds":0,"missing_worlds":len(left)}
                continue
            diff=[x[0]/x[1]-y[0]/y[1] for x,y in pairs]
            eq=mean(diff)
            pooled=math.fsum(x[0] for x,y in pairs)/sum(x[1] for x,y in pairs)-math.fsum(y[0] for x,y in pairs)/sum(y[1] for x,y in pairs)
            metrics[f]={"paired_worlds":len(pairs),"missing_worlds":len(left)-len(pairs),
                        "equal_world_difference":eq,"pooled_window_difference":pooled,
                        "sign_reversal":sign(eq)*sign(pooled)==-1,
                        "positive":sum(sign(v)>0 for v in diff),"negative":sum(sign(v)<0 for v in diff),
                        "ties":sum(sign(v)==0 for v in diff)}
        result[key]=metrics
    return result


def phase_reversals(contrasts):
    out=[]
    for key,metrics in contrasts.items():
        if not key.endswith("/0"):
            continue
        prefix=key.rsplit("/",1)[0]
        width=int(prefix.rsplit("/",1)[1])
        if width==1:
            continue
        second=contrasts.get(f"{prefix}/{width//2}",{})
        for f,x in metrics.items():
            y=second.get(f,{})
            if "equal_world_difference" not in x or "equal_world_difference" not in y:
                continue
            if sign(x["equal_world_difference"])*sign(y["equal_world_difference"])==-1:
                out.append({"scale":prefix,"metric":f,"phase_0":x["equal_world_difference"],
                            "phase_half":y["equal_world_difference"],"worlds":[x["paired_worlds"],y["paired_worlds"]]})
    return out
