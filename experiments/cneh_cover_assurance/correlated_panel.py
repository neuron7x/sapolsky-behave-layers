"""Frozen exact-support and regret-sandwich evaluation."""
from __future__ import annotations

from copy import deepcopy
from fractions import Fraction as F
from itertools import product
import json

from experiments.cneh_exp_06c import algebra as a
from experiments.cneh_exp_06f.run import canonical
from experiments.cneh_exp_06h import reference as h
from experiments.cneh_exp_06i import panel as ip, solver as old
from experiments.cneh_cover_assurance import cover as c, panel as cp
from experiments.cneh_cover_assurance import correlated_decision as d

QUALIFIED="PASS_CONDITIONAL_CORRELATED_SUPPORT_AND_REGRET_ONLY"
WORLDS=((F(1),F(0),F(0)),(F(7,8),F(-16),F(-1)),
        (F(9,8),F(16),F(1)),(F(1),F(8),F(1)),(F(1),F(-8),F(-1)))
ERRORS=((0,0,0),(1,1,1),(-1,-1,-1),(1,-1,1),(-1,1,-1),(1,-1,-1))
CURRENTS=tuple(tuple(map(F,x)) for x in ((-10,-3),(-1,1),(0,0),(120,120),(80,140)))
DOMINANCE=[["0/1"]*5,["1/1"]+["0/1"]*4]
THRESHOLD=[["0/1","1/1","0/1","0/1","0/1"],
           ["1/1","-1/1","0/1","0/1","0/1"]]
TIE=[["0/1"]*5,["0/1"]*5]


def support_panel():
    rows=[]
    for wi,ei,ci,t in product(range(5),range(6),range(5),(0,120,240)):
        g,b,drift=WORLDS[wi]
        e0,e1,e2=(F(x)*h.R for x in ERRORS[ei])
        codes=(b+e0,128*g+b+e1,b+2*drift+e2)
        interval=CURRENTS[ci]
        actual=d.support(codes,interval,t)
        independent=d.vertex_support(codes,interval,t)
        marginal=d.cartesian(codes,interval,t)
        a.need(actual is not None and actual==independent and marginal is not None and
               marginal[0]<=actual[0]<=actual[1]<=marginal[1],"joint support enclosure")
        values=tuple(g*x+b+drift*F(t,120) for x in interval)
        a.need(actual[0]<=min(values)<=max(values)<=actual[1],"electronic truth lost")
        rows.append({"id":[wi,ei,ci,t],"codes":[a.q(x) for x in codes],
                     "joint":a.encode(actual),"cartesian":a.encode(marginal),
                     "strict":actual!=marginal})
    a.need(len(rows)==450 and any(row["strict"] for row in rows),"support roster or strict improvement")
    codes=(F(0),F(128),F(0))
    exact=d.support(codes,(F(120),F(120)),0)
    marginal=d.cartesian(codes,(F(120),F(120)),0)
    a.need(exact==(120-h.R,120+h.R) and marginal==(120-F(23,8)*h.R,120+F(23,8)*h.R),
           "analytic correlation identity")
    # Degenerate reference polytope: all three electronic coordinates fixed.
    b=F(8); gain=F(7,8)
    point_codes=(b,128*gain+b-h.R,b+2+h.R)
    a.need(d.vertices(point_codes)==((gain,b,F(1)),),"degenerate polytope vertex")
    for interval,t in product(CURRENTS,(0,120,240)):
        a.need(d.support(point_codes,interval,t)==d.vertex_support(point_codes,interval,t),
               "degenerate support mismatch")
    invalid=point_codes[:2]+(point_codes[2]+h.STEP,)
    a.need(d.support(invalid,(F(120),F(120)),0) is None and not d.vertices(invalid),
           "empty electronics admitted")
    return {"comparisons":rows,"strict_improvements":sum(row["strict"] for row in rows),
            "analytic_joint":a.encode(exact),"analytic_cartesian":a.encode(marginal),
            "analytic_width_ratio":"23/8","degenerate_checks":15,"empty_polytope":True}


