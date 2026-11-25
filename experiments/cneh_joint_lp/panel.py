"""Frozen independent vertex oracle and continuous-record qualification."""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction as F
from itertools import combinations, product
import json

from experiments.cneh_exp_06c import algebra as a
from experiments.cneh_exp_06f.run import canonical
from experiments.cneh_exp_06h import reference as h
from experiments.cneh_exp_06i import panel as ip
from experiments.cneh_joint_lp import kernel as k, search as s

QUALIFIED="PASS_CONDITIONAL_SHARED_SAMPLE_DUAL_ASSURANCE_ONLY"


def toy_rows(cap,delta):
    return tuple(k.row(name,coef,rhs) for name,coef,rhs in (
        ("X_LO",(-1,0),0),("X_HI",(1,0),1),("Y_LO",(0,-1),0),("Y_HI",(0,1),1),
        ("SUM",(1,1),cap),("DIFF",(1,-1),delta)))


def vertices2(rows):
    """Independent exact geometric oracle; not the simplex implementation."""
    points=set()
    for (_,u,a0),(_,v,b0) in combinations(rows,2):
        det=u[0]*v[1]-u[1]*v[0]
        if det==0:
            continue
        point=((a0*v[1]-u[1]*b0)/det,(u[0]*b0-a0*v[0])/det)
        if all(k.dot(coef,point)<=rhs for _,coef,rhs in rows):
            points.add(point)
    return tuple(sorted(points))


def toy_panel():
    results=[]
    for cap,delta in product(map(F,(0,F(1,2),1,2)),map(F,(-1,F(-1,2),0,1))):
        rows=toy_rows(cap,delta)
        vertices=vertices2(rows)
        for index,sign in product(range(2),(-1,1)):
            target=k.unit(2,index,sign)
            if vertices:
                proof,cost=s.dual(rows,target)
                expected=max(k.dot(target,x) for x in vertices)
                k.need(proof is not None and k.check(rows,target,proof)==expected,
                       "toy exact optimal bound mismatch")
                disposition="EXACT_BOUND"
            else:
                proof,cost=s.dual(rows,(F(0),F(0)),farkas=True)
                k.need(proof is not None and k.check_infeasible(rows,proof),
                       "toy contradiction certificate absent")
                expected=k.decode(proof["bound"])
                disposition="CERTIFIED_INFEASIBLE"
            results.append({"cap":a.q(cap),"delta":a.q(delta),"coordinate":index,"sign":sign,
                            "vertices":[[a.q(v) for v in point] for point in vertices],
                            "disposition":disposition,"bound":k.encode(expected),"proof":proof,
                            "search":cost})
    k.need(len(results)==64,"toy roster")
    return results


def compatible(index,world_id,stress):
    if stress:
        item=ip.stress_case(index,world_id)
        (gain,gamma,delay,tau),sign=ip.STRESS_WORLDS[world_id]
        nuisance=(gain,F(16*sign),F(-sign),gamma,delay,tau)
    else:
        item=ip.clean_case(index,world_id)
        nuisance=ip.CLEAN_WORLDS[world_id]
    record=item["record"]
    truth=tuple(map(F,item["truth"]))
    world=truth+nuisance
    rows=k.checked_system(record)
    lifted=k.lift(world)
    slack=tuple(rhs-k.dot(coef,lifted) for _,coef,rhs in rows)
    k.need(min(slack)>=0,"compatible world excluded by compiled LP")
    proof,cost=s.analyze(record,h.BOUNDED)
    k.need(k.verify(record,proof,h.BOUNDED,s.MAX_PIVOTS) and proof["status"]==k.OUTER,
           "compatible world excluded by proof")
    k.need(all(F(lo)<=x<=F(hi) for x,(lo,hi) in zip(truth,proof["outer_bounds"],strict=True)),
           "physical truth omitted from certified interval")
    k.need(proof["joint_existence_established"] is False,"LP relaxation promoted to existence")
    h_width=F(item["H"]["max_width"])
    return {"id":["STRESS" if stress else "CLEAN",index,world_id],"record":record,
            "known_world":[a.q(x) for x in world],"lifted_world":[a.q(x) for x in lifted],
            "minimum_row_slack":k.encode(min(slack)),"H_max_width":a.q(h_width),
            "I_status":item["I"]["status"],"proof":proof,"search":cost,
            "width_delta":k.encode(F(proof["max_width"])-h_width)}


