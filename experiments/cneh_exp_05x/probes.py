"""Separate arithmetic sensitivity and manufactured discontinuity diagnostics."""
from __future__ import annotations

import copy
from fractions import Fraction as F
import math

import numpy as np
from scipy.integrate import RK45

from experiments.cneh_exp_05x import verify as v
from experiments.cneh_exp_05x import worlds as w


def fused(a,b,c):
    return float(F(a)*F(b)+F(c))


def micro(index,variant):
    def rhs(t,y):
        z=.1*float(y[0])+t
        exp=math.exp(z)
        if variant=="EXP_PLUS":
            exp=math.nextafter(exp,math.inf)
        elif variant=="EXP_MINUS":
            exp=math.nextafter(exp,-math.inf)
        value=fused(-.5,float(y[0]),exp) if variant=="FUSED" else -.5*float(y[0])+exp
        return np.array([value])
    solver=RK45(rhs,0.,np.array([index/64.]),.4,rtol=1e-9,atol=1e-11,max_step=.025)
    steps=[]
    states=[]
    while solver.status=="running":
        solver.step()
        w.need(solver.status!="failed","micro solver failure")
        steps.append(w.hx(solver.t));states.append(w.hx(solver.y[0]))
    return {"steps":steps,"states":states}


def one_step(fun,start,end,y):
    s=RK45(fun,start,np.array([y]),end,first_step=end-start,max_step=end-start,rtol=.1,atol=.1)
    s.step()
    w.need(s.status=="finished" and s.t==end,"manufactured trial did not finish")
    return float(s.y[0])


def discontinuity():
    results=[]
    for h in (.5,.25,.125,.0625):
        syn=3*h/7
        exact=-math.expm1(-(h-syn))
        unsplit=one_step(lambda t,y:np.array([-y[0]+float(t>=syn)]),0.,h,0.)
        before=one_step(lambda t,y:np.array([-y[0]]),0.,syn,0.)
        split=one_step(lambda t,y:np.array([1.-y[0]]),syn,h,before)
        results.append({"h":h,"t_syn":syn,"unsplit_error":abs(unsplit-exact),"split_error":abs(split-exact)})
    w.need(all(r["unsplit_error"]>r["split_error"] for r in results),"manufactured discontinuity control failed")
    for a,b in zip(results[:-1],results[1:],strict=True):
        b["unsplit_observed_local_order"]=math.log2(a["unsplit_error"]/b["unsplit_error"])
        b["split_observed_local_order"]=math.log2(a["split_error"]/b["split_error"]) if b["split_error"] else None
    return results


def sensitivity():
    a,b,c=1.+2.**-27,1.-2.**-27,-1.
    separate=a*b+c
    single=fused(a,b,c)
    w.need(separate==0. and single==-2.**-54,"FMA exact rational witness failed")
    counts={name:{"changed_step_sequence":0,"changed_full_trace":0} for name in ("EXP_PLUS","EXP_MINUS","FUSED")}
    for i in range(64):
        base=micro(i,"BASE")
        for name in counts:
            test=micro(i,name)
            counts[name]["changed_step_sequence"]+=int(test["steps"]!=base["steps"])
            counts[name]["changed_full_trace"]+=int(test!=base)
    return {"fma_witness":{"separate":w.hx(separate),"fused_reference":w.hx(single)},
            "microcases":64,"mutations":counts,"manufactured_discontinuity":discontinuity(),
            "scope":"LOCAL_ARITHMETIC_MUTATIONS_NOT_CPU_CAUSAL_ATTRIBUTION"}


def boundary_attacks(world,result):
    # Recompute all local digests after each corruption so the semantic checks,
    # rather than a stale outer checksum, must reject it.
    out={}
    for name in ("STAGE_CROSS","OMITTED_BOUNDARY","DUPLICATE_BOUNDARY","ALTERED_JUMP","RAW_GABA"):
        bad=copy.deepcopy(result)
        rows=bad["ledgers"][0]
        if name=="STAGE_CROSS":
            rows[0]["rhs_max"]=w.hx(math.nextafter(w.f(rows[0]["bound"]),math.inf))
        elif name=="OMITTED_BOUNDARY":
            rows.pop(0)
        elif name=="DUPLICATE_BOUNDARY":
            rows.insert(0,copy.deepcopy(rows[0]))
        elif name=="ALTERED_JUMP":
            rows[0]["g_start"][0]=w.hx(w.f(rows[0]["g_start"][0])+.01)
        else:
            bad["physical"]["samples"][1][4][0]+=.01
        bad["trace_sha256"]=w.digest(bad["ledgers"])
        bad["physical_sha256"]=w.digest(bad["physical"])
        try:
            v.audit(world,bad)
        except (ValueError,TypeError,KeyError,OverflowError) as exc:
            out[name]=str(exc)
        else:
            raise ValueError("boundary mutation accepted: "+name)
    return out