def compatible(index,world_id,stress):
    row=cp.legacy_case(index,world_id,stress)
    record=row["record"]; truth=tuple(map(F,row["known_world"]))
    covers=[]
    for budget,parent in zip((1,7),row["proofs"][1:],strict=True):
        outer=d.correlated(record,parent,h.BOUNDED,budget)
        a.need(d.verify_cover(record,parent,outer,h.BOUNDED,budget),"independent cover")
        a.need(outer["status"]==c.OUTER and
               any(d.contains(d.decode_box(box,4),truth[:4]) for box in outer["frontier"]),
               "compatible truth lost")
        a.need(all(box in parent["frontier"] for box in outer["frontier"]) and
               F(outer["max_width"])<=F(parent["max_width"]),"cover expanded")
        covers.append({"budget":budget,"parent":parent,"correlated":outer})
    decisions=[]
    if world_id==0:
        parent=covers[0]["parent"]; outer=covers[0]["correlated"]
        result=old.solve(record,h.BOUNDED)
        witnesses=[result] if result["status"]==old.WITNESS else []
        for losses in (DOMINANCE,THRESHOLD):
            proof=d.decide(record,parent,outer,witnesses,losses,"0/1",h.BOUNDED,1)
            a.need(d.verify_decision(record,parent,outer,witnesses,losses,"0/1",
                                     h.BOUNDED,1,proof),"independent regret certificate")
            L,_=d.loss_contract(losses,"0/1")
            actual=tuple(d.dot(r,(F(1),*truth[:4])) for r in L)
            regrets=[x-min(actual) for x in actual]
            a.need(all(F(pair[1])>=regrets[k] for k,pair in enumerate(proof["bounds"])),
                   "upper regret excluded true state")
            a.need(all(regrets[k]==0 for k in proof["certified_actions"]),
                   "wrong conditional decision")
            a.need(not witnesses or losses!=DOMINANCE or proof["certified_actions"]==[0],
                   "dominance certificate lost")
            a.need(witnesses or proof["status"]=="UNKNOWN","existence not established")
            decisions.append({"witnesses":witnesses,"proof":proof})
    return {"id":row["id"],"record":record,"known_world":row["known_world"],
            "covers":covers,"decisions":decisions}


def contradiction(record,key):
    parent=c.solve(record,h.BOUNDED,1)
    result=d.correlated(record,parent,h.BOUNDED,1)
    a.need(d.verify_cover(record,parent,result,h.BOUNDED,1) and
           result["status"]==c.EXCLUDED and not result["frontier"],"contradiction lost")
    proof=d.decide(record,parent,result,[],DOMINANCE,"0/1",h.BOUNDED,1)
    a.need(proof["status"]=="CONTRADICTION" and not proof["certified_actions"] and
           d.verify_decision(record,parent,result,[],DOMINANCE,"0/1",h.BOUNDED,1,proof),
           "vacuous decision")
    return {"id":key,"record":record,"parent":parent,"correlated":result,"decision":proof}


def pair_witness():
    """Two separately verified compatible worlds imply opposing zero-regret actions."""
    x=(F(1,2),)*4
    nuisance=ip.CLEAN_WORLDS[0]
    record,_=ip.clean_record(F(-71),x,nuisance)
    base=old.solve(record,h.BOUNDED)
    a.need(base["status"]==old.WITNESS,"base constructive fixture")
    _,observed,refs=h.parse(record)
    proofs=[]
    for sign in (-1,1):
        world=(x[0]+sign*F(1,2**20),*x[1:],*nuisance)
        cert=old.witness_for(world,observed,refs)
        a.need(cert is not None,"constructed alternative not compatible")
        item=deepcopy(base)
        item["certificate"]={"kind":"WITNESS","witness":cert}
        a.need(old.verify(record,item,h.BOUNDED),"constructed alternative verifier")
        proofs.append(item)
    parent=c.solve(record,h.BOUNDED,1)
    outer=d.correlated(record,parent,h.BOUNDED,1)
    result=d.decide(record,parent,outer,proofs,THRESHOLD,"0/1",h.BOUNDED,1)
    a.need(result["status"]=="NO_EPSILON_ACTION" and result["excluded_actions"]==[0,1] and
           all(F(pair[0])==F(1,2**19) for pair in result["bounds"]) and
           d.verify_decision(record,parent,outer,proofs,THRESHOLD,"0/1",h.BOUNDED,1,result),
           "opposing compatible-world certificate")
    return {"record":record,"parent":parent,"outer":outer,"witnesses":proofs,"decision":result}