def contradiction(key,record,required):
    rows=k.checked_system(record)
    proof,cost=s.analyze(record,h.BOUNDED)
    k.need(k.verify(record,proof,h.BOUNDED,s.MAX_PIVOTS),"contradiction proof admission")
    if required:
        k.need(proof["status"]==k.EXCLUDED and k.check_infeasible(rows,proof["exclusion"]),
               "required joint contradiction not certified")
    return {"id":key,"record":record,"required":required,"proof":proof,"search":cost}


def subtle(sign):
    record,_=ip.clean_record(F(-71),(F(1,2),)*4,ip.CLEAN_WORLDS[0])
    sample=record["samples"][h.TIMES.index(60)]
    sample["current_pA"]=a.q(F(sample["current_pA"])+sign)
    return record


def controls():
    record,_=ip.clean_record(F(-71),(F(1,2),)*4,ip.CLEAN_WORLDS[0])
    proof,cost=s.analyze(record,h.BOUNDED)
    k.need(proof["status"]==k.OUTER and k.verify(record,proof,h.BOUNDED,s.MAX_PIVOTS),
           "positive proof control")
    results={}
    for name,profile,budget in (("ZERO_BUDGET",h.BOUNDED,0),("UNVERIFIED","UNVERIFIED",s.MAX_PIVOTS)):
        out,telemetry=s.analyze(record,profile,budget)
        k.need(k.verify(record,out,profile,budget) and
               out["outer_bounds"]==[["0/1","1/1"]]*4 and
               not telemetry and out["exclusion"] is None,"budget or calibration overclaim")
        results[name]="FULL_PRIOR"
    empty=deepcopy(record);empty["references"]["gamma"]="3/1"
    out,_=s.analyze(empty,h.BOUNDED)
    k.need(out["status"]==k.EXCLUDED and k.verify(empty,out,h.BOUNDED,s.MAX_PIVOTS),
           "scalar reference contradiction")
    results["EMPTY_SCALAR_STRIP"]="CERTIFIED_INFEASIBLE"
    box=toy_rows(F(2),F(1))[:4]
    target=(F(1),F(1))
    limited,meta=s.dual(box,target,1)
    k.need(limited is None and meta=={"pivots":1,"reason":"PIVOT_BUDGET"},
           "bounded proposer exhaustion")
    results["PIVOT_EXHAUSTION"]="UNKNOWN"
    equal=toy_rows(F(0),F(0))
    cp,_=s.dual(equal,k.unit(2,0))
    k.need(cp is not None and k.check(equal,k.unit(2,0),cp)==0,
           "boundary equality excluded")
    results["BOUNDARY_EQUALITY"]="EXACT_BOUND"
    rows=k.checked_system(record)
    source=proof["coordinate_proofs"][0][1]
    objective=k.unit(k.DIM,0)
    k.need(source is not None,"coordinate certificate fixture")
    def reject(name,fn):
        try:
            fn()
        except (ValueError,TypeError,KeyError,IndexError):
            results[name]="REJECTED"
        else:
            raise ValueError("proof mutation survived: "+name)
    for name,field,value in (
        ("WRONG_SYSTEM","system_sha256","0"*64),
        ("WRONG_OBJECTIVE","objective",["0/1"]*7),
        ("FORGED_BOUND","bound","-1000/1"),
        ("MISSING_MULTIPLIER","multipliers",source["multipliers"][:-1]),
        ("BOOLEAN_MULTIPLIER","multipliers",[True]+source["multipliers"][1:]),
        ("NEGATIVE_MULTIPLIER","multipliers",["-1/1"]+source["multipliers"][1:]),
        ("NONCANONICAL_RATIONAL","multipliers",["2/2"]+source["multipliers"][1:]),
    ):
        forged=deepcopy(source);forged[field]=value
        k.need(canonical(forged)!=canonical(source),"vacuous mutation")
        reject(name,lambda forged=forged:k.check(rows,objective,forged))
    altered=list(rows);name,coef,rhs=altered[0];altered[0]=(name,coef,rhs+1)
    reject("CHANGED_CONSTRAINT",lambda:k.check(tuple(altered),objective,source))
    reject("WRONG_DIMENSION",lambda:s.dual(rows,(F(1),)))
    reject("FALSE_FARKAS",lambda:k.check_infeasible(rows,k.certificate(
        rows,(F(0),)*7,(F(0),)*len(rows))))
    stale=deepcopy(record);stale["samples"][0]["current_pA"]=a.q(
        F(stale["samples"][0]["current_pA"])+h.STEP)
    reject("STALE_RECORD",lambda:k.verify(stale,proof,h.BOUNDED,s.MAX_PIVOTS))
    for name,field,value in (
        ("FALSE_DISPOSITION","status",k.EXCLUDED),
        ("FALSE_EXISTENCE","joint_existence_established",True),
        ("DROPPED_COORDINATE","coordinate_proofs",proof["coordinate_proofs"][:-1]),
        ("BOOLEAN_BUDGET","pivot_budget_per_solve",True),
        ("OVERSIZED_SCOPE","scope","x"*1025),
    ):
        forged=deepcopy(proof);forged[field]=value
        k.need(canonical(forged)!=canonical(proof),"vacuous mutation")
        reject(name,lambda forged=forged:k.verify(record,forged,h.BOUNDED,s.MAX_PIVOTS))
    forged=deepcopy(proof);forged.update(json.loads('{"scientific_promotion_authorized":true}'))
    reject("FORGED_AUTHORITY",lambda:k.verify(record,forged,h.BOUNDED,s.MAX_PIVOTS))
    reject("EXCESS_BUDGET",lambda:s.analyze(record,h.BOUNDED,129))
    k.need(len(results)==23 and sum(v=="REJECTED" for v in results.values())==18,
           "control roster")
    return results


