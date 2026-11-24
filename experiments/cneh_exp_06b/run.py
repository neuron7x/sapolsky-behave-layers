"""Finite native intervention campaign and independent receipt admission."""
from __future__ import annotations

import argparse
import copy
import gzip
import json
import os
from pathlib import Path

from experiments.cneh_exp_05x import worlds as w
from experiments.cneh_exp_05y import run as custody
from experiments.cneh_exp_06a import runtime as rt,verify
from experiments.cneh_exp_06b import certificate as theorem,fixtures as f

EXPERIMENT="CNEH-EXP-06B"
ARCHES=("x86_64","aarch64")
PARENT=(14912290707,"51a6e0d9886a59ea48ae5ad52f6f7753ecc6c468fe18eadb568d0846a696d84d")
PARENT_HEAD="7de4b8c6eaf1edbb1ac977c9787c004a3db19baa"
MAX_RAW=64*1024*1024


def need(c,msg):
    if not c:
        raise ValueError(msg)


def authenticate_parent(root):
    from experiments.cneh_exp_06a.inputs import archive
    value=custody.json_strict(archive(root,PARENT,{"report.json"})["report.json"])
    need(value["head_sha"]==PARENT_HEAD and value["run_id"]=="45375987636"
         and value["qualification"]=="PASS_FINITE_ONLY" and value["qualified_cases"]==12
         and value["exact_cross_cpu_pairs"]==12 and value["reference_cases"]==8
         and value["scientific_promotion_authorized"] is False and value["blind_causal_cohort"]=="BLOCKED","parent causal runtime receipt")
    return w.digest(value)


def spec(shard,identity):
    if shard.startswith("silent-"):
        i,v=identity
        initial,mode=f.silent(v)
        actions=f.actions(i)
    elif shard=="active":
        a,mode=identity
        initial=f.active()
        actions=[a]
    else:
        a,coord,sign=identity
        if coord==-1:
            initial,mode=f.silent("BASE")
        else:
            initial,mode,_=f.perturbed(coord,sign)
        actions=[a]
    frames=[f.frame(k,mode) for k in range(len(actions))]
    return initial,frames,actions


def compute(shard):
    rows=[]
    for identity in f.roster(shard):
        initial,frames,actions=spec(shard,identity)
        engine=rt.Runtime(initial)
        receipts=[engine.advance(frame,a) for frame,a in zip(frames,actions,strict=True)]
        rows.append({"identity":list(identity),"initial_sha256":w.digest(initial),"receipts":receipts})
    return rows


def counts(obs):
    return (obs["receiver_spikes"],obs["population_spikes"])


def audit_row(shard,identity,row):
    initial,frames,actions=spec(shard,identity)
    if shard.startswith("silent-"):
        theorem.certify_silent_inputs(initial,frames,actions)
    need(type(row) is dict and set(row)=={"identity","initial_sha256","receipts"}
         and row["identity"]==list(identity) and row["initial_sha256"]==w.digest(initial)
         and len(row["receipts"])==len(actions),"intervention row identity")
    previous=rt.initial_snapshot(initial)
    summary={"frames":len(actions),"accepted_steps":0,"root_certificates":0,"synaptic_stops":0}
    for frame,a,receipt in zip(frames,actions,row["receipts"],strict=True):
        checked=verify.audit(previous,frame,a,receipt)
        for k in ("accepted_steps","root_certificates","synaptic_stops"):
            summary[k]+=checked[k]
        previous=receipt["snapshot"]
    return summary


