"""Finite native streaming qualification with independent raw receipt replay."""
from __future__ import annotations

import argparse
import gzip
import io
import os
from pathlib import Path

import numpy as np

from experiments.cneh_exp_05j import verify as root
from experiments.cneh_exp_05x import worlds as w
from experiments.cneh_exp_05x import verify as xv
from experiments.cneh_exp_05y import run as custody
from experiments.cneh_exp_05y import portable
from experiments.cneh_exp_06a import attacks, inputs, runtime as rt, verify

EXPERIMENT="CNEH-EXP-06A"
ARCHES=("x86_64","aarch64")
MAX_RAW=128*1024*1024
COUNT_FIELDS=("accepted_steps","rejected_trials","rhs_evaluations","synaptic_stops",
              "root_certificates","forcing_stops","source_arrivals")


def need(c,msg):
    if not c:
        raise ValueError(msg)


def play(world,perturb=False,start=0,checkpoint=None):
    if start==0:
        need(checkpoint is None,"unexpected start checkpoint")
        engine=rt.Runtime(world["initial"])
    else:
        need(checkpoint is not None,"missing start checkpoint")
        engine=rt.Runtime.restore(*checkpoint)
        need(engine.observation()["tick"]==start,"restored start tick")
    rows=[]
    for k in range(start,512):
        f,a=inputs.frame_at(world,k,perturb)
        need(engine.observation()["tick"]==k,"observation chronology")
        rows.append(engine.advance(f,a))
    return rows


def evaluate(world,rows,perturb=False):
    need(type(rows) is list and len(rows)==512,"full frame roster")
    prev=rt.initial_snapshot(world["initial"])
    states=[rt.state_decode(prev["state"]).tolist()]
    times=[[] for _ in range(32)]
    counts=dict.fromkeys(COUNT_FIELDS,0)
    max_g=0.
    for k,rec in enumerate(rows):
        f,a=inputs.frame_at(world,k,perturb)
        audit=verify.audit(prev,f,a,rec)
        for key in counts:
            counts[key]+=audit[key]
        max_g=max(max_g,audit["max_conductance_residual_nS"])
        prev=rec["snapshot"]
        states.append(rt.state_decode(prev["state"]).tolist())
        for i,e in enumerate(rec["payload"]["events"]):
            times[i].extend(w.f(x["t_ms"]) for x in e)
    need(len(states)==513 and all(ts==sorted(set(ts)) for ts in times),"physical trajectory roster")
    return states,times,{"counts":counts,"max_conductance_residual_nS":max_g,
                          "final_checkpoint_sha256":w.digest(prev),
                          "receipt_chain":prev["chain"],"receipt_sha256":w.digest(rows),
                          "public_observation_sha256":w.digest([r["observation"] for r in rows])}


def summarize(index,world,refs,payload):
    need(set(payload)=={"baseline","alternative","restore_hashes","attacks","live_r1"},"evidence payload roster")
    rows=payload["baseline"]
    states,times,ledger=evaluate(world,rows)
    comparisons=[]
    for name,ref in refs.items():
        comparisons.append({"reference":name,**root.comparison(states,times,ref["states"],ref["events"])})
    if index<8:
        need(payload["alternative"] is None and payload["restore_hashes"] is None and payload["attacks"] is None
             and payload["live_r1"] is None,"unexpected counterfactual on archived reference")
        prefix=None
    else:
        alternative=payload["alternative"]
        alt_states,alt_times,alt=evaluate(world,alternative,True)
        need(all(w.canonical(a)==w.canonical(b) for a,b in zip(rows[:256],alternative[:256],strict=True)),
             "future input changed committed prefix")
        need(any(a["snapshot"]["state"]!=b["snapshot"]["state"] for a,b in zip(rows[256:],alternative[256:],strict=True)),
             "vacuous future intervention")
        need(payload["restore_hashes"]==[w.digest(r) for r in rows[256:]],"restored suffix differs")
        names={"STALE_TICK","FUTURE_TICK","FUTURE_IMPULSE","DUPLICATE_IMPULSE","INVALID_MODE","OUTSIDE_SWITCH",
               "INVALID_ACTION","WRONG_CHECKPOINT_DIGEST","SELF_REHASHED_STALE_CHECKPOINT","HIDDEN_PUBLIC_FIELD",
               "OBSERVATION_MUTATION","ACTION_BINDING","STAGE_CROSS","MISSING_BOUNDARY","DUPLICATE_BOUNDARY",
               "REHASHED_COMMITTED_STATE","MISSING_RESET","ROUTE_ROSTER","RECEIPT_ALIAS"}
        need(set(payload["attacks"])==names and all(type(x) is str and bool(x) for x in payload["attacks"].values())
             and payload["attacks"]["RECEIPT_ALIAS"]=="NO_ALIAS","negative control receipt")
        prefix={"identical_prefix_frames":256,"identical_observation_at_fork":True,
                "divergent_suffix_frames":sum(a["snapshot"]["state"]!=b["snapshot"]["state"] for a,b in zip(rows[256:],alternative[256:],strict=True)),
                "exact_restore_frames":256,"alternative":alt,"negative_controls":payload["attacks"]}
    return {"case":index,"world_id":world["id"],"arm":world["arm"],
            "input_sha256":w.digest(world),"frames":512,"ledger":ledger,"comparisons":comparisons,
            "prefix":prefix,"live_r1":payload["live_r1"],
            "status":"PASS_FINITE" if all(x["status"]=="PASS_FINITE" for x in comparisons) else "FAIL"}