def report():
    cases=[];negative=[];failures=[];extras={}
    for name,fn in (("toy",toy_panel),("controls",controls)):
        try:
            extras[name]=fn()
        except Exception as exc:
            failures.append({"id":name,"error_type":type(exc).__name__,"error":str(exc)})
    for index,world_id,stress in product(ip.TRUTHS,range(2),(False,True)):
        try:
            cases.append(compatible(index,world_id,stress))
        except Exception as exc:
            failures.append({"id":[index,world_id,stress],"error_type":type(exc).__name__,"error":str(exc)})
    jobs=[]
    for b,sign in product((-8,8),(-1,1)):
        jobs.append((["REFERENCE",b,sign],True,lambda b=b,sign=sign:
                     ip.marginal_conflict(F(b),sign)["record"]))
    for t,y in ((0,900),(60,-100)):
        jobs.append((["GROSS",t,y],True,lambda t=t,y=y:ip.current_conflict(t,F(y))["record"]))
    for sign in (-1,1):
        jobs.append((["SUBTLE",sign],False,lambda sign=sign:subtle(sign)))
    for key,required,fn in jobs:
        try:
            negative.append(contradiction(key,fn(),required))
        except Exception as exc:
            failures.append({"id":key,"error_type":type(exc).__name__,"error":str(exc)})
    if not failures:
        k.need(len(cases)==32 and len(negative)==8,"frozen record roster")
    return {"experiment":"CNEH-JOINT-LP-01","scope":k.SCOPE,
            "qualification":"FAIL_FROZEN_GATE" if failures else QUALIFIED,
            "cases":cases,"contradictions":negative,"failures":failures,
            "strict_width_improvements":sum(F(row["width_delta"])<0 for row in cases),
            "max_lp_width":a.q(max((F(row["proof"]["max_width"]) for row in cases),default=F(0))),
            "max_H_width":a.q(max((F(row["H_max_width"]) for row in cases),default=F(0))),
            **extras,**k.NEGATIVE}