def group_check(shard,rows):
    roster=f.roster(shard)
    need(type(rows) is list and len(rows)==len(roster),"complete intervention roster")
    totals={"frames":0,"accepted_steps":0,"root_certificates":0,"synaptic_stops":0}
    for identity,row in zip(roster,rows,strict=True):
        for k,v in audit_row(shard,identity,row).items():
            totals[k]+=v
    if shard.startswith("silent-"):
        physical_differences=graph_differences=pairs=0
        for i in range(0,len(rows),len(f.VARIANTS)):
            base=rows[i]
            base_obs=[r["observation"] for r in base["receipts"]]
            need(all(counts(o)==(0,0) for o in base_obs),"silent certificate contradicted")
            for alt in rows[i+1:i+6]:
                need([r["observation"] for r in alt["receipts"]]==base_obs,"public output distinguished a quiet fixture")
                ia,va=alt["identity"]
                need(ia==base["identity"][0],"action sequence mismatch")
                x,m=f.silent(va);y,n=f.silent("BASE")
                need(x!=y or m!=n,"collapsed hidden pair")
                dif=alt["receipts"][-1]["snapshot"]["state"]!=base["receipts"][-1]["snapshot"]["state"]
                need(dif==(x!=y),"unexpected quiet physical difference/equality")
                physical_differences+=int(dif)
                graph_differences+=int(m!=n)
                pairs+=1
        return {**totals,"kind":"silent","runs":len(rows),"indistinguishable_pairs":pairs,
                "different_final_physical_state_pairs":physical_differences,
                "different_graph_pairs":graph_differences}
    if shard=="active":
        certificates=theorem.active_certificate()
        lo,hi=[n/d for n,d in certificates["source_event_time_bounds_ms"]]
        lower=59./120.
        graph_pairs=0
        min_g=.5
        max_g=0.
        max_receiver_voltage_delta=0.
        for i in range(0,12,4):
            block=rows[i:i+4]
            obs=block[0]["receipts"][0]["observation"]
            need(counts(obs)==(0,1),"active public counts")
            events0=block[0]["receipts"][0]["payload"]["events"][24]
            for mode,row in enumerate(block):
                rec=row["receipts"][0];pay=rec["payload"]
                need(rec["observation"]==obs and len(pay["events"][24])==1
                     and all(not e for j,e in enumerate(pay["events"]) if j!=24),"active source event roster")
                event=pay["events"][24][0]
                # The source has no input from graph. Changing only graph
                # cannot change its numerical event or physical state here.
                need(event==events0[0] and lo<w.f(event["t_ms"])<hi,"active event identity/time bound")
                expected=[{"t_ms":event["t_ms"],"source":24,"mode":mode,"increment_nS":.5}] if mode in (0,2) else []
                need(pay["arrivals"]==expected,"active route witness")
                g=[w.f(x) for x in rec["snapshot"]["state"][4]]
                need(all(x==0. for x in g[16:]),"nonreceiver GABA")
                if mode in (0,2):
                    need(all(lower<x<=.5 for x in g[:16]),"active connected conductance bound")
                    min_g=min(min_g,min(g[:16]));max_g=max(max_g,max(g[:16]))
                else:
                    need(all(x==0. for x in g[:16]),"active disconnected conductance")
            for connected in (0,2):
                for disconnected in (1,3):
                    a=block[connected]["receipts"][0]["snapshot"]["state"]
                    b=block[disconnected]["receipts"][0]["snapshot"]["state"]
                    need(a!=b,"active hidden state collapsed")
                    delta=max(abs(w.f(a[0][j])-w.f(b[0][j])) for j in range(16))
                    need(delta>0.,"active shunt voltage effect not observed")
                    max_receiver_voltage_delta=max(max_receiver_voltage_delta,delta)
                    graph_pairs+=1
        return {**totals,"kind":"active","runs":12,"indistinguishable_active_graph_pairs":graph_pairs,
                "min_connected_GABA_nS":min_g,"max_connected_GABA_nS":max_g,
                "max_receiver_voltage_difference_mV":max_receiver_voltage_delta}
    # Counts are integers. Central difference zero is exact numerator zero.
    base=rows[0]["receipts"][0]["observation"]
    need(counts(base)==(0,0),"central baseline not silent")
    matrix=[[],[]]
    for j in range(160):
        neg,pos=rows[1+2*j:3+2*j]
        n=counts(neg["receipts"][0]["observation"])
        p=counts(pos["receipts"][0]["observation"])
        need(n==p==counts(base),"nonzero central difference")
        for i in range(2):
            matrix[i].append(p[i]-n[i])
    need(all(x==0 for row in matrix for x in row),"finite sensitivity numerator")
    return {**totals,"kind":"gramian","runs":321,"central_coordinates":160,
            "count_difference_numerators":matrix,"empirical_rank":0}


def reject(fn):
    try:
        fn()
    except (ValueError,TypeError,KeyError,OverflowError) as exc:
        return str(exc)
    raise ValueError("negative control escaped")


