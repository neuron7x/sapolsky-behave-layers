"""Independent event certificate and full physical sample verifier."""
from __future__ import annotations

from bisect import bisect_right
from fractions import Fraction as F
import math

import numpy as np

END=51.2
TIMES=np.arange(513,dtype=np.float64)/10.
MODES=((1,0),(0,1),(1,1),(0,0))
ROUTE_TIMES=(12.8,25.6,38.4)
CURRENT_TIMES=tuple(k/10. for k in range(64,512,64))
PROFILES={"LOOSE":.05,"TIGHT":.025}
STATE_FIELDS=("V","w","g_ampa","g_nmda","g_gabaa")


def need(c,msg):
    if not c:
        raise ValueError(msg)


def decode(s):
    need(type(s) is str,"float encoding")
    v=float.fromhex(s)
    need(math.isfinite(v) and v.hex()==s,"noncanonical float")
    return v


def rational(pair):
    need(type(pair) is list and len(pair)==2 and all(type(x) is int for x in pair)
         and pair[1]>0,"invalid rational")
    q=F(*pair)
    need([q.numerator,q.denominator]==pair,"noncanonical rational")
    return q


def trim(p):
    p=list(p)
    while p and p[-1]==0:
        p.pop()
    return tuple(p)


def evaluate(p,x):
    return sum((c*x**k for k,c in enumerate(p)),F(0))


def diff(p):
    return trim(tuple(k*p[k] for k in range(1,len(p))))


def remainder(a,b):
    need(bool(b),"polynomial division by zero")
    a=list(a)
    while len(a)>=len(b):
        shift=len(a)-len(b)
        coeff=a[-1]/b[-1]
        for i,c in enumerate(b):
            a[i+shift]-=coeff*c
        a=list(trim(a))
    return tuple(a)


def sturm(p):
    p=trim(p)
    need(len(p)>=2,"constant threshold polynomial")
    seq=[p,diff(p)]
    while seq[-1]:
        rem=remainder(seq[-2],seq[-1])
        if not rem:
            break
        seq.append(tuple(-x for x in rem))
    return tuple(seq)


def side_sign(p,x,side):
    order=0
    while p:
        v=evaluate(p,x)
        if v:
            return (1 if v>0 else -1)*(side**order)
        p=diff(p)
        order+=1
    raise ValueError("zero Sturm member")


def variations(seq,x,side):
    signs=[side_sign(p,x,side) for p in seq]
    return sum(a!=b for a,b in zip(signs[:-1],signs[1:],strict=True))


def roots_open(seq,l,u):
    if l==u:
        return 0
    need(l<u,"invalid root counting interval")
    n=variations(seq,l,1)-variations(seq,u,-1)
    need(n>=0,"negative root count")
    return n


def verify_bracket(p,l,u):
    need(0<=l<=u<=1 and u-l<=F(1,2**70) and evaluate(p,F(0))<0,"root bracket domain")
    seq=sturm(p)
    need(roots_open(seq,F(0),l)==0,"earlier root in dense step")
    if l==u:
        need(evaluate(p,l)==0,"singleton is not a root")
    else:
        need(evaluate(p,l)<0<evaluate(p,u) and roots_open(seq,l,u)==1,"nonisolated/non-upward root")
    m=(l+u)/2
    need(evaluate(diff(p),m)>0,"nontransverse root")
    return m


