"""Transactional interval-local AdEx runtime on the frozen R1 arithmetic."""
from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
import math

import numpy as np

from experiments.cneh_exp_05j import integrator as j
from experiments.cneh_exp_05j import verify as root
from experiments.cneh_exp_05x import trace as traces
from experiments.cneh_exp_05x import worlds as w
from experiments.cneh_exp_05y import portable as p

ACTIONS=("WAIT","G0","G1")
MODES=((1,0),(0,1),(1,1),(0,0))
TAU=(2.5,100.,6.)
N_TICKS=512
ZERO="0"*64


def need(c,msg):
    if not c:
        raise ValueError(msg)


def time_at(tick):
    return tick/10.


def digest(x):
    return w.digest(x)


def state_encode(a):
    return [[w.hx(x) for x in row] for row in a]


def state_decode(raw):
    need(type(raw) is list and len(raw)==5 and all(type(x) is list and len(x)==32 for x in raw),"state roster")
    a=np.array([[w.f(x) for x in row] for row in raw],dtype=np.float64)
    need(np.isfinite(a).all() and np.min(a[0])>=-100. and np.max(a[0])<30. and np.min(a[2:])>=0.,"state envelope")
    return a


def initial_snapshot(raw):
    state_decode(raw)
    return {"tick":0,"state":[list(x) for x in raw],"last_action":None,
            "receiver_spikes":0,"population_spikes":0,"chain":ZERO}


def public(snapshot):
    return {"tick":snapshot["tick"],"receiver_spikes":snapshot["receiver_spikes"],
            "population_spikes":snapshot["population_spikes"],"last_action":snapshot["last_action"]}


def validate_snapshot(s):
    need(type(s) is dict and set(s)=={"tick","state","last_action","receiver_spikes","population_spikes","chain"},"checkpoint roster")
    tick=s["tick"]
    need(type(tick) is int and 0<=tick<=N_TICKS,"checkpoint tick")
    state_decode(s["state"])
    need(type(s["chain"]) is str and len(s["chain"])==64 and all(c in "0123456789abcdef" for c in s["chain"]),"checkpoint chain")
    a=s["receiver_spikes"];b=s["population_spikes"]
    need(type(a) is int and type(b) is int and 0<=a<=b,"checkpoint observations")
    if tick==0:
        need(s["chain"]==ZERO and s["last_action"] is None and a==b==0,"initial checkpoint")
    else:
        need(s["last_action"] in ACTIONS and s["chain"]!=ZERO,"checkpoint action/chain")


@dataclass(frozen=True,slots=True)
class Frame:
    tick:int
    mode:int
    switches:tuple[tuple[str,int],...]
    external:tuple[tuple[str,...],...]


def frame_data(f):
    return {"tick":f.tick,"mode":f.mode,"switches":[list(x) for x in f.switches],
            "external":[list(x) for x in f.external]}


def validate_frame(f,tick):
    need(type(f) is Frame and type(f.tick) is int and f.tick==tick and 0<=tick<N_TICKS,"stale/future frame")
    need(type(f.mode) is int and 0<=f.mode<4 and type(f.switches) is tuple,"route schema")
    start,end=time_at(tick),time_at(tick+1)
    previous=start
    mode=f.mode
    for row in f.switches:
        need(type(row) is tuple and len(row)==2,"switch roster")
        at,new=row
        t=w.f(at)
        need(previous<t<end and type(new) is int and 0<=new<4 and new!=mode,"route chronology")
        previous,mode=t,new
    need(type(f.external) is tuple and len(f.external)==32,"external roster")
    for seq in f.external:
        need(type(seq) is tuple,"external immutability")
        ts=[w.f(x) for x in seq]
        need(ts==sorted(set(ts)) and all(start<=t<end for t in ts),"external causal interval/duplicates")


def frame_from_data(d):
    need(type(d) is dict and set(d)=={"tick","mode","switches","external"},"frame fields")
    return Frame(d["tick"],d["mode"],tuple(tuple(x) for x in d["switches"]),tuple(tuple(x) for x in d["external"]))


def current_for(action,i):
    if i<16:
        return 300.
    if action=="G0" and 24<=i<28 or action=="G1" and 28<=i<32:
        return 500.
    return 0.