def negative_controls(rows):
    # Use an actual active-edge witness. Rehash mutations before independent
    # verification so a stale outer digest cannot be the sole rejection.
    initial,frames,actions=spec("active",("WAIT",0))
    frame,action=frames[0],actions[0]
    previous=rt.initial_snapshot(initial)
    good=rows[0]["receipts"][0]
    def check(change):
        bad=copy.deepcopy(good)
        change(bad)
        bad["payload"]["next_without_chain"]={k:v for k,v in bad["snapshot"].items() if k!="chain"}
        bad["snapshot"]["chain"]=w.digest(bad["payload"])
        return reject(lambda:verify.audit(previous,frame,action,bad))
    results={}
    results["REHASHED_PUBLIC_COUNT"]=check(lambda r:r["observation"].update(population_spikes=0))
    results["DELETED_ACTIVE_ARRIVAL"]=check(lambda r:r["payload"]["arrivals"].clear())
    engine=rt.Runtime(initial)
    before=engine.checkpoint()
    results["STALE_FRAME"]=reject(lambda:engine.advance(f.frame(1,0),action))
    need(before==engine.checkpoint(),"stale frame mutated committed state")
    cert=theorem.certificate()
    cert["quiet"]["sensitivity_gramian_rank"]=160
    results["FORGED_GRAMIAN_RANK"]=reject(lambda:theorem.certify_result(cert))
    ia,mode=f.silent("BASE")
    ff=[f.frame(k,mode) for k in range(20)];aa=f.actions(0)
    ib=copy.deepcopy(ia);ib[0][0]=w.hx(-50.)
    results["OUTSIDE_QUIET_DOMAIN"]=reject(lambda:theorem.certify_silent_inputs(ib,ff,aa))
    bad=list(ff);ex=[()]*32;ex[0]=(w.hx(.05),)
    bad[0]=rt.Frame(0,mode,(),tuple(ex))
    results["UNSUPPORTED_EXTERNAL_PULSE"]=reject(lambda:theorem.certify_silent_inputs(ia,bad,aa))
    collapsed=copy.deepcopy(rows)
    collapsed[1]=copy.deepcopy(collapsed[0])
    collapsed[1]["identity"]=["WAIT",1]
    results["COLLAPSED_GRAPH_PAIR"]=reject(lambda:group_check("active",collapsed))
    need(len(results)==7,"negative-control roster")
    return results


def summarize(shard,rows):
    result=group_check(shard,rows)
    result["negative_controls"]=negative_controls(rows) if shard=="active" else {}
    return result


def run(args):
    parent=authenticate_parent(args.archives)
    fingerprint=custody.fingerprint(args.arch,args.install)
    cert=theorem.certificate()
    raw=compute(args.shard)
    summary=summarize(args.shard,raw)
    data=w.canonical(raw)
    need(len(data)<=MAX_RAW,"raw payload limit")
    report={"experiment":EXPERIMENT,"architecture":args.arch,"shard":args.shard,
            "head_sha":os.environ["HEAD_SHA"],"run_id":os.environ["GITHUB_RUN_ID"],
            "parent_sha256":parent,"fingerprint":fingerprint,"certificate":cert,
            "payload_sha256":w.sha(data),"summary":summary,
            "scientific_promotion_authorized":False,"scientific_promotion":"BLOCKED",
            "blind_causal_cohort":"BLOCKED"}
    args.out.mkdir()
    custody.write(args.out/"report.json",report)
    (args.out/"raw.json.gz").write_bytes(gzip.compress(data,mtime=0))
    (args.out/"install.json").write_bytes(args.install.read_bytes())
    custody.seal(args.out,{"report.json","raw.json.gz","install.json"})
    print(w.canonical({"architecture":args.arch,"shard":args.shard,"payload_sha256":report["payload_sha256"],"summary":summary}).decode(),end="")