def compute(index,world,refs,old):
    baseline=play(world)
    payload={"baseline":baseline,"alternative":None,"restore_hashes":None,"attacks":None,"live_r1":None}
    if index>=8:
        live=portable.simulate(world)
        xv.audit(world,live)
        need(live["physical_sha256"]==old["physical_sha256"] and live["trace_sha256"]==old["trace_sha256"]
             and w.canonical(live["physical"])==w.canonical(old["physical"]),"live R1 differs from sealed original")
        payload["live_r1"]={"physical_sha256":live["physical_sha256"],"trace_sha256":live["trace_sha256"],"exact_archive":True}
        payload["alternative"]=play(world,True)
        checkpoint=baseline[255]["snapshot"]
        resumed=play(world,start=256,checkpoint=(w.canonical(checkpoint),w.digest(checkpoint)))
        payload["restore_hashes"]=[w.digest(r) for r in resumed]
        payload["attacks"]=attacks.run(world,baseline)
    return payload,summarize(index,world,refs,payload)


def run(args):
    world,refs,old=inputs.load_case(args.archives,args.case)
    fp=custody.fingerprint(args.arch,args.install)
    payload,summary=compute(args.case,world,refs,old)
    raw=w.canonical(payload)
    need(len(raw)<=MAX_RAW,"raw evidence size")
    report={"experiment":EXPERIMENT,"head_sha":os.environ["HEAD_SHA"],"run_id":os.environ["GITHUB_RUN_ID"],
            "architecture":args.arch,"fingerprint":fp,"payload_sha256":w.sha(raw),"summary":summary,
            "scientific_promotion":"BLOCKED","scientific_promotion_authorized":False,
            "blind_causal_cohort":"BLOCKED","historical_native_replay":"FAIL_PRESERVED"}
    args.out.mkdir()
    (args.out/"raw.json.gz").write_bytes(gzip.compress(raw,mtime=0))
    custody.write(args.out/"report.json",report)
    (args.out/"install.json").write_bytes(args.install.read_bytes())
    custody.seal(args.out,{"report.json","raw.json.gz","install.json"})
    print(w.canonical({k:v for k,v in report.items() if k!="fingerprint"}).decode(),end="")


def read_payload(path):
    with gzip.open(path,"rb") as f:
        data=f.read(MAX_RAW+1)
    need(len(data)<=MAX_RAW,"raw evidence bound")
    value=custody.json_strict(data)
    need(w.canonical(value)==data,"noncanonical raw evidence")
    return value,w.sha(data)