def solve_cell(initial,external,incoming,boundaries,current):
    """Only solve this cell inside one already-authorized interval."""
    y=np.array(initial[:2],dtype=np.float64,copy=True)
    g=np.array(initial[2:],dtype=np.float64,copy=True)
    evs=[]
    tracker=traces.Trace()
    steps=0
    for start,end in zip(boundaries[:-1],boundaries[1:],strict=True):
        if start in external:
            g[0]+=.7*.3
            g[1]+=.3*.3
        g[2]+=incoming.get(start,0.)
        g0=g.copy()

        def conductance(time):
            dt=time-start
            return tuple(float(g0[i])*p.exp(-dt/tau) for i,tau in enumerate(TAU))

        def rhs(time,state):
            # PortableRK45 reads the two explicitly bound closures and
            # evaluates the actual RHS in the sealed C/MPFR kernel.
            return conductance(time),current,state

        time=start
        while time<end:
            need(y[0]<30. and np.isfinite(y).all(),"invalid pre-step state")
            tracker.begin(rhs,time,y,end)
            solver=p.PortableRK45(rhs,time,y,end,rtol=1e-11,atol=1e-13,max_step=.025,tracker=tracker)
            tracker.solver=solver
            hit=False
            while solver.status=="running":
                message=solver.step()
                need(solver.status!="failed","RK failed "+str(message))
                dense=solver.dense_output()
                steps+=1
                need(steps<=100000 and dense.t_old<dense.t<=end,"interval step bound")
                event=j.dense_crossing(dense)
                if event is not None:
                    stop=w.f(event["t_ms"])
                    need(dense.t_old<stop<=solver.t and all(abs(stop-b)>1e-9 for b in boundaries),
                         "ambiguous threshold/forcing/observation coincidence")
                    event["conductance"]=[w.hx(x) for x in conductance(stop)]
                    event["forcing_interval_ms"]=[w.hx(start),w.hx(end)]
                    root.verify_event(event,"TIGHT")
                    tracker.accept(dense,event)
                    y=np.array([w.f(x) for x in event["post"]],dtype=np.float64)
                    evs.append(event)
                    time=stop
                    hit=True
                    break
                tracker.accept(dense,None)
            if not hit:
                need(solver.status=="finished" and solver.t==end,"forcing end not reached")
                y=solver.y.copy()
                time=end
        g=np.array(conductance(end),dtype=np.float64)
    need(np.isfinite(y).all() and -100.<=y[0]<30. and np.isfinite(g).all() and np.min(g)>=0.,"committed state envelope")
    return np.concatenate((y,g)),evs,tracker.segments,steps


def transition(snapshot,f,action):
    validate_snapshot(snapshot)
    validate_frame(f,snapshot["tick"])
    need(type(action) is str and action in ACTIONS,"invalid public action")
    initial=state_decode(snapshot["state"])
    start,end=time_at(f.tick),time_at(f.tick+1)
    switch_times=[w.f(x[0]) for x in f.switches]
    mode_order=[f.mode]+[x[1] for x in f.switches]
    events=[[] for _ in range(32)]
    ledgers=[[] for _ in range(32)]
    steps=[0]*32
    state=np.empty_like(initial)

    def one(i,incoming):
        external={w.f(t) for t in f.external[i]}
        boundaries=sorted({start,end,*switch_times,*external,*incoming})
        state[:,i],events[i],ledgers[i],steps[i]=solve_cell(
            initial[:,i],external,incoming,boundaries,current_for(action,i))

    for i in range(24,32):
        one(i,{})
    arrivals=[]
    for i in range(24,32):
        for e in events[i]:
            t=w.f(e["t_ms"])
            need(start<t<end,"source event outside causal interval")
            mode=mode_order[bisect_right(switch_times,t)]
            if MODES[mode][(i-24)//4]:
                arrivals.append({"t_ms":e["t_ms"],"source":i,"mode":mode,"increment_nS":.5})
    arrivals.sort(key=lambda a:(w.f(a["t_ms"]),a["source"]))
    incoming=defaultdict(float)
    for a in arrivals:
        incoming[w.f(a["t_ms"])]+=.5
    for i in range(24):
        one(i,dict(incoming) if i<16 else {})
    after={"tick":f.tick+1,"state":state_encode(state),"last_action":action,
           "receiver_spikes":sum(len(e) for e in events[:16]),"population_spikes":sum(len(e) for e in events)}
    payload={"frame":frame_data(f),"action":action,"previous_sha256":digest(snapshot),
             "events":events,"arrivals":arrivals,"ledgers":ledgers,"steps_per_neuron":steps,
             "next_without_chain":after}
    after={**after,"chain":digest(payload)}
    validate_snapshot(after)
    return {"payload":payload,"snapshot":after,"observation":public(after)}


class Runtime:
    """Own only committed state, never the future input tape or a policy callable."""
    __slots__=("_snapshot",)

    def __init__(self,initial):
        self._snapshot=initial_snapshot(initial)

    def observation(self):
        return public(self._snapshot)

    def checkpoint(self):
        # Roundtrip canonical bytes avoids aliasing even nested state lists.
        import json
        return w.canonical(self._snapshot),digest(self._snapshot)

    @classmethod
    def restore(cls,raw,expected_sha256):
        import json
        need(type(raw) is bytes and type(expected_sha256) is str and w.sha(raw)==expected_sha256,"checkpoint custody digest")
        value=json.loads(raw)
        need(w.canonical(value)==raw,"noncanonical checkpoint")
        validate_snapshot(value)
        instance=cls.__new__(cls)
        instance._snapshot=value
        return instance

    def advance(self,f,action):
        # Candidate and independent admission both execute before commit.
        from experiments.cneh_exp_06a import verify
        receipt=transition(self._snapshot,f,action)
        verify.audit(self._snapshot,f,action,receipt)
        # Copy the committed state away from any caller-owned receipt.
        import json
        self._snapshot=json.loads(w.canonical(receipt["snapshot"]))
        return receipt
