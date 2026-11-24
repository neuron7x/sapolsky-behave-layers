"""Sealed hybrid qualification: no blind cohort or positive authority."""
from __future__ import annotations

import argparse
import copy
import gzip
import io
from pathlib import Path

from experiments.cneh_exp_05h import run as history
from experiments.cneh_exp_05j import integrator as candidate
from experiments.cneh_exp_05j import verify as verifier
from experiments.cneh_exp_05v import audit as evidence
from experiments.cneh_exp_05v import oracle

EXPERIMENT="CNEH-EXP-05J"
H_AGGREGATE=(14898206091,"55cdc7928aba9162c51247dc5e53791e70b5ab3dad59a34d13c3b975315ea3cd")
SHARDS=(
    (14897588018,"f4675a91cfb1993842223871b0c8c55c91e93b2e3aba6ae5f423a53694779dd7"),
    (14897882365,"a9086766f6643dfb139d2d6f5bc7b6c393fb78affd7a720f805d30a6dd3efc72"),
    (14898111151,"001492b56be07f2feab0b86c416437cd19d3ae7d37b74e13f491eb45ddbc5e72"),
    (14897329874,"6119fbcecb06081e206a76f23b80f79e9eaf4264dd7a379982f809bf73c8f60e"),
    (14898275795,"9c07ce0a1fdaeef7a61decda220084b00562151e556abb93d71144dbff818660"),
    (14896844936,"a1990a5b41982ec2e39577a4b1f03ba6361b33ae5b920e7f9996359d518e2e6d"),
    (14897598019,"90cbae6f25e88fbaddf5c63ed7c4233d7e512946da1114a8baec3e8322820145"),
    (14898290682,"b766e6b69ea5c1f1c262f625caaee9f476d4d599e22ef64d7378f9f86267eed1"),
)
MAX_RAW=128*1024*1024


def need(c,msg):
    if not c:
        raise ValueError(msg)


def canonical(x):
    return oracle.canonical(x)


def read(root,anchor,names):
    aid,digest=anchor
    path=root/f"{aid}.zip"
    need(path.is_file() and not path.is_symlink(),"reference artifact path")
    return evidence.read_zip(path.read_bytes(),digest,names)


def unpack(raw):
    with gzip.GzipFile(fileobj=io.BytesIO(raw)) as stream:
        data=stream.read(MAX_RAW+1)
    need(len(data)<=MAX_RAW,"decompressed evidence limit")
    return evidence.strict_json(data)


def inputs(root,index):
    aggregate=evidence.strict_json(read(root,H_AGGREGATE,{"report.json","SHA256SUMS"})["report.json"])
    need(aggregate["continuous_time_numerical_gate"]=="FAIL" and aggregate["reference_qualified"]==8
         and aggregate["native_qualified"]==aggregate["finest_qualified"]==0
         and aggregate["scientific_promotion_authorized"] is False
         and len(aggregate["reports"])==8,"historical negative gate")
    files=read(root,SHARDS[index],{"report.json","raw.json.gz","SHA256SUMS"})
    report=evidence.strict_json(files["report.json"])
    value=unpack(files["raw.json.gz"])
    need(value["report"]==report==aggregate["reports"][index]
         and report["index"]==index and report["reference_status"]=="QUALIFIED_FINITE","reference binding")
    ep,archived,bits,tape=history.load(root,index)
    need((ep["seed"],ep["arm"])==history.ROSTER[index]==(report["seed"],report["arm"]),"input roster")
    reference={k:value[k] for k in ("loose","tight")}
    for r in reference.values():
        a=verifier.sample_array(r["states"])
        need((a[0]==archived[0]).all(),"reference initial state")
    return ep,archived[0],tape,reference


def rejected(action):
    try:
        action()
    except (ValueError,TypeError,KeyError,OverflowError) as exc:
        return str(exc)
    raise ValueError("adversarial event mutation escaped")