def controls():
    pair=pair_witness()
    record,parent,outer,ws=(pair[k] for k in ("record","parent","outer","witnesses"))
    valid=d.decide(record,parent,outer,ws,TIE,"0/1",h.BOUNDED,1)
    a.need(valid["certified_actions"]==[0,1],"ties incorrectly forced unique")
    no_witness=d.decide(record,parent,outer,[],DOMINANCE,"0/1",h.BOUNDED,1)
    a.need(no_witness["status"]=="UNKNOWN" and not no_witness["certified_actions"],"vacuity")
    zero=c.solve(record,h.BOUNDED,0)
    outer_zero=d.correlated(record,zero,h.BOUNDED,0)
    a.need(d.decide(record,zero,outer_zero,[],THRESHOLD,"0/1",h.BOUNDED,0)["status"]=="UNKNOWN",
           "budget exhaustion promoted")
    unverified=c.solve(record)
    unknown=d.correlated(record,unverified,"UNVERIFIED",c.MAX_NODES)
    a.need(d.decide(record,unverified,unknown,[],DOMINANCE,"0/1","UNVERIFIED",c.MAX_NODES)["status"]
           =="UNKNOWN","unverified authority")
    results={"TIE":"MULTIPLE_CERTIFIED","NO_WITNESS":"UNKNOWN","ZERO_BUDGET":"UNKNOWN",
             "UNVERIFIED":"UNKNOWN","OPPOSING_WITNESSES":"NO_EPSILON_ACTION"}
    def reject(name,fn):
        try:
            fn()
        except (ValueError,TypeError,KeyError,IndexError):
            results[name]="REJECTED"
        else:
            raise ValueError("mutation survived: "+name)
    for name,key,value in (("WRONG_RECORD","record_sha256","0"*64),
                           ("WRONG_OUTER","outer_sha256","0"*64),
                           ("WRONG_WITNESSES","witnesses_sha256","0"*64),
                           ("WRONG_STATUS","status","UNKNOWN"),
                           ("WRONG_LOSS","losses",DOMINANCE),
                           ("WRONG_EPSILON","epsilon","1/1"),
                           ("WRONG_ACTIONS","certified_actions",[0]),
                           ("BOOLEAN_WITNESS_COUNT","witness_count",True),
                           ("FORGED_AUTHORITY","scientific_promotion_authorized",True)):
        forged=deepcopy(valid); forged[key]=value
        a.need(canonical(forged)!=canonical(valid),"vacuous decision mutation")
        reject(name,lambda forged=forged:d.verify_decision(
            record,parent,outer,ws,TIE,"0/1",h.BOUNDED,1,forged))
    bad=deepcopy(outer); bad["frontier"].pop()
    reject("DROPPED_FRONTIER",lambda:d.verify_cover(record,parent,bad,h.BOUNDED,1))
    bad_ws=deepcopy(ws); bad_ws[0]["certificate"]["witness"]["samples"][0]["t_ms"]=False
    reject("BOOLEAN_WITNESS_TIME",lambda:d.decide(record,parent,outer,bad_ws,TIE,"0/1",h.BOUNDED,1))
    reject("DUPLICATE_WITNESS",lambda:d.decide(record,parent,outer,[ws[0],ws[0]],TIE,"0/1",h.BOUNDED,1))
    reject("WITNESS_BUDGET",lambda:d.decide(record,parent,outer,ws*5,TIE,"0/1",h.BOUNDED,1))
    reject("NEGATIVE_TOLERANCE",lambda:d.loss_contract(TIE,"-1/1"))
    reject("EMPTY_ACTIONS",lambda:d.loss_contract([],"0/1"))
    reject("LOSS_COEFFICIENT_DOMAIN",lambda:d.loss_contract([["17/1"]*5,TIE[0]],"0/1"))
    reject("BOOLEAN_LOSS",lambda:d.loss_contract([[True]*5,TIE[0]],"0/1"))
    reject("STALE_TOLERANCE",lambda:d.verify_decision(record,parent,outer,ws,TIE,"1/1",h.BOUNDED,1,valid))
    return {"dispositions":results,"opposing_witnesses":pair,"tie_certificate":valid}


def report():
    failures=[]; cases=[]; negatives=[]; extras={}
    for name,operation in (("support",support_panel),("controls",controls)):
        try:
            extras[name]=operation()
        except Exception as exc:
            failures.append({"id":name,"error_type":type(exc).__name__,"error":str(exc)})
    for index,world_id,stress in product(ip.TRUTHS,range(2),(False,True)):
        try:
            cases.append(compatible(index,world_id,stress))
        except Exception as exc:
            failures.append({"id":[index,world_id,stress],"error_type":type(exc).__name__,"error":str(exc)})
    jobs=[]
    for b,sign in product((-8,8),(-1,1)):
        jobs.append((["REFERENCE",b,sign],lambda b=b,sign=sign:ip.marginal_conflict(F(b),sign)["record"]))
    for t,y in ((0,900),(60,-100)):
        jobs.append((["GROSS",t,y],lambda t=t,y=y:ip.current_conflict(t,F(y))["record"]))
    for sign in (-1,1):
        jobs.append((["SUBTLE",sign],lambda sign=sign:cp.subtle_case(sign)["record"]))
    for key,operation in jobs:
        try:
            negatives.append(contradiction(operation(),key))
        except Exception as exc:
            failures.append({"id":key,"error_type":type(exc).__name__,"error":str(exc)})
    cover_checks=sum(len(row["covers"]) for row in cases)
    decisions=[d["proof"] for row in cases for d in row["decisions"]]
    counts={}
    for item in decisions:
        counts[item["status"]]=counts.get(item["status"],0)+1
    if not failures:
        a.need(len(cases)==32 and cover_checks==64 and len(decisions)==32 and len(negatives)==8,
               "frozen evaluation roster")
    return {"experiment":"CNEH-COVER-02","scope":d.SCOPE,
            "qualification":"FAIL_FROZEN_GATE" if failures else QUALIFIED,
            "cases":cases,"contradictions":negatives,"failures":failures,
            "cover_checks":cover_checks,"decision_cases":len(decisions),"decision_counts":counts,
            "strict_width_improvements":sum(F(row["correlated"]["max_width"])<F(row["parent"]["max_width"])
                                            for case in cases for row in case["covers"]),
            **extras,**d.NEGATIVE}
