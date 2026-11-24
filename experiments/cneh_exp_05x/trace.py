"""Passively instrument the frozen EXP05J kernel; no arithmetic replacement."""
from __future__ import annotations

from collections import defaultdict
import hashlib
import inspect
import math
import struct
from unittest.mock import patch

import numpy as np
from scipy.integrate import RK45

from experiments.cneh_exp_05j import integrator as j
from experiments.cneh_exp_05x import worlds as w


def pack(*values):
    a=np.asarray(values,dtype=">f8")
    w.need(np.isfinite(a).all(),"nonfinite trace")
    return a.tobytes()


def array_bytes(a):
    a=np.asarray(a,dtype=">f8")
    w.need(np.isfinite(a).all(),"nonfinite stage")
    return a.tobytes(order="C")


class Trace:
    def __init__(self):
        self.segments=[]
        self.active=None
        self.solver=None

    def begin(self,fun,t0,y0,bound):
        closure=inspect.getclosurevars(fun).nonlocals
        w.need("conductance" in closure,"parent RHS contract drift")
        self.conductance=closure["conductance"]
        self.active={"start":w.hx(t0),"bound":w.hx(bound),"Vw_start":[w.hx(x) for x in y0],
                     "g_start":[w.hx(x) for x in self.conductance(t0)],
                     "rhs_count":0,"rhs_min":w.hx(t0),"rhs_max":w.hx(t0),
                     "trials":0,"rejected":0,"accepted":0,"chunks":[]}
        self.segments.append(self.active)
        self.hash=hashlib.sha256()
        self.chunk=hashlib.sha256()
        self.chunk_n=0

    def rhs(self,t):
        row=self.active
        w.need(w.f(row["start"])<=t<=w.f(row["bound"]),"RHS stage crosses t_syn/forcing bound")
        row["rhs_count"]+=1
        row["rhs_min"]=w.hx(min(t,w.f(row["rhs_min"])))
        row["rhs_max"]=w.hx(max(t,w.f(row["rhs_max"])))

    def add(self,raw):
        self.hash.update(raw)
        self.chunk.update(raw)

    def trial(self,solver,K,h,scale,error):
        row=self.active
        row["trials"]+=1
        row["rejected"]+=int(error>=1.)
        self.add(b"T"+pack(solver.t,h,error)+array_bytes(K)+array_bytes(scale))

    def accept(self,dense,event):
        row=self.active
        solver=self.solver
        t= w.f(event["t_ms"]) if event is not None else float(solver.t)
        w.need(w.f(row["start"])<=dense.t_old<t<=solver.t<=w.f(row["bound"]),"accepted step crosses forcing bound")
        row["accepted"]+=1
        self.add(b"A"+pack(dense.t_old,solver.t,solver.h_abs,t)
                 +array_bytes(solver.y)+array_bytes(dense.y_old)+array_bytes(dense.Q)
                 + (w.canonical(event) if event is not None else b"-"))
        self.chunk_n+=1
        if self.chunk_n==64:
            row["chunks"].append(self.chunk.hexdigest())
            self.chunk=hashlib.sha256()
            self.chunk_n=0
        row["end"]=w.hx(t)
        row["accepted_end"]=w.hx(solver.t)
        row["Vw_end"]=event["post"] if event is not None else [w.hx(x) for x in solver.y]
        row["g_end"]=[w.hx(x) for x in self.conductance(t)]
        row["reset"]=event is not None
        if event is not None or solver.status=="finished":
            if self.chunk_n:
                row["chunks"].append(self.chunk.hexdigest())
            row["trace_sha256"]=self.hash.hexdigest()
            w.need(row["trials"]==row["accepted"]+row["rejected"],"trial count binding")

    def solver_class(self):
        tracker=self

        class Traced(RK45):
            def __init__(self,fun,t0,y0,t_bound,**kwargs):
                tracker.begin(fun,float(t0),y0,float(t_bound))
                def guarded(t,y):
                    tracker.rhs(float(t))
                    return fun(t,y)
                super().__init__(guarded,t0,y0,t_bound,**kwargs)
                tracker.solver=self

            def _estimate_error_norm(self,K,h,scale):
                value=super()._estimate_error_norm(K,h,scale)
                tracker.trial(self,K,h,scale,float(value))
                return value

        return Traced


def simulate(world,trace=True):
    initial=np.array([[w.f(v) for v in row] for row in world["initial"]],dtype=np.float64)
    modes=tuple(w.MODES[k] for k in world["mode_order"])
    switches=tuple(w.f(x) for x in world["switches"])
    current=tuple(w.f(x) for x in world["current_switches"])
    arm=world["arm"]
    samples=np.empty((513,5,32),dtype=np.float64)
    events=[[] for _ in range(32)]
    ledgers=[[] for _ in range(32)]
    counts=[0]*32
    original_cross=j.dense_crossing

    def one(i,incoming):
        t=Trace()
        ext=[w.f(x) for x in world["external"][i]]
        if trace:
            def crossing(dense):
                event=original_cross(dense)
                t.accept(dense,event)
                return event
            with patch.object(j,"RK45",t.solver_class()),patch.object(j,"dense_crossing",crossing):
                s,e,n,_=j.cell(initial[:,i],ext,incoming,arm,i,"TIGHT")
        else:
            s,e,n,_=j.cell(initial[:,i],ext,incoming,arm,i,"TIGHT")
        samples[:,:,i]=s
        events[i]=e
        counts[i]=n
        ledgers[i]=t.segments

    with patch.object(j,"MODES",modes),patch.object(j,"SWITCHES",switches),patch.object(j,"CURRENT_SWITCHES",current):
        for i in range(24,32):
            one(i,{})
        arrivals=j.routed_arrivals(events)
        incoming=defaultdict(float)
        for a in arrivals:
            incoming[w.f(a["t_ms"])]+=a["increment_nS"]
        for i in range(24):
            one(i,dict(incoming) if i<16 else {})
    physical={"samples":samples.tolist(),"events":events,"arrivals":arrivals,"accepted_steps":counts}
    return {"physical":physical,"physical_sha256":w.digest(physical),
            "ledgers":ledgers,"trace_sha256":w.digest(ledgers)}