def attacks(result,reference,initial,tape,arm):
    profile=result["profile"]
    event=next(e for events in result["events"] for e in events)
    out={}
    for label in ("RESET_V","ADAPTATION_JUMP","SHIFTED_TIME","CORRUPT_BRACKET","CORRUPT_POLYNOMIAL"):
        bad=copy.deepcopy(event)
        if label=="RESET_V":
            bad["post"][0]=(-57.).hex()
        elif label=="ADAPTATION_JUMP":
            bad["post"][1]=(float.fromhex(bad["post"][1])+1.).hex()
        elif label=="SHIFTED_TIME":
            bad["t_ms"]=(float.fromhex(bad["t_ms"])+1e-4).hex()
        elif label=="CORRUPT_BRACKET":
            bad["x_hi"]=[1,1]
        else:
            bad["Q"][0][0]=(float.fromhex(bad["Q"][0][0])+1e5).hex()
        out[label]=rejected(lambda:verifier.verify_event(bad,profile))
    rt=reference["tight"]
    times=verifier.event_times(result)
    i=next(i for i,s in enumerate(times) if s)
    missing=copy.deepcopy(times);missing[i].pop()
    extra=copy.deepcopy(times)
    extra[i].append((extra[i][-1]+51.2)/2.)
    for label,bad in (("MISSING_EVENT",missing),("EXTRA_EVENT",extra)):
        test=verifier.comparison(result["samples"],bad,rt["states"],rt["events"])
        need(not test["gates"]["SPIKE_COUNT"],"event roster attack escaped")
        out[label]="SPIKE_COUNT"
    mutated=copy.copy(result)
    if result["arrivals"]:
        mutated["arrivals"]=[{**result["arrivals"][0],"mode":3}]+result["arrivals"][1:]
    else:
        mutated["arrivals"]=[{"source":24,"mode":3,"t_ms":(1.).hex(),"increment_nS":.5}]
    out["SOURCE_ROUTE"]=rejected(lambda:verifier.verify_result(mutated,initial,tape,arm))
    samples=copy.deepcopy(result["samples"])
    samples[1][0][0]+=0.01
    test=verifier.comparison(samples,times,rt["states"],rt["events"])
    need(not test["gates"]["V"],"unsmoothed V mutation escaped")
    out["RAW_V_SAMPLE"]="V"
    samples=copy.deepcopy(result["samples"])
    samples[1][4][0]+=0.01
    mutated=copy.copy(result);mutated["samples"]=samples
    out["RAW_GABA_SAMPLE"]=rejected(lambda:verifier.verify_result(mutated,initial,tape,arm))
    need(len(out)==10,"attack roster")
    return out


def report_for(ep,initial,tape,reference,results,index):
    audit=verifier.verify_pair(results,reference,initial,tape,ep["arm"])
    negative=attacks(results[1],reference,initial,tape,ep["arm"])
    return {"experiment":EXPERIMENT,"scientific_promotion_authorized":False,
            "scientific_promotion":"BLOCKED","historical_native_replay":"FAIL_PRESERVED",
            "historical_fixed_step_gate":"FAIL_PRESERVED",
            "scope":"FINITE_EVENT_RESOLVED_ENGINEERING_PANEL_ONLY",
            "index":index,"seed":ep["seed"],"arm":ep["arm"],"audit":audit,"attacks_rejected":negative}


def run(root,index):
    ep,initial,tape,reference=inputs(root,index)
    results=[candidate.run(initial,tape,ep["arm"],p) for p in ("LOOSE","TIGHT")]
    report=report_for(ep,initial,tape,reference,results,index)
    return {"report":report,"candidates":results}


