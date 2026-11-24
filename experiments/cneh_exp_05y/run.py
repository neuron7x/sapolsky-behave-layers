"""Native architecture campaign; incomplete/mismatched evidence cannot promote."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import platform
import sys

from experiments.cneh_exp_05x import worlds as w

ARCHES=("x86_64","aarch64")
SENTINELS=(0,250,500,750)
COUNTS=("synaptic_stops","external_impulses","receiver_arrivals","forcing_stops",
        "accepted_steps","trials","rejected_trials","rhs_evaluations","root_certificates")


def file_sha(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f,"sha256").hexdigest()


def json_strict(raw):
    def unique(pairs):
        obj={}
        for k,v in pairs:
            w.need(k not in obj,"duplicate JSON key")
            obj[k]=v
        return obj
    def finite(s):
        v=float(s)
        w.need(math.isfinite(v),"nonfinite JSON number")
        return v
    def reject(s):
        raise ValueError("invalid JSON constant "+s)
    return json.loads(raw,object_pairs_hook=unique,parse_float=finite,parse_constant=reject)


def write(path,value):
    with Path(path).open("xb") as f:
        f.write(w.canonical(value))


def read(path):
    return json_strict(Path(path).read_bytes())


def seal(folder,names):
    payload="".join(file_sha(folder/k)+"  "+k+"\n" for k in sorted(names))
    with (folder/"SHA256SUMS").open("x") as f:
        f.write(payload)


def authenticate(folder,names):
    w.need(folder.is_dir() and {p.name for p in folder.iterdir()}==set(names)|{"SHA256SUMS"}
           and all(p.is_file() and not p.is_symlink() for p in folder.iterdir()),"artifact roster")
    actual="".join(file_sha(folder/k)+"  "+k+"\n" for k in sorted(names))
    w.need((folder/"SHA256SUMS").read_text()==actual,"artifact manifest mismatch")


def inputs(path,expected):
    raw=path.read_bytes()
    w.need(w.sha(raw)==expected,"pre-execution manifest SHA256 mismatch")
    value=json_strict(raw)
    w.need(w.canonical(value)==raw,"noncanonical manifest")
    w.validate_manifest(value)
    return value["worlds"]


def ids(shard):
    w.need(type(shard) is int and 0<=shard<w.SHARDS,"shard id")
    return tuple(range(shard*w.PER_SHARD,(shard+1)*w.PER_SHARD))


def elf_machine(path):
    with Path(path).open("rb") as f:
        header=f.read(20)
    w.need(len(header)==20 and header[:4]==b"\x7fELF" and header[4]==2 and header[5]==1,"non-ELF64 native binary")
    return int.from_bytes(header[18:20],"little")


def fingerprint(arch,install):
    import numpy as np
    import scipy
    from scipy.integrate import RK45
    import scipy.linalg._fblas as fblas
    import scipy._lib._ccallback_c as callback
    actual=platform.machine()
    w.need(arch in ARCHES and actual==os.uname().machine==arch and platform.system()=="Linux"
           and os.environ.get("RUNNER_ARCH")==("X64" if arch=="x86_64" else "ARM64")
           and os.environ.get("RUNNER_ENVIRONMENT")=="github-hosted","native hosted architecture not established")
    w.need(sys.version_info[:3]==(3,12,16) and np.__version__=="2.4.1" and scipy.__version__=="1.17.1","dependency contract")
    threads={k:os.environ.get(k) for k in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS")}
    w.need(set(threads.values())=={"1"} and not os.environ.get("NPY_DISABLE_CPU_FEATURES"),"dispatch/thread drift")
    machine=62 if arch=="x86_64" else 183
    paths={str(Path(sys.executable).resolve()),str(Path(np._core._multiarray_umath.__file__).resolve()),
           str(Path(fblas.__file__).resolve()),str(Path(callback.__file__).resolve())}
    maps=Path("/proc/self/maps").read_text()
    for line in maps.splitlines():
        fields=line.split(maxsplit=5)
        if len(fields)==6 and fields[5].startswith("/") and ".so" in Path(fields[5]).name:
            path=Path(fields[5])
            w.need(path.is_file(),"unreadable mapped library")
            paths.add(str(path.resolve()))
    binaries={}
    for path in sorted(paths):
        w.need(elf_machine(path)==machine,"foreign executable/library architecture")
        binaries[path]=file_sha(path)
    cpu=Path("/proc/cpuinfo").read_text()
    w.need(bool(cpu.strip()),"CPU provenance missing")
    core=np._core._multiarray_umath
    from experiments.cneh_exp_05y import portable
    build=read(Path("/tmp/cneh05y/build.json"))
    w.need(build["arch"]==arch and build["library_sha256"]==file_sha(portable.LIBRARY)
           and build["kernel_source_sha256"]==file_sha(Path("experiments/cneh_exp_05y/kernel.c"))
           and build["forbidden_fma"]==build["forbidden_transcendental_imports"]==0,"portable build identity")
    return {"build":build,"software_version":portable.LIB.software_version().decode(),"arch":arch,"elf_machine":machine,"runner_arch":os.environ["RUNNER_ARCH"],
            "runner_environment":os.environ["RUNNER_ENVIRONMENT"],"cpuinfo":cpu.split("\n\n",1)[0],
            "platform":platform.platform(),"python":sys.version,"numpy":np.__version__,"scipy":scipy.__version__,
            "image_os":os.environ.get("ImageOS"),"image_version":os.environ.get("ImageVersion"),
            "thread_environment":threads,"numpy_features":{k:bool(v) for k,v in sorted(core.__cpu_features__.items())},
            "numpy_dispatch":list(core.__cpu_dispatch__),"numpy_baseline":list(core.__cpu_baseline__),
            "binaries":binaries,"install_sha256":file_sha(install),
            "head_sha":os.environ.get("HEAD_SHA"),"run_id":os.environ.get("GITHUB_RUN_ID"),
            "merge_sha":os.environ.get("GITHUB_SHA"),"attempt":os.environ.get("GITHUB_RUN_ATTEMPT"),
            "exp_probe_hex":[math.exp(x).hex() for x in (-20.,-2.,-.1,0.,.1,2.,20.)],
            "rk45_tableau_sha256":w.digest([RK45.A.tolist(),RK45.B.tolist(),RK45.C.tolist(),RK45.E.tolist(),RK45.P.tolist()])}


def preflight(args,worlds):
    from experiments.cneh_exp_05y import portable as trace
    from experiments.cneh_exp_05x import verify,probes
    fp=fingerprint(args.arch,args.install)
    result=trace.simulate(worlds[0])
    audit=verify.audit(worlds[0],result)
    plain=trace.simulate(worlds[0],False)
    w.need(plain["physical_sha256"]==result["physical_sha256"] and w.canonical(plain["physical"])==w.canonical(result["physical"]),
           "passive instrumentation changed physical output")
    report={"arch":args.arch,"manifest_sha256":args.manifest_sha,"fingerprint":fp,
            "audit":audit,"physical_sha256":result["physical_sha256"],"trace_sha256":result["trace_sha256"],
            "passive_parity":True,"mutations":probes.boundary_attacks(worlds[0],result),
            "arithmetic":trace.probes()}
    args.out.mkdir()
    write(args.out/"report.json",report)
    seal(args.out,{"report.json"})
    print(w.canonical({k:v for k,v in report.items() if k!="fingerprint"}).decode(),end="")


def execute(args,worlds):
    from experiments.cneh_exp_05y import portable as trace
    from experiments.cneh_exp_05x import verify
    fp=fingerprint(args.arch,args.install)
    args.out.mkdir()
    complete=0
    failed=[]
    with (args.out/"episodes.jsonl.gz").open("xb") as raw:
        with gzip.GzipFile(fileobj=raw,mode="wb",filename="",mtime=0) as out:
            for i in ids(args.shard):
                world=worlds[i]
                row={"id":i,"input_sha256":w.digest(world)}
                try:
                    result=trace.simulate(world)
                    audit=verify.audit(world,result)
                    if i in SENTINELS:
                        plain=trace.simulate(world,False)
                        w.need(w.canonical(plain["physical"])==w.canonical(result["physical"]),"passive instrumentation changed output")
                    row.update(status="COMPLETE",result=result,audit=audit,
                               passive_parity=True if i in SENTINELS else None)
                    complete+=1
                except Exception as exc:
                    row.update(status="FAIL",error_type=type(exc).__name__,error=str(exc))
                    failed.append({"id":i,"error_type":type(exc).__name__,"error":str(exc)})
                out.write(w.canonical(row))
                print(w.canonical({k:v for k,v in row.items() if k not in ("result","audit")}).decode(),end="",flush=True)
    receipt={"arch":args.arch,"shard":args.shard,"manifest_sha256":args.manifest_sha,
             "ids":list(ids(args.shard)),"complete":complete,"failures":failed,"fingerprint":fp,
             "episode_file_sha256":file_sha(args.out/"episodes.jsonl.gz")}
    write(args.out/"receipt.json",receipt)


def rows(folder,receipt):
    p=folder/"episodes.jsonl.gz"
    w.need(file_sha(p)==receipt["episode_file_sha256"],"episode file hash")
    with gzip.open(p,"rb") as f:
        for i in ids(receipt["shard"]):
            line=f.readline()
            w.need(bool(line),"missing episode")
            row=json_strict(line)
            w.need(w.canonical(row)==line and type(row["id"]) is int and row["id"]==i,"episode identity/canonical encoding")
            yield row
        w.need(not f.read(1),"extra episode")


def repeat(args,worlds):
    from experiments.cneh_exp_05y import portable as trace
    from experiments.cneh_exp_05x import verify
    fp=fingerprint(args.arch,args.install)
    receipt=read(args.out/"receipt.json")
    w.need((receipt["arch"],receipt["shard"],receipt["manifest_sha256"])==(args.arch,args.shard,args.manifest_sha),"repeat identity")
    checks=[]
    for row in rows(args.out,receipt):
        i=row["id"]
        if i not in SENTINELS:
            continue
        try:
            result=trace.simulate(worlds[i])
            verify.audit(worlds[i],result)
            equal=row["status"]=="COMPLETE" and w.canonical(row["result"])==w.canonical(result)
            checks.append({"id":i,"status":"PASS" if equal else "FAIL","physical_sha256":result["physical_sha256"],
                           "trace_sha256":result["trace_sha256"]})
        except Exception as exc:
            checks.append({"id":i,"status":"FAIL","error_type":type(exc).__name__,"error":str(exc)})
    w.need([x["id"] for x in checks]==[i for i in ids(args.shard) if i in SENTINELS],"sentinel repeat roster")
    write(args.out/"repeat.json",{"arch":args.arch,"shard":args.shard,"checks":checks,"fingerprint":fp})
    (args.out/"install.json").write_bytes(args.install.read_bytes())
    seal(args.out,{"receipt.json","episodes.jsonl.gz","repeat.json","install.json"})


def check_fp(fp,arch,head,run,install_hash):
    w.need(fp["arch"]==arch and fp["elf_machine"]==(62 if arch=="x86_64" else 183)
           and fp["runner_arch"]==("X64" if arch=="x86_64" else "ARM64")
           and fp["runner_environment"]=="github-hosted" and fp["head_sha"]==head and fp["run_id"]==run
           and fp["install_sha256"]==install_hash and fp["numpy"]=="2.4.1" and fp["scipy"]=="1.17.1"
           and bool(fp["binaries"]) and all(type(s) is str and len(s)==64 for s in fp["binaries"].values()),
           "native provenance binding")
    build=fp["build"]
    w.need(fp["software_version"]=="4.2.1" and build["arch"]==arch and build["forbidden_fma"]==0
           and build["forbidden_transcendental_imports"]==0 and "-ffp-contract=off" in build["flags"]
           and build["kernel_source_sha256"]==file_sha(Path("experiments/cneh_exp_05y/kernel.c")),"software arithmetic provenance")


def pair(args,worlds):
    from experiments.cneh_exp_05x import verify
    folders=[args.profiles/f"cneh05y-{a}-{args.shard}" for a in ARCHES]
    receipts=[];repeats=[]
    for arch,folder in zip(ARCHES,folders,strict=True):
        authenticate(folder,{"receipt.json","episodes.jsonl.gz","repeat.json","install.json"})
        rec=read(folder/"receipt.json");rep=read(folder/"repeat.json")
        w.need((rec["arch"],rec["shard"],rec["manifest_sha256"])==(arch,args.shard,args.manifest_sha)
               and rec["ids"]==list(ids(args.shard)) and (rep["arch"],rep["shard"])==(arch,args.shard),"shard identity")
        for fp in (rec["fingerprint"],rep["fingerprint"]):
            check_fp(fp,arch,args.head,args.run_id,file_sha(folder/"install.json"))
        w.need([x["id"] for x in rep["checks"]]==[i for i in ids(args.shard) if i in SENTINELS],"sentinel roster")
        receipts.append(rec);repeats.append(rep["checks"])
    reports=[]
    for a,b in zip(rows(folders[0],receipts[0]),rows(folders[1],receipts[1]),strict=True):
        i=a["id"];world=worlds[i]
        w.need(b["id"]==i and a["input_sha256"]==b["input_sha256"]==w.digest(world),"paired world identity")
        audits={}
        failures={}
        for arch,row in zip(ARCHES,(a,b),strict=True):
            w.need(row["status"] in ("COMPLETE","FAIL"),"episode status")
            if row["status"]=="COMPLETE":
                checked=verify.audit(world,row["result"])
                claimed=row["audit"]
                w.need(claimed["status"]==checked["status"]=="PASS" and all(claimed[k]==checked[k] for k in COUNTS)
                       and 0<=claimed["max_conductance_residual_nS"]<=1e-10,"independent boundary recomputation")
                w.need(row["passive_parity"] is (True if i in SENTINELS else None),"sentinel passive parity")
                audits[arch]=checked
            else:
                failures[arch]={"error_type":row["error_type"],"error":row["error"]}
        metrics=verify.compare(a["result"],b["result"]) if not failures else None
        reports.append({"id":i,"stratum":world["stratum"],"audits":audits,"failures":failures,"comparison":metrics})
    for arch,rec in zip(ARCHES,receipts,strict=True):
        observed=[{"id":x["id"],**x["failures"][arch]} for x in reports if arch in x["failures"]]
        w.need(rec["failures"]==observed and rec["complete"]==len(reports)-len(observed),"receipt failure roster")
    result={"shard":args.shard,"manifest_sha256":args.manifest_sha,"head_sha":args.head,"run_id":args.run_id,
            "reports":reports,"sentinel_repeats":dict(zip(ARCHES,repeats,strict=True)),
            "producer_fingerprints":{r["arch"]:r["fingerprint"] for r in receipts},
            "scientific_promotion_authorized":False,"scientific_promotion":"BLOCKED"}
    args.out.mkdir();write(args.out/"report.json",result);seal(args.out,{"report.json"})
    print(w.canonical({"shard":args.shard,"compared":sum(x["comparison"] is not None for x in reports),
                       "exact":sum(x["comparison"] is not None and x["comparison"]["exact"] for x in reports)}).decode(),end="")


def aggregate(args):
    all_reports=[];sentinels={a:[] for a in ARCHES};missing=[];provenance=[]
    for shard in range(w.SHARDS):
        folder=args.profiles/f"cneh05y-pair-{shard}"
        try:
            authenticate(folder,{"report.json"})
            value=read(folder/"report.json")
            w.need((value["shard"],value["manifest_sha256"],value["head_sha"],value["run_id"])==
                   (shard,args.manifest_sha,args.head,args.run_id),"pair identity")
            w.need(tuple(x["id"] for x in value["reports"])==ids(shard),"pair episode roster")
            w.need(set(value["sentinel_repeats"])==set(ARCHES),"pair repeat architecture roster")
            for arch in ARCHES:
                w.need([x["id"] for x in value["sentinel_repeats"][arch]]==[i for i in ids(shard) if i in SENTINELS],"pair sentinel roster")
                sentinels[arch].extend(value["sentinel_repeats"][arch])
            all_reports.extend(value["reports"])
            provenance.append(value["producer_fingerprints"])
        except (ValueError,TypeError,KeyError,OSError) as exc:
            missing.append({"shard":shard,"reason":str(exc)})
    complete={arch:sum(arch in r["audits"] for r in all_reports) for arch in ARCHES}
    compared=[r for r in all_reports if r["comparison"] is not None]
    exact=sum(r["comparison"]["exact"] for r in compared)
    close=sum(r["comparison"]["numerical_close"] for r in compared)
    sentinel_ok=all([s["id"] for s in sentinels[a]]==list(SENTINELS) and all(s["status"]=="PASS" for s in sentinels[a]) for a in ARCHES)
    preflight={}
    for arch in ARCHES:
        try:
            folder=args.profiles/f"cneh05y-preflight-{arch}"
            authenticate(folder,{"report.json"})
            value=read(folder/"report.json")
            fp=value["fingerprint"]
            check_fp(fp,arch,args.head,args.run_id,fp["install_sha256"])
            w.need(value["arch"]==arch and value["manifest_sha256"]==args.manifest_sha
                   and value["passive_parity"] is True and value["audit"]["status"]=="PASS"
                   and len(value["mutations"])==5 and value["arithmetic"]["exp_independent_fixtures"]==2049,"preflight scope")
            preflight[arch]=value
        except (ValueError,TypeError,KeyError,OSError) as exc:
            missing.append({"preflight":arch,"reason":str(exc)})
    reference=[]
    for i in range(8):
        try:
            folder=args.profiles/f"cneh05y-reference-{i}"
            authenticate(folder,{"report.json"})
            value=read(folder/"report.json")
            w.need(value["index"]==i and value["head_sha"]==args.head and value["run_id"]==args.run_id
                   and len(value["comparisons"])==2 and value["scientific_promotion_authorized"] is False,"reference identity")
            reference.append(value)
        except (ValueError,TypeError,KeyError,OSError) as exc:
            missing.append({"reference":i,"reason":str(exc)})
    reference_ok=len(reference)==8 and all(x["status"]=="PASS_FINITE" for x in reference)
    full=not missing and reference_ok and len(preflight)==2 and len(all_reports)==w.N and complete==dict.fromkeys(ARCHES,w.N) and len(compared)==w.N and sentinel_ok
    observed_exact_fail=any(not r["comparison"]["exact"] for r in compared)
    gate="FAIL" if observed_exact_fail else "PASS_FINITE_ONLY" if full and exact==w.N else "BLOCKED"
    counts={a:{k:sum(r["audits"][a][k] for r in all_reports if a in r["audits"]) for k in COUNTS} for a in ARCHES}
    result={"experiment":"CNEH-EXP-05Y","head_sha":args.head,"manifest_sha256":args.manifest_sha,"run_id":args.run_id,
            "scope":"PUBLIC_NUMERICAL_OOD_STRESS_ONLY","expected_unique_worlds":1000,"expected_native_episodes":2000,
            "complete_by_arch":complete,"paired_comparisons":len(compared),"exact_pairs":exact,"numerically_close_pairs":close,
            "exact_step_schedules":sum(r["comparison"]["step_schedule_exact"] for r in compared),
            "exact_event_tapes":sum(r["comparison"]["event_tape_exact"] for r in compared),
            "exact_raw_samples":sum(r["comparison"]["raw_samples_exact"] for r in compared),
            "cross_cpu_deterministic_replay":gate,"complete_evidence":full,"missing_or_invalid_shards":missing,
            "sentinel_repeat_pass":sentinel_ok,"counts_by_arch":counts,
            "max_event_time_error_ms":max((r["comparison"]["max_event_time_error_ms"] for r in compared if r["comparison"]["max_event_time_error_ms"] is not None),default=None),
            "max_full_errors":{k:max((r["comparison"]["max_full_errors"][k] for r in compared),default=None) for k in ("V","w","g_ampa","g_nmda","g_gabaa")},
            "scientific_promotion_authorized":False,"scientific_promotion":"BLOCKED","blind_causal_cohort":"BLOCKED",
            "historical_native_replay":"FAIL_PRESERVED","historical_fixed_step_gate":"FAIL_PRESERVED",
            "historical_cross_cpu_replay":"FAIL_PRESERVED","reference_qualified":sum(x["status"]=="PASS_FINITE" for x in reference),
            "reference_reports":reference,
            "reports":all_reports,"sentinel_repeats":sentinels,"provenance":provenance,"preflight":preflight}
    args.out.mkdir();write(args.out/"report.json",result);seal(args.out,{"report.json"})
    print(w.canonical({k:v for k,v in result.items() if k not in ("reports","provenance","sentinel_repeats","preflight")}).decode(),end="")
    return 0 if gate=="PASS_FINITE_ONLY" else 2


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    s=ap.add_subparsers(dest="command",required=True)
    m=s.add_parser("manifest");m.add_argument("--out",type=Path,required=True)
    for name in ("preflight","run","repeat","pair","aggregate"):
        p=s.add_parser(name)
        p.add_argument("--manifest-sha",required=True)
        p.add_argument("--out",type=Path,required=True)
        if name!="aggregate":
            p.add_argument("--manifest",type=Path,required=True)
        if name in ("preflight","run","repeat"):
            p.add_argument("--arch",choices=ARCHES,required=True);p.add_argument("--install",type=Path,required=True)
        if name in ("run","repeat","pair"):
            p.add_argument("--shard",type=int,required=True)
        if name in ("pair","aggregate"):
            p.add_argument("--profiles",type=Path,required=True);p.add_argument("--head",required=True);p.add_argument("--run-id",required=True)
    args=ap.parse_args()
    if args.command=="manifest":
        write(args.out,w.manifest());print(file_sha(args.out));return 0
    if args.command=="aggregate":
        return aggregate(args)
    worlds=inputs(args.manifest,args.manifest_sha)
    if args.command=="preflight":preflight(args,worlds)
    elif args.command=="run":execute(args,worlds)
    elif args.command=="repeat":repeat(args,worlds)
    else:pair(args,worlds)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
