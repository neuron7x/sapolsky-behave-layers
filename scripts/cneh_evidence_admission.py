"""Independent negative-evidence admission. No positive scientific issuer."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import random
import re
import shutil
import stat
import sys
import tempfile
import zipfile

from scripts import cneh_promotion_gate as promotion
from scripts.cneh_history_guard import git, require_commit

ROOT=Path(__file__).resolve().parents[1]
BASE="8cd266c51d9b0ae495e42557dd5da2d5a443dbbd"
FLAG="scientific_promotion_authorized"
CORE=("episodes.json.gz","implementation.json","preregistration.md","verdict.json","worlds.json")
SOURCE_COMMIT="c1de425ce4ece362e7f2feb2d9f24da5d3231014"
HEX=re.compile(r"[0-9a-f]{64}\Z")
MAX_FILE=512*1024*1024
MAX_EPISODE=64*1024*1024
MODES=((1,0),(0,1),(1,1),(0,0))
DECAY=math.exp(-.1/6.)
WINDOWS=((650,750),(1450,1550),(2250,2350))
SEQUENCES=((1,3,2),(2,3,0),(3,1,2),(3,2,0))
ARCHIVES={
    "CNEH-EXP-04G":(14889488512,"03a5731775b7def8a9f09a9aab806737253a5431ea5e08ea10360ec1cf58b103","cneh04g"),
    "CNEH-EXP-05":(14890028886,"db78569d633a4fd1ae5649ab02e53a86b48e97f0317b45a849a56cd73e993ea8","cneh05"),
}


class EvidenceViolation(ValueError):
    def __init__(self,code,detail):
        super().__init__(f"{code}: {detail}")
        self.code=code


def need(condition,code,detail):
    if not condition:
        raise EvidenceViolation(code,detail)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return (json.dumps(value,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()


def equal(x,y):
    return canonical(x)==canonical(y)


def integer(x):
    return type(x) is int


def exact_int(x,n):
    return integer(x) and x==n


def hex_digest(x):
    return type(x) is str and HEX.fullmatch(x) is not None


def read_json(raw,code):
    try:
        return promotion.strict_json(raw)
    except (ValueError,TypeError,UnicodeError,RecursionError) as exc:
        raise EvidenceViolation(code,str(exc)) from exc


def regular(path,code="ROSTER"):
    try:
        info=path.lstat()
    except OSError as exc:
        raise EvidenceViolation(code,str(exc)) from exc
    need(stat.S_ISREG(info.st_mode) and info.st_nlink==1,code,"nonregular or aliased member: "+path.name)
    need(info.st_size<=MAX_FILE,code,"oversize member: "+path.name)
    return info


def file_hash(path):
    before=regular(path)
    try:
        fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd,"rb") as stream:
            info=os.fstat(stream.fileno())
            need((info.st_dev,info.st_ino,info.st_size)==(before.st_dev,before.st_ino,before.st_size),"ROSTER","member changed during open")
            digest=hashlib.file_digest(stream,"sha256").hexdigest()
            after=os.fstat(stream.fileno())
            need((after.st_size,after.st_mtime_ns,after.st_ctime_ns)==(info.st_size,info.st_mtime_ns,info.st_ctime_ns),"MANIFEST","member changed during hash")
    except OSError as exc:
        raise EvidenceViolation("ROSTER",str(exc)) from exc
    final=regular(path)
    need((final.st_dev,final.st_ino,final.st_size,final.st_mtime_ns,final.st_ctime_ns)==
         (before.st_dev,before.st_ino,before.st_size,before.st_mtime_ns,before.st_ctime_ns),"MANIFEST","member replaced or changed")
    return digest


def snapshot(root,names):
    need(not root.is_symlink() and root.is_dir(),"ROSTER","invalid evidence directory")
    wanted=set(names)|{"SHA256SUMS"}
    need({p.name for p in root.iterdir()}==wanted,"ROSTER","evidence member roster")
    for name in sorted(wanted):
        regular(root/name)
    hashes={name:file_hash(root/name) for name in sorted(names)}
    manifest="".join(f"{hashes[k]}  {k}\n" for k in sorted(hashes)).encode("ascii")
    need((root/"SHA256SUMS").read_bytes()==manifest,"MANIFEST","exact manifest mismatch")
    return {"files":hashes,"manifest_sha256":sha(manifest)}


def require_same_snapshot(before,after):
    need(isinstance(before,dict) and isinstance(after,dict) and equal(before,after),"REPLAY","pre/post replay bytes differ")


def schedule(seed,start):
    rng=random.Random(seed)
    return [[rng.randint(lo,hi),m] for (lo,hi),m in zip(WINDOWS,SEQUENCES[(seed-start)%4],strict=True)]


def trusted_contract(experiment,repo=ROOT):
    need(experiment in ARCHIVES,"LINEAGE","unregistered evidence schema")
    head=git(repo,"rev-parse","HEAD").decode().strip()
    require_commit(repo,BASE,head)
    def frozen(path):
        data=git(repo,"show",BASE+":"+path)
        need((repo/path).read_bytes()==data,"LINEAGE","checkout differs from frozen file: "+path)
        return data
    lock_path="experiments/cneh_exp_01/bnsyn_integration_contract.json"
    lock=frozen(lock_path)
    source=read_json(lock,"LINEAGE")["source"]
    need(source["commit"]==SOURCE_COMMIT,"LINEAGE","runtime commit")
    if experiment=="CNEH-EXP-04G":
        stem="experiments/cneh_exp_04g/"
        b_arms=tuple(f"P{w}_{a}" for w in (80,160,400) for a in ("NATIVE","CLAMP"))+("P160_NATIVE_EMULATOR",)
        c_arms=("RESPONSE_ROLLING","EXACT_EMULATOR","MODEL_ORACLE","ROUTE_ORACLE")
        worlds={("B",s):{"arms":b_arms,"schedule":[],"duplicate":("P160_NATIVE","P160_NATIVE_EMULATOR")} for s in range(89001,89009)}
        worlds.update({("C",s):{"arms":c_arms,"schedule":schedule(s,89201) if s<89301 else [],
                               "duplicate":("RESPONSE_ROLLING","EXACT_EMULATOR")}
                       for s in (*range(89201,89209),*range(89301,89305))})
        implementation={"runner_sha256":sha(frozen(stem+"run.py")),
                        "parent_policy_sha256":sha(frozen("experiments/cneh_exp_04f/policy.py")),
                        "runtime_lock_sha256":sha(lock),"source":source}
        extra="calibration.json.gz"
        authority="PROSPECTIVE_SIMULATOR_MECHANISTIC_QUALIFICATION"
    else:
        stem="experiments/cneh_exp_05/"
        arms=("DUAL","EXACT_EMULATOR","CONTROL_ONLY","INFO_ONLY","FIXED_ALTERNATE")
        worlds={("",s):{"arms":arms,"schedule":schedule(s,90001) if s<90101 else [],
                        "duplicate":("DUAL","EXACT_EMULATOR")}
                for s in (*range(90001,90013),*range(90101,90105))}
        implementation={"runner_sha256":sha(frozen(stem+"run.py")),"policy_sha256":sha(frozen(stem+"policy.py")),
                        "runtime_lock_sha256":sha(lock),"source":source}
        extra="certificate.json"
        authority="PROSPECTIVE_INTERNAL_ENGINEERED_DUAL_CONTROL_PILOT"
    return {"experiment":experiment,"authority":authority,"worlds":worlds,"names":tuple(sorted((*CORE,extra))),
            "implementation":implementation,"protocol_sha256":sha(frozen(stem+"PREREGISTRATION.md")),
            "steps":3200,"stim_ticks":1600,"source_effort":3200000,"native":True}


def authority_check(verdict,contract):
    try:
        promotion.check_verdict(contract["experiment"],verdict)
        promotion.reject_positive_claims(verdict)
    except (ValueError,TypeError,RecursionError) as exc:
        raise EvidenceViolation("AUTHORITY",str(exc)) from exc
    need(verdict.get("authority")==contract["authority"],"AUTHORITY","wrong evidence authority")
    need(verdict.get("all_instrument_checks_passed") is True,"AUTHORITY","instrument did not pass")
    need(verdict.get("external_replication")=="NOT_TESTED" and verdict.get("physical_energy")=="NOT_VALIDATED",
         "AUTHORITY","unqualified external or energy claim")
    need(verdict.get("invalid_worlds")==[],"AUTHORITY","invalid world roster")
    worlds=contract["worlds"]
    for field,n in (("worlds",len(worlds)),("valid_worlds",len(worlds)),("exact_emulator_equal_worlds",len(worlds)),
                    ("episodes",sum(len(v["arms"]) for v in worlds.values()))):
        need(exact_int(verdict.get(field),n),"AUTHORITY","count mismatch: "+field)


def lineage_check(implementation,protocol_hash,contract):
    need(equal(implementation,contract["implementation"]),"LINEAGE","implementation contract differs")
    need(protocol_hash==contract["protocol_sha256"],"LINEAGE","preregistration differs")


def world_key(row):
    need(isinstance(row,dict),"WORLD","world object required")
    stage=row.get("stage","")
    seed=row.get("seed")
    need(type(stage) is str and integer(seed),"WORLD","world identity")
    return stage,seed


def world_index(rows,contract):
    need(isinstance(rows,list),"WORLD","world array")
    index={}
    for row in rows:
        key=world_key(row)
        need(key in contract["worlds"] and key not in index,"WORLD","unknown or duplicate world")
        spec=contract["worlds"][key]
        need(row.get("valid") is True and row.get("exact_emulator_equal") is True,"WORLD","invalid world or emulator")
        need(equal(row.get("schedule"),spec["schedule"]),"WORLD","schedule mismatch")
        endpoints=row.get("endpoints")
        need(isinstance(endpoints,dict) and set(endpoints)==set(spec["arms"]),"WORLD","endpoint arm roster")
        index[key]=row
    need(set(index)==set(contract["worlds"]),"WORLD","incomplete world roster")
    return index


def strict_array(path):
    """Stream complete JSON objects without accepting duplicate keys or nonfinite numbers."""
    def pairs(items):
        obj={}
        for k,v in items:
            need(k not in obj,"ENCODING","duplicate JSON key")
            obj[k]=v
        return obj
    def finite(s):
        v=float(s)
        need(math.isfinite(v),"ENCODING","nonfinite number")
        return v
    def bad(s):
        raise EvidenceViolation("ENCODING","nonfinite constant "+s)
    decoder=json.JSONDecoder(object_pairs_hook=pairs,parse_float=finite,parse_constant=bad)
    try:
        with gzip.open(path,"rt",encoding="utf-8") as stream:
            buf=""
            def fill():
                nonlocal buf
                chunk=stream.read(1024*1024)
                buf+=chunk
                need(len(buf)<=MAX_EPISODE,"ENCODING","oversize decoded record")
                return bool(chunk)
            def nonempty():
                nonlocal buf
                while True:
                    buf=buf.lstrip()
                    if buf or not fill():
                        return
            nonempty()
            need(buf.startswith("["),"ENCODING","expected array")
            buf=buf[1:]
            first=True
            while True:
                nonempty()
                need(bool(buf),"ENCODING","truncated array")
                if buf.startswith("]"):
                    need(not buf[1:].strip() and not stream.read(1),"ENCODING","trailing data")
                    return
                if not first:
                    need(buf.startswith(","),"ENCODING","missing separator")
                    buf=buf[1:]
                    nonempty()
                    need(bool(buf) and not buf.startswith("]"),"ENCODING","trailing comma")
                while True:
                    try:
                        obj,end=decoder.raw_decode(buf)
                        break
                    except json.JSONDecodeError:
                        need(fill(),"ENCODING","invalid or truncated record")
                need(isinstance(obj,dict),"ENCODING","expected object")
                buf=buf[end:]
                first=False
                yield obj
    except (OSError,EOFError,UnicodeError,RecursionError) as exc:
        raise EvidenceViolation("ENCODING",str(exc)) from exc


def decode_gaba(row):
    values=row.get("true_gaba")
    need(isinstance(values,list) and len(values)==16,"TRACE","receiver roster")
    try:
        result=[float.fromhex(x) for x in values]
    except (ValueError,TypeError,OverflowError) as exc:
        raise EvidenceViolation("TRACE","bad conductance") from exc
    need(all(math.isfinite(x) and x>=0 for x in result),"TRACE","invalid conductance")
    return result


def validate_trace(ep,key,contract):
    rows=ep.get("trace")
    steps=contract["steps"]
    need(isinstance(rows,list) and len(rows)==steps+1,"TRACE","sample roster")
    stage,seed=key
    schedule0=dict(contract["worlds"][key]["schedule"])
    mode=2 if stage=="B" else 0
    used=0
    previous=None
    for t,row in enumerate(rows):
        need(isinstance(row,dict) and exact_int(row.get("tick"),t),"TRACE","ordered sample IDs")
        need(hex_digest(row.get("state_sha256")) and hex_digest(row.get("rng_sha256")),"TRACE","state/RNG digest")
        if contract["native"]:
            values=decode_gaba(row)
            bits=row.get("true_bits")
            need(isinstance(bits,list) and len(bits)==8 and all(integer(x) and x in (0,1) for x in bits),"TRACE","source bits")
            need(row.get("transition_mode")== (None if t==0 else mode),"TRACE","transition mode")
            if previous is not None:
                old,old_bits=previous
                n=sum(MODES[mode][j]*sum(old_bits[j*4:j*4+4]) for j in (0,1))
                need(max(abs(y-DECAY*(x+.5*n)) for x,y in zip(old,values,strict=True))<=1e-9,"TRACE","native recurrence")
            mode=schedule0.get(t,mode)
            need(exact_int(row.get("next_mode"),mode),"TRACE","next mode")
            previous=values,bits
        if t<steps:
            group=row.get("group")
            need("group" in row and (group is None or integer(group) and group in (0,1)),"TRACE","source group")
            used+=group is not None
            if contract["native"]:
                need(equal(row.get("source_inputs_pA"),[500. if group==g else 0. for g in (0,1)])
                     and row.get("direct_B_pA")==300. and row.get("applied_gain")==1.,"TRACE","native current envelope")
        else:
            need("group" not in row,"TRACE","terminal action")
    need(used==contract["stim_ticks"] and exact_int(ep.get("source_current_l1_pA_ticks"),contract["source_effort"]),"TRACE","source effort")
    return sha(canonical([rows[0]["state_sha256"],[(r["rng_sha256"],r.get("noise"),r.get("erasures")) for r in rows]]))


def episode_index(episodes,worlds,contract):
    seen=set()
    signatures={}
    duplicate={}
    for ep in episodes:
        try:
            key=world_key(ep)
        except EvidenceViolation as exc:
            raise EvidenceViolation("TRACE",str(exc)) from exc
        arm=ep.get("arm")
        need(key in worlds and type(arm) is str and arm in contract["worlds"][key]["arms"] and (key,arm) not in seen,"TRACE","episode identity")
        seen.add((key,arm))
        need(ep.get("valid") is True,"TRACE","invalid episode")
        projected={k:v for k,v in ep.items() if k not in ("trace","seed","arm","stage")}
        need(equal(projected,worlds[key]["endpoints"][arm]),"TRACE","endpoint projection mismatch")
        sig=validate_trace(ep,key,contract)
        need(key not in signatures or signatures[key]==sig,"TRACE","paired exogenous or initial-state mismatch")
        signatures[key]=sig
        if arm in contract["worlds"][key]["duplicate"]:
            digest=sha(canonical({k:v for k,v in ep.items() if k!="arm"}))
            need(key not in duplicate or duplicate[key]==digest,"TRACE","exact emulator mismatch")
            duplicate[key]=digest
    want={(key,arm) for key,spec in contract["worlds"].items() for arm in spec["arms"]}
    need(seen==want and set(duplicate)==set(worlds),"TRACE","incomplete episode/emulator roster")
    return len(seen)


def validate_extra(root,contract,verdict):
    if not contract["native"]:
        return
    if contract["experiment"]=="CNEH-EXP-04G":
        roster=set()
        projections=[]
        for row in strict_array(root/"calibration.json.gz"):
            current,clamp=row.get("current_pA"),row.get("clamp")
            need(integer(current) and current in (0,100,130,160,200,300,400,500) and type(clamp) is bool
                 and (current,clamp) not in roster,"TRACE","calibration roster")
            roster.add((current,clamp))
            trace=row.get("trace")
            need(isinstance(trace,list) and len(trace)==3200,"TRACE","calibration horizon")
            spikes=[]
            for t,sample in enumerate(trace,1):
                need(exact_int(sample.get("tick"),t) and integer(sample.get("spike")) and sample["spike"] in (0,1),"TRACE","calibration sample")
                if sample["spike"]:
                    spikes.append(t)
            need(exact_int(row.get("spikes"),len(spikes)) and exact_int(row.get("second_half_spikes"),sum(t>1600 for t in spikes))
                 and row.get("first_spike_ticks")== (spikes[0] if spikes else None),"TRACE","calibration endpoint mismatch")
            projections.append({k:v for k,v in row.items() if k!="trace"})
        need(len(roster)==16 and equal(projections,verdict.get("calibration")),"TRACE","calibration verdict roster")
    else:
        cert=read_json((root/"certificate.json").read_bytes(),"TRACE")
        need(equal(cert,verdict.get("reachability_certificate")) and isinstance(cert,dict),"TRACE","certificate mismatch")
        for k,v in (("max_contiguous_samples",25),("min_inter_run_gap",24),("bound_320_samples",175),("bound_3200_samples",1640)):
            need(exact_int(cert.get(k),v),"TRACE","structural certificate field "+k)


def admit(root,contract,before=None):
    observed=snapshot(root,contract["names"])
    if before is not None:
        require_same_snapshot(before,observed)
    verdict=read_json((root/"verdict.json").read_bytes(),"AUTHORITY")
    authority_check(verdict,contract)
    impl=read_json((root/"implementation.json").read_bytes(),"LINEAGE")
    lineage_check(impl,observed["files"]["preregistration.md"],contract)
    worlds=world_index(read_json((root/"worlds.json").read_bytes(),"WORLD"),contract)
    count=episode_index(strict_array(root/"episodes.json.gz"),worlds,contract)
    validate_extra(root,contract,verdict)
    require_same_snapshot(observed,snapshot(root,contract["names"]))
    return {"schema":"cneh-negative-evidence-admission-v2","experiment":contract["experiment"],
            "worlds":len(worlds),"episodes":count,"manifest":observed,"same_worker_snapshot_match":before is not None,
            "engineering_evidence":"CHECKED","scientific_promotion":"BLOCKED",FLAG:False}


def admit_archive(path,contract):
    identifier,digest,prefix=ARCHIVES[contract["experiment"]]
    need(file_hash(path)==digest,"MANIFEST","historical archive digest mismatch")
    with tempfile.TemporaryDirectory(prefix="cneh-sealed-") as tmp,zipfile.ZipFile(path) as z:
        folder=Path(tmp)
        entries=[i for i in z.infolist() if not i.is_dir()]
        names=[i.filename for i in entries]
        expected={prefix+"/"+n for n in (*contract["names"],"SHA256SUMS")}|{prefix+"-install.json"}
        need(len(names)==len(set(names)) and set(names)==expected,"ROSTER","historical ZIP roster")
        for info in entries:
            need(info.file_size<=MAX_FILE and (info.external_attr>>16)&0o170000 in (0,stat.S_IFREG),"ROSTER","invalid ZIP member")
            if info.filename==prefix+"-install.json":
                continue
            name=info.filename.split("/")[-1]
            with z.open(info) as inp,(folder/name).open("xb") as out:
                shutil.copyfileobj(inp,out,1024*1024)
        report=admit(folder,contract)
    return {**report,"historical_archive_id":identifier,"historical_archive_sha256":digest}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    sub=ap.add_subparsers(dest="command",required=True)
    for command in ("snapshot","admit","archive"):
        p=sub.add_parser(command)
        p.add_argument("--experiment",choices=tuple(ARCHIVES),required=True)
        p.add_argument("--input",type=Path,required=True)
        p.add_argument("--out",type=Path,required=True)
        if command=="admit":
            p.add_argument("--before",type=Path,required=True)
    args=ap.parse_args()
    try:
        contract=trusted_contract(args.experiment)
        if args.command=="snapshot":
            report=snapshot(args.input,contract["names"])
        elif args.command=="archive":
            report=admit_archive(args.input,contract)
        else:
            regular(args.before,"REPLAY")
            report=admit(args.input,contract,read_json(args.before.read_bytes(),"REPLAY"))
        with args.out.open("xb") as out:
            out.write(canonical(report))
        print(canonical(report).decode(),end="")
        return 0
    except (ValueError,OSError,TypeError,KeyError,RecursionError,zipfile.BadZipFile) as exc:
        print(json.dumps({"engineering_evidence":"BLOCKED","scientific_promotion":"BLOCKED",FLAG:False,"error":str(exc)}),file=sys.stderr)
        return 2


if __name__=="__main__":
    raise SystemExit(main())