def verify_event(event,profile):
    fields={"t_ms","t_old_ms","h_ms","y_old","Q","x_lo","x_hi","threshold_derivative_mV_ms",
            "pre","post","conductance","forcing_interval_ms"}
    need(type(event) is dict and set(event)==fields,"event field roster")
    t,t0,h=(decode(event[k]) for k in ("t_ms","t_old_ms","h_ms"))
    need(0<=t0<t<=END and 0<h<=PROFILES[profile]+1e-14 and t<=t0+h+1e-14,"event step range")
    need(len(event["y_old"])==2 and len(event["Q"])==2 and all(len(q)==4 for q in event["Q"]),"dense polynomial roster")
    polynomials=tuple((F(decode(v)),)+tuple(F(h)*F(decode(q)) for q in row)
                      for v,row in zip(event["y_old"],event["Q"],strict=True))
    v,w=polynomials
    p=(v[0]-30,)+v[1:]
    l,u=(rational(event[k]) for k in ("x_lo","x_hi"))
    m=verify_bracket(p,l,u)
    expected_time=float(F(t0)+F(h)*m)
    slope=float(evaluate(diff(p),m)/F(h))
    pre=(float(evaluate(v,m)),float(evaluate(w,m)))
    need(t.hex()==expected_time.hex() and event["threshold_derivative_mV_ms"]==slope.hex(),"event time/derivative binding")
    need(event["pre"]==[x.hex() for x in pre] and abs(pre[0]-30.)<=1e-6,"pre-reset root state")
    need(event["post"]==[(-58.).hex(),(pre[1]+80.).hex()],"AdEx reset jump")
    need(len(event["conductance"])==3 and all(decode(x)>=0 for x in event["conductance"]),"event conductance roster")
    need(len(event["forcing_interval_ms"])==2,"forcing interval roster")
    start,end=map(decode,event["forcing_interval_ms"])
    need(start<t<end and min(t-start,end-t)>1e-9 and t0>=start,"ambiguous event boundary")
    return {"time":t,"root_width_ms":float(F(h)*(u-l)),
            "residual_mV":abs(pre[0]-30.),"w_jump_pA":decode(event["post"][1])-pre[1]}


def event_times(result):
    need(type(result["events"]) is list and len(result["events"])==32,"neuron event roster")
    out=[]
    for seq in result["events"]:
        need(type(seq) is list,"invalid event sequence")
        times=[decode(x["t_ms"]) for x in seq]
        need(all(0<t<=END for t in times) and times==sorted(set(times)),"event time order")
        out.append(times)
    return out