def aggregate(profiles,root):
    need({p.name for p in profiles.iterdir()}=={f"cneh-exp-05j-{i}" for i in range(8)},"full shard roster")
    reports=[]
    for index in range(8):
        folder=profiles/f"cneh-exp-05j-{index}"
        names={"report.json","raw.json.gz","SHA256SUMS"}
        need({p.name for p in folder.iterdir()}==names and all(p.is_file() and not p.is_symlink() for p in folder.iterdir()),"artifact roster")
        raw={k:(folder/k).read_bytes() for k in names}
        manifest="".join(evidence.sha(raw[k])+"  "+k+"\n" for k in sorted(names-{"SHA256SUMS"})).encode()
        need(raw["SHA256SUMS"]==manifest,"shard manifest")
        stored=evidence.strict_json(raw["report.json"])
        payload=unpack(raw["raw.json.gz"])
        need(set(payload)=={"report","candidates"} and payload["report"]==stored,"shard payload binding")
        ep,initial,tape,reference=inputs(root,index)
        fresh=report_for(ep,initial,tape,reference,payload["candidates"],index)
        need(canonical(fresh)==raw["report.json"],"independent report recomputation mismatch")
        reports.append(fresh)
    comparisons=[x for r in reports for x in r["audit"]["comparisons"]]
    checks=[x for r in reports for x in r["audit"]["independent_checks"]]
    passed=sum(x["audit"]["status"]=="PASS_FINITE" for x in reports)
    result={"experiment":EXPERIMENT,"scientific_promotion_authorized":False,"scientific_promotion":"BLOCKED",
            "blind_causal_cohort":"BLOCKED","historical_native_replay":"FAIL_PRESERVED",
            "historical_fixed_step_gate":"FAIL_PRESERVED",
            "scope":"FINITE_REFERENCE_RELATIVE_EVENT_BACKEND_ONLY","episode_count":8,"qualified_episodes":passed,
            "candidate_profiles":16,"independent_comparisons":len(comparisons),
            "qualified_comparisons":sum(x["status"]=="PASS_FINITE" for x in comparisons),
            "event_certificates":sum(x["root_certificates"] for x in checks),
            "routed_arrivals":sum(x["routed_arrivals"] for x in checks),
            "max_root_width_ms":max(x["max_root_width_ms"] for x in checks),
            "max_root_residual_mV":max(x["max_root_residual_mV"] for x in checks),
            "max_analytic_conductance_error_nS":max(max(x["max_sample_conductance_residual_nS"],x["max_event_conductance_residual_nS"]) for x in checks),
            "max_event_time_error_ms":max((x["max_event_time_error_ms"] for x in comparisons if x["max_event_time_error_ms"] is not None),default=None),
            "max_full_errors":{k:max(x["max_full_errors"][k] for x in comparisons) for k in verifier.STATE_FIELDS},
            "attacks_rejected":sum(len(r["attacks_rejected"]) for r in reports),
            "qualification":"PASS_FINITE_ONLY" if passed==8 else "FAIL",
            "unqualified":["cross_domain_exact_replay","seed_initialization_provenance","broader_parameter_domain",
                           "biophysical_validity","multiscale_scientific_coherence","statistical_generalization","closed_loop_causal_efficacy"],
            "reports":reports}
    need(len(comparisons)==40 and len(checks)==16 and result["attacks_rejected"]==80,"aggregate roster")
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    sub=ap.add_subparsers(dest="command",required=True)
    r=sub.add_parser("run")
    r.add_argument("--index",type=int,choices=range(8),required=True)
    a=sub.add_parser("aggregate")
    a.add_argument("--profiles",type=Path,required=True)
    for p in (r,a):
        p.add_argument("--archives",type=Path,required=True)
        p.add_argument("--out",type=Path,required=True)
        p.add_argument("--verify",action="store_true")
    args=ap.parse_args()
    if args.command=="run":
        result=run(args.archives,args.index)
        files={"report.json":canonical(result["report"]),"raw.json.gz":gzip.compress(canonical(result),mtime=0)}
    else:
        result=aggregate(args.profiles,args.archives)
        files={"report.json":canonical(result)}
    files["SHA256SUMS"]="".join(evidence.sha(files[k])+"  "+k+"\n" for k in sorted(files)).encode()
    if args.verify:
        need({p.name for p in args.out.iterdir()}==set(files),"replay artifact roster")
        for k,v in files.items():
            need((args.out/k).read_bytes()==v,"exact evidence replay mismatch "+k)
    else:
        args.out.mkdir()
        for k,v in files.items():
            (args.out/k).write_bytes(v)
    output=result["report"] if args.command=="run" else {k:v for k,v in result.items() if k!="reports"}
    print(canonical(output).decode(),end="")
    return 2 if args.command=="aggregate" and result["qualification"]!="PASS_FINITE_ONLY" else 0


if __name__=="__main__":
    raise SystemExit(main())