def aggregate(args):
    parent=authenticate_parent(args.archives)
    expected={f"cneh06b-{a}-{s}" for a in ARCHES for s in f.SHARDS}
    need({p.name for p in args.profiles.iterdir()}==expected,"complete native shard roster")
    reports=[]
    for shard in f.SHARDS:
        paired=[]
        for arch in ARCHES:
            folder=args.profiles/f"cneh06b-{arch}-{shard}"
            custody.authenticate(folder,{"report.json","raw.json.gz","install.json"})
            report=custody.read(folder/"report.json")
            need(report["experiment"]==EXPERIMENT and report["architecture"]==arch
                 and report["shard"]==shard and report["head_sha"]==args.head and report["run_id"]==args.run_id
                 and report["parent_sha256"]==parent and report["scientific_promotion_authorized"] is False
                 and report["scientific_promotion"]==report["blind_causal_cohort"]=="BLOCKED","native report identity")
            custody.check_fp(report["fingerprint"],arch,args.head,args.run_id,custody.file_sha(folder/"install.json"))
            theorem.certify_result(report["certificate"])
            with gzip.open(folder/"raw.json.gz","rb") as stream:
                raw=stream.read(MAX_RAW+1)
            need(len(raw)<=MAX_RAW and w.sha(raw)==report["payload_sha256"],"raw evidence binding")
            rows=custody.json_strict(raw)
            need(w.canonical(rows)==raw,"noncanonical raw intervention evidence")
            summary=summarize(shard,rows)
            need(summary==report["summary"],"independent report mismatch")
            paired.append({"architecture":arch,"payload_sha256":w.sha(raw),"summary":summary})
            del rows,raw
        reports.append({"shard":shard,"exact":paired[0]["payload_sha256"]==paired[1]["payload_sha256"],"native":paired})
    first=[x["native"][0]["summary"] for x in reports]
    quiet=[x for x in first if x["kind"]=="silent"]
    gramian=[x for x in first if x["kind"]=="gramian"]
    active=next(x for x in first if x["kind"]=="active")
    need(sum(x["runs"] for x in quiet)==162 and sum(x["indistinguishable_pairs"] for x in quiet)==135
         and sum(x["different_graph_pairs"] for x in quiet)==54
         and sum(x["different_final_physical_state_pairs"] for x in quiet)==108
         and sum(x["runs"] for x in gramian)==963 and sum(x["central_coordinates"] for x in gramian)==480
         and active["runs"]==12 and active["indistinguishable_active_graph_pairs"]==12
         and len(active["negative_controls"])==7,"fixed intervention metrics")
    exact=sum(x["exact"] for x in reports)
    report={"experiment":EXPERIMENT,"head_sha":args.head,"run_id":args.run_id,
            "qualification":"PASS_FINITE_ONLY" if exact==len(f.SHARDS) else "FAIL",
            "observability_global_injectivity":"FAIL_COUNTEREXAMPLE",
            "finite_horizon_graph_distinguishability":"FAIL_COUNTEREXAMPLE",
            "sensitivity_gramian_rank":0,"continuous_state_nullity":160,
            "silent_action_strings_covered_analytically":3**20,
            "silent_finite_action_sequences":27,"silent_indistinguishable_pairs_per_arch":135,
            "active_indistinguishable_graph_pairs_per_arch":12,
            "central_coordinate_action_tests_per_arch":480,
            "exact_cross_cpu_shards":exact,"expected_cross_cpu_shards":len(f.SHARDS),
            "native_primary_executions":2*sum(x["runs"] for x in first),
            "native_committed_frames":2*sum(x["frames"] for x in first),
            "native_accepted_steps":sum(x["summary"]["accepted_steps"] for p in reports for x in p["native"]),
            "negative_controls_rejected":14,"certificate":theorem.certificate(),
            "active_metrics":active,"parent_sha256":parent,
            "historical_native_replay":"FAIL_PRESERVED","scientific_promotion_authorized":False,
            "scientific_promotion":"BLOCKED","blind_causal_cohort":"BLOCKED",
            "scope":"FINITE_HORIZON_NONOBSERVABILITY_NOT_INDEFINITE_OR_BIOPHYSICAL","reports":reports}
    args.out.mkdir()
    custody.write(args.out/"report.json",report)
    custody.seal(args.out,{"report.json"})
    print(w.canonical({k:v for k,v in report.items() if k!="reports"}).decode(),end="")
    return 0 if exact==len(f.SHARDS) else 2


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    sub=ap.add_subparsers(dest="command",required=True)
    r=sub.add_parser("run");a=sub.add_parser("aggregate")
    for p in (r,a):
        p.add_argument("--archives",type=Path,required=True);p.add_argument("--out",type=Path,required=True)
    r.add_argument("--shard",choices=f.SHARDS,required=True);r.add_argument("--arch",choices=ARCHES,required=True)
    r.add_argument("--install",type=Path,required=True)
    a.add_argument("--profiles",type=Path,required=True);a.add_argument("--head",required=True);a.add_argument("--run-id",required=True)
    args=ap.parse_args()
    if args.command=="run":
        run(args);return 0
    return aggregate(args)


if __name__=="__main__":
    raise SystemExit(main())
