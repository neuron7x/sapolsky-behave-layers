"""Causal-prefix, restore, and rehashed-evidence negative controls."""
from __future__ import annotations

import copy
from dataclasses import replace

from experiments.cneh_exp_05x import worlds as w
from experiments.cneh_exp_06a import inputs, runtime as rt, verify


def reject(fn):
    try:
        fn()
    except (ValueError,TypeError,KeyError,OverflowError) as exc:
        return str(exc)
    raise ValueError("negative control escaped")


def rehash(receipt):
    p=receipt["payload"]
    s=receipt["snapshot"]
    p["next_without_chain"]={k:v for k,v in s.items() if k!="chain"}
    s["chain"]=w.digest(p)
    return receipt


def run(world,baseline):
    k=256
    previous=baseline[k-1]["snapshot"]
    checkpoint=w.canonical(previous)
    engine=rt.Runtime.restore(checkpoint,w.digest(previous))
    frame,action=inputs.frame_at(world,k)
    before=engine.checkpoint()
    end=(k+1)/10.
    start=k/10.
    bad_external=list(frame.external)
    bad_external[0]=(w.hx(end),)
    duplicate=list(frame.external)
    duplicate[0]=(w.hx(start),w.hx(start))
    cases={
        "STALE_TICK":lambda:engine.advance(replace(frame,tick=k-1),action),
        "FUTURE_TICK":lambda:engine.advance(replace(frame,tick=k+1),action),
        "FUTURE_IMPULSE":lambda:engine.advance(replace(frame,external=tuple(bad_external)),action),
        "DUPLICATE_IMPULSE":lambda:engine.advance(replace(frame,external=tuple(duplicate)),action),
        "INVALID_MODE":lambda:engine.advance(replace(frame,mode=4),action),
        "OUTSIDE_SWITCH":lambda:engine.advance(replace(frame,switches=((w.hx(end),0),)),action),
        "INVALID_ACTION":lambda:engine.advance(frame,"UNKNOWN"),
        "WRONG_CHECKPOINT_DIGEST":lambda:rt.Runtime.restore(checkpoint,"0"*64),
    }
    modified=copy.deepcopy(previous)
    modified["state"][0][0]=w.hx(w.f(modified["state"][0][0])+.01)
    cases["SELF_REHASHED_STALE_CHECKPOINT"]=lambda:rt.Runtime.restore(w.canonical(modified),w.digest(previous))
    out={}
    for name,fn in cases.items():
        out[name]=reject(fn)
        rt.need(engine.checkpoint()==before and engine.observation()==rt.public(previous),"failed transaction mutated state")
    good=baseline[k]
    def check(bad,prior=previous,f=frame,a=action):
        return reject(lambda:verify.audit(prior,f,a,rehash(bad)))
    bad=copy.deepcopy(good);bad["observation"]["latent_mode"]=frame.mode
    out["HIDDEN_PUBLIC_FIELD"]=check(bad)
    bad=copy.deepcopy(good);bad["observation"]["population_spikes"]+=1
    out["OBSERVATION_MUTATION"]=check(bad)
    bad=copy.deepcopy(good);bad["payload"]["action"]="G0" if action=="WAIT" else "WAIT"
    out["ACTION_BINDING"]=check(bad)
    bad=copy.deepcopy(good);bad["payload"]["ledgers"][0][0]["rhs_max"]=w.hx(end+.01)
    out["STAGE_CROSS"]=check(bad)
    bad=copy.deepcopy(good);bad["payload"]["ledgers"][0].pop(0)
    out["MISSING_BOUNDARY"]=check(bad)
    bad=copy.deepcopy(good);bad["payload"]["ledgers"][0].insert(0,copy.deepcopy(bad["payload"]["ledgers"][0][0]))
    out["DUPLICATE_BOUNDARY"]=check(bad)
    bad=copy.deepcopy(good);bad["snapshot"]["state"][0][0]=w.hx(w.f(bad["snapshot"]["state"][0][0])+.01)
    out["REHASHED_COMMITTED_STATE"]=check(bad)
    # Select a real witnessed reset and a routed event if one exists.
    j=next(i for i,r in enumerate(baseline) if any(r["payload"]["events"]))
    prior=rt.initial_snapshot(world["initial"]) if j==0 else baseline[j-1]["snapshot"]
    f,a=inputs.frame_at(world,j)
    bad=copy.deepcopy(baseline[j]);cell=next(i for i,e in enumerate(bad["payload"]["events"]) if e)
    bad["payload"]["events"][cell].pop()
    out["MISSING_RESET"]=check(bad,prior,f,a)
    j=next((i for i,r in enumerate(baseline) if r["payload"]["arrivals"]),None)
    if j is None:
        bad=copy.deepcopy(good);bad["payload"]["arrivals"].append({"t_ms":w.hx((start+end)/2),"source":24,"mode":0,"increment_nS":.5})
        out["ROUTE_ROSTER"]=check(bad)
    else:
        prior=rt.initial_snapshot(world["initial"]) if j==0 else baseline[j-1]["snapshot"]
        f,a=inputs.frame_at(world,j)
        bad=copy.deepcopy(baseline[j]);bad["payload"]["arrivals"].pop(0)
        out["ROUTE_ROSTER"]=check(bad,prior,f,a)
    # Receipt is caller-owned; mutating it cannot change committed engine state.
    made=engine.advance(frame,action)
    expected=engine.checkpoint()
    made["snapshot"]["state"][0][0]="invalid"
    made["observation"]["tick"]=-1
    rt.need(engine.checkpoint()==expected,"caller-owned receipt aliases committed state")
    out["RECEIPT_ALIAS"]="NO_ALIAS"
    rt.need(len(out)==19,"negative-control roster")
    return out