def aggregate(args):
    need({p.name for p in args.profiles.iterdir()}=={f"cneh06a-{arch}-{i}" for arch in ARCHES for i in range(12)},"complete native roster")
    results=[]
    for i in range(12):
        world,refs,old=inputs.load_case(args.archives,i)
        cases=[]
        for arch in ARCHES:
            folder=args.profiles/f"cneh06a-{arch}-{i}"
            custody.authenticate(folder,{"report.json","raw.json.gz","install.json"})
            report=custody.read(folder/"report.json")
            need(report["experiment"]==EXPERIMENT and report["architecture"]==arch and report["head_sha"]==args.head
                 and report["run_id"]==args.run_id and report["scientific_promotion_authorized"] is False
                 and report["blind_causal_cohort"]=="BLOCKED","native report identity")
            custody.check_fp(report["fingerprint"],arch,args.head,args.run_id,custody.file_sha(folder/"install.json"))
            raw,sha=read_payload(folder/"raw.json.gz")
            need(sha==report["payload_sha256"],"raw receipt hash")
            independently=summarize(i,world,refs,raw)
            stored=report["summary"]
            # Independent analytic residual is evaluated with verifier libm;
            # it is bounded, not asserted bitwise across CPU architectures.
            for a,b in ((stored["ledger"],independently["ledger"]),):
                need(all(a[k]==b[k] for k in b if k!="max_conductance_residual_nS")
                     and 0<=a["max_conductance_residual_nS"]<=1e-10,"baseline independent recomputation")
            if i>=8:
                need(raw["live_r1"]=={"physical_sha256":old["physical_sha256"],"trace_sha256":old["trace_sha256"],"exact_archive":True},"sealed R1 comparator")
                # Recompute all serialized receipt attacks on this evidence,
                # excluding no input; runtime negative controls also execute in worker.
                needed=stored["prefix"];actual=independently["prefix"]
                need(all(needed[k]==actual[k] for k in actual if k!="alternative")
                     and all(needed["alternative"][k]==actual["alternative"][k] for k in actual["alternative"] if k!="max_conductance_residual_nS")
                     and 0<=needed["alternative"]["max_conductance_residual_nS"]<=1e-10,"prefix independent recomputation")
            need(stored["comparisons"]==independently["comparisons"] and stored["status"]==independently["status"],"reference recomputation")
            cases.append({"architecture":arch,"payload_sha256":sha,"summary":independently})
            del raw
        exact=cases[0]["payload_sha256"]==cases[1]["payload_sha256"]
        results.append({"case":i,"world_id":world["id"],"exact":exact,"native":cases,
                        "status":"PASS_FINITE" if exact and all(x["summary"]["status"]=="PASS_FINITE" for x in cases) else "FAIL"})
    total=sum(x["status"]=="PASS_FINITE" for x in results)
    report={"experiment":EXPERIMENT,"head_sha":args.head,"run_id":args.run_id,
            "qualification":"PASS_FINITE_ONLY" if total==12 else "FAIL",
            "cases":12,"qualified_cases":total,"exact_cross_cpu_pairs":sum(x["exact"] for x in results),
            "reference_cases":sum(x["status"]=="PASS_FINITE" for x in results[:8]),
            "ood_cases":sum(x["status"]=="PASS_FINITE" for x in results[8:]),
            "native_primary_episodes":24,"prefix_tests":8,"restoration_tests":8,
            "negative_controls_per_ood_episode":19,
            "scope":"FINITE_STREAMING_CAUSAL_PREFIX_NOT_CLOSED_LOOP_EFFICACY",
            "historical_native_replay":"FAIL_PRESERVED","scientific_promotion_authorized":False,
            "scientific_promotion":"BLOCKED","blind_causal_cohort":"BLOCKED","reports":results}
    args.out.mkdir()
    custody.write(args.out/"report.json",report)
    custody.seal(args.out,{"report.json"})
    print(w.canonical({k:v for k,v in report.items() if k!="reports"}).decode(),end="")
    return 0 if total==12 else 2


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    sub=ap.add_subparsers(dest="command",required=True)
    r=sub.add_parser("run");a=sub.add_parser("aggregate")
    for p in (r,a):
        p.add_argument("--archives",type=Path,required=True)
        p.add_argument("--out",type=Path,required=True)
    r.add_argument("--case",type=int,choices=range(12),required=True)
    r.add_argument("--arch",choices=ARCHES,required=True)
    r.add_argument("--install",type=Path,required=True)
    a.add_argument("--profiles",type=Path,required=True)
    a.add_argument("--head",required=True);a.add_argument("--run-id",required=True)
    args=ap.parse_args()
    if args.command=="run":
        run(args);return 0
    return aggregate(args)


if __name__=="__main__":
    raise SystemExit(main())