def independent_arrivals(times):
    result=[]
    for mode,(lo,hi) in enumerate(zip((0.,)+ROUTE_TIMES,ROUTE_TIMES+(END,),strict=True)):
        for i in range(24,32):
            if MODES[mode][(i-24)//4]:
                for t in times[i]:
                    if lo<=t<hi:
                        result.append({"source":i,"mode":mode,"t_ms":t.hex(),"increment_nS":.5})
    return sorted(result,key=lambda x:(decode(x["t_ms"]),x["source"]))


def analytic_value(initial,impulses,tau,t):
    # Before coincident impulse at a sample boundary.
    return math.fsum([float(initial)*math.exp(-t/tau)]+
                    [weight*math.exp(-(t-at)/tau) for at,weight in impulses if at<t])


def band_count(a):
    g=np.mean(a[:,4,:16],axis=1)
    return int(np.count_nonzero((.4<=g)&(g<=.6)))


def sample_array(raw):
    a=np.asarray(raw,dtype=float)
    need(a.shape==(513,5,32) and np.isfinite(a).all(),"raw physical sample roster")
    need(np.min(a[:,0])>=-100. and np.max(a[:,0])<30. and np.min(a[:,2:])>=0.,"physical sample envelope")
    return a


def verify_result(result,initial,tape,arm):
    need(set(result)=={"profile","samples","events","arrivals","accepted_steps","steps_per_neuron","distinct_step_sizes"},
         "candidate result roster")
    profile=result["profile"]
    need(profile in PROFILES,"profile")
    need(type(result["accepted_steps"]) is int and len(result["steps_per_neuron"])==32 and
         all(type(n) is int and n>0 for n in result["steps_per_neuron"]) and
         sum(result["steps_per_neuron"])==result["accepted_steps"] and
         type(result["distinct_step_sizes"]) is int and 1<result["distinct_step_sizes"]<=result["accepted_steps"],"adaptive ledger")
    a=sample_array(result["samples"])
    need(np.array_equal(a[0],initial),"initial physical state mismatch")
    times=event_times(result)
    arrivals=independent_arrivals(times)
    need(result["arrivals"]==arrivals,"source routing ledger mismatch")
    gaba=[(decode(x["t_ms"]),.5) for x in arrivals]
    max_residual=0.
    max_event_g=0.
    roots=[]
    for i in range(32):
        ext=[float(TIMES[t]) for t in range(512) if tape[t,i]]
        impulse_lists=([(t,.21) for t in ext],[(t,.09) for t in ext],gaba if i<16 else [])
        changes=sorted({0.,END,*ROUTE_TIMES,*ext,*(t for t,_ in impulse_lists[2])}|
                       (set(CURRENT_TIMES) if arm=="ALTERNATE" else set()))
        for t_index,t in enumerate(TIMES):
            for k,tau in enumerate((2.5,100.,6.)):
                expected=analytic_value(initial[k+2,i],impulse_lists[k],tau,float(t))
                max_residual=max(max_residual,abs(a[t_index,k+2,i]-expected))
        for event in result["events"][i]:
            root=verify_event(event,profile)
            t=root["time"]
            k=bisect_right(changes,t)
            need(0<k<len(changes) and event["forcing_interval_ms"]==[changes[k-1].hex(),changes[k].hex()],
                 "event forcing interval differs from input timeline")
            for j,tau in enumerate((2.5,100.,6.)):
                expected=analytic_value(initial[j+2,i],impulse_lists[j],tau,t)
                max_event_g=max(max_event_g,abs(decode(event["conductance"][j])-expected))
            roots.append(root)
    need(max(max_residual,max_event_g)<=1e-10,"analytic conductance recurrence mismatch")
    return {"root_certificates":len(roots),"routed_arrivals":len(arrivals),
            "max_root_width_ms":max((r["root_width_ms"] for r in roots),default=0.),
            "max_root_residual_mV":max((r["residual_mV"] for r in roots),default=0.),
            "max_sample_conductance_residual_nS":max_residual,"max_event_conductance_residual_nS":max_event_g,
            "accepted_steps":result["accepted_steps"],"distinct_step_sizes":result["distinct_step_sizes"]}


def comparison(left,lt,right,rt):
    a,b=sample_array(left),sample_array(right)
    for times in (lt,rt):
        need(len(times)==32 and all(seq==sorted(set(seq)) and all(math.isfinite(t) and 0<t<=END for t in seq) for seq in times),
             "reference event roster")
    counts=[len(x) for x in lt]==[len(x) for x in rt]
    max_time=max((abs(x-y) for aa,bb in zip(lt,rt,strict=True)
                  for x,y in zip(aa,bb,strict=True)),default=0.) if counts else None
    errs={key:float(np.max(np.abs(a[:,i,:]-b[:,i,:]))) for i,key in enumerate(STATE_FIELDS)}
    n1,n2=band_count(a),band_count(b)
    gates={"SPIKE_COUNT":counts,"SPIKE_TIME":max_time is not None and max_time<=1e-6,
           "V":errs["V"]<=1e-3,"W":errs["w"]<=1e-5,
           "AMPA":errs["g_ampa"]<=1e-6,"NMDA":errs["g_nmda"]<=1e-6,"GABA":errs["g_gabaa"]<=1e-6,
           "PHYSICAL_BAND_COUNT":n1==n2}
    return {"status":"PASS_FINITE" if all(gates.values()) else "FAIL","gates":gates,
            "spikes":sum(len(x) for x in lt),"reference_spikes":sum(len(x) for x in rt),
            "max_event_time_error_ms":max_time,"max_full_errors":errs,
            "physical_band_count":n1,"reference_band_count":n2}


def verify_pair(candidates,reference,initial,tape,arm):
    need([x["profile"] for x in candidates]==["LOOSE","TIGHT"],"candidate profile roster")
    checked=[verify_result(x,initial,tape,arm) for x in candidates]
    comparisons=[]
    for c in candidates:
        for name in ("loose","tight"):
            r=reference[name]
            comparisons.append({"left":c["profile"],"right":"DOP853_"+name.upper(),
                                **comparison(c["samples"],event_times(c),r["states"],r["events"])})
    a,b=candidates
    comparisons.append({"left":"LOOSE","right":"TIGHT",
                        **comparison(a["samples"],event_times(a),b["samples"],event_times(b))})
    return {"status":"PASS_FINITE" if all(x["status"]=="PASS_FINITE" for x in comparisons) else "FAIL",
            "independent_checks":checked,"comparisons":comparisons}
