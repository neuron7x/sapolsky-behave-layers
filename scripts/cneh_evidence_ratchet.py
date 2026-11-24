"""Executable seven-family fault injection panel for the real evidence gate."""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
from pathlib import Path
import random
import sys
import tempfile

from scripts import cneh_evidence_admission as a

FAMILIES=("AUTHORITY","LINEAGE","MANIFEST","ROSTER","WORLD","TRACE","REPLAY")
NAMES=tuple(sorted((*a.CORE,"certificate.json")))
ARMS=("DUAL","EXACT_EMULATOR")
SEEDS=tuple(range(101,107))
FLAG="scientific_promotion_authorized"
ROOT=Path(__file__).resolve().parents[1]


def fixture():
    protocol=b"Independent finite synthetic fault-injection fixture.\n"
    impl={"runner_sha256":"1"*64,"policy_sha256":"2"*64,"runtime_lock_sha256":"3"*64,
          "source":{"commit":"4"*40}}
    contract={"experiment":"CNEH-EXP-FIXTURE","authority":"SYNTHETIC_NEGATIVE_EVIDENCE_ONLY",
              "names":NAMES,"protocol_sha256":a.sha(protocol),"implementation":impl,
              "worlds":{("",s):{"arms":ARMS,"schedule":[],"duplicate":ARMS} for s in SEEDS},
              "steps":4,"stim_ticks":2,"source_effort":4000,"native":False}
    worlds=[]
    episodes=[]
    for seed in SEEDS:
        endpoints={}
        for arm in ARMS:
            rows=[{"tick":t,"state_sha256":a.sha(f"{seed}/state/{t}".encode()),
                   "rng_sha256":a.sha(f"{seed}/rng/{t}".encode()),"noise":[0.],"erasures":[False]}
                  for t in range(5)]
            for t,row in enumerate(rows[:-1]):
                row["group"]=0 if t%2==0 else None
            end={"valid":True,"source_current_l1_pA_ticks":4000,"metric":seed/1000}
            endpoints[arm]=copy.deepcopy(end)
            episodes.append({"seed":seed,"arm":arm,**copy.deepcopy(end),"trace":rows})
        worlds.append({"seed":seed,"valid":True,"exact_emulator_equal":True,"schedule":[],"endpoints":endpoints})
    verdict={"experiment":contract["experiment"],"authority":contract["authority"],FLAG:False,
             "all_instrument_checks_passed":True,"external_replication":"NOT_TESTED","physical_energy":"NOT_VALIDATED",
             "invalid_worlds":[],"worlds":6,"valid_worlds":6,"exact_emulator_equal_worlds":6,"episodes":12}
    files={"preregistration.md":protocol,"implementation.json":a.canonical(impl),
           "verdict.json":a.canonical(verdict),"worlds.json":a.canonical(worlds),
           "episodes.json.gz":gzip.compress(a.canonical(episodes),mtime=0),
           "certificate.json":a.canonical({"fixture_only":True})}
    return contract,files


def manifest(root):
    data="".join(f"{a.sha((root/name).read_bytes())}  {name}\n" for name in NAMES).encode("ascii")
    (root/"SHA256SUMS").write_bytes(data)


def write_fixture(root,files):
    root.mkdir()
    for k,v in files.items():
        (root/k).write_bytes(v)
    manifest(root)


def read(root,name):
    raw=(root/name).read_bytes()
    return json.loads(gzip.decompress(raw) if name.endswith(".gz") else raw)


def write(root,name,value):
    raw=a.canonical(value)
    (root/name).write_bytes(gzip.compress(raw,mtime=0) if name.endswith(".gz") else raw)


def signature(root):
    entries=[]
    for p in sorted(root.iterdir()):
        if p.is_symlink():
            value=["symlink",str(p.readlink().name)]
        elif p.is_dir():
            value=["directory"]
        else:
            value=["file",a.sha(p.read_bytes())]
        entries.append([p.name,value])
    return a.sha(a.canonical(entries))


AUTH_CASES=(
    (FLAG,True),(FLAG,1),(FLAG,0),(FLAG,None),(FLAG,"false"),(FLAG,"__DELETE__"),
    ("experiment","CNEH-EXP-OTHER"),("experiment",None),("experiment",1),("experiment","__DELETE__"),
    ("nested",[{FLAG:True}]),("nested",{"scientific_promotion":"PASS"}),
    ("authority","CONFIRMED"),("authority",False),("authority","__DELETE__"),
    ("all_instrument_checks_passed",False),("all_instrument_checks_passed",1),
    ("all_instrument_checks_passed","__DELETE__"),("external_replication","PASS"),
    ("external_replication","__DELETE__"),("physical_energy","VALIDATED"),
    ("invalid_worlds",[101]),("worlds",True),("exact_emulator_equal_worlds",5),
)
LINEAGE_FIELDS=("runner_sha256","policy_sha256","runtime_lock_sha256","source")


def cases():
    out=[]
    for i,(field,value) in enumerate(AUTH_CASES):
        out.append(("AUTHORITY",f"A{i+1:02}",[field,value]))
    for field in LINEAGE_FIELDS:
        for operation in ("delete","null","list","wrong","boolean","object"):
            out.append(("LINEAGE",f"L/{field}/{operation}",[field,operation]))
    for name in NAMES:
        for operation in ("append","omit_line","duplicate_line","wrong_hash"):
            out.append(("MANIFEST",f"M/{name}/{operation}",[name,operation]))
        for operation in ("missing","renamed","directory","symlink"):
            out.append(("ROSTER",f"R/{name}/{operation}",[name,operation]))
        for i in range(4):
            out.append(("REPLAY",f"P/{name}/change-{i+1}",[name,i]))
    for seed in SEEDS:
        for operation in ("unknown_seed","invalid_world","false_emulator","missing_arm"):
            out.append(("WORLD",f"W/{seed}/{operation}",[seed,operation]))
        for operation in ("endpoint","effort","sample_id","exogenous"):
            out.append(("TRACE",f"T/{seed}/{operation}",[seed,operation]))
    return out


def mutate(root,family,args):
    if family=="AUTHORITY":
        field,value=args
        data=read(root,"verdict.json")
        if value=="__DELETE__":
            del data[field]
        else:
            data[field]=value
        write(root,"verdict.json",data)
        manifest(root)
    elif family=="LINEAGE":
        field,op=args
        data=read(root,"implementation.json")
        if op=="delete":
            del data[field]
        else:
            data[field]={"null":None,"list":[],"wrong":"forged","boolean":True,"object":{"forged":field}}[op]
        write(root,"implementation.json",data)
        manifest(root)
    elif family=="MANIFEST":
        name,op=args
        if op=="append":
            with (root/name).open("ab") as out:
                out.write(b"\x00")
        else:
            path=root/"SHA256SUMS"
            lines=path.read_text().splitlines()
            i=next(j for j,x in enumerate(lines) if x.endswith("  "+name))
            if op=="omit_line":
                lines.pop(i)
            elif op=="duplicate_line":
                lines.insert(i,lines[i])
            else:
                lines[i]="0"*64+"  "+name
            path.write_text("\n".join(lines)+"\n")
    elif family=="ROSTER":
        name,op=args
        path=root/name
        if op=="renamed":
            path.rename(root/(name+".alias"))
        else:
            raw=path.read_bytes()
            path.unlink()
            if op=="directory":
                path.mkdir()
            elif op=="symlink":
                outside=root.parent/("external-"+name)
                outside.write_bytes(raw)
                path.symlink_to(outside)
    elif family=="WORLD":
        seed,op=args
        data=read(root,"worlds.json")
        row=next(x for x in data if x["seed"]==seed)
        if op=="unknown_seed":
            row["seed"]=seed+1000
        elif op=="invalid_world":
            row["valid"]=False
        elif op=="false_emulator":
            row["exact_emulator_equal"]=False
        else:
            del row["endpoints"]["EXACT_EMULATOR"]
        write(root,"worlds.json",data)
        manifest(root)
    elif family=="TRACE":
        seed,op=args
        data=read(root,"episodes.json.gz")
        row=next(x for x in data if x["seed"]==seed and x["arm"]=="EXACT_EMULATOR")
        if op=="endpoint":
            row["metric"]=-1
        elif op=="effort":
            row["source_current_l1_pA_ticks"]=2000
            worlds=read(root,"worlds.json")
            next(x for x in worlds if x["seed"]==seed)["endpoints"]["EXACT_EMULATOR"]["source_current_l1_pA_ticks"]=2000
            write(root,"worlds.json",worlds)
        elif op=="sample_id":
            row["trace"][1]["tick"]=0
        else:
            row["trace"][2]["rng_sha256"]="a"*64
        write(root,"episodes.json.gz",data)
        manifest(root)
    elif family=="REPLAY":
        name,i=args
        with (root/name).open("ab") as out:
            out.write(bytes([i+1]))
        manifest(root)
    else:
        raise ValueError("unknown fault family")


def campaign(seed):
    contract,files=fixture()
    catalog=cases()
    ids=[x[1] for x in catalog]
    if len(catalog)!=168 or len(set(ids))!=168 or any(sum(x[0]==f for x in catalog)!=24 for f in FAMILIES):
        raise ValueError("fault catalogue drift")
    order=list(catalog)
    random.Random(seed).shuffle(order)
    records=[]
    with tempfile.TemporaryDirectory(prefix="cneh-seven-axis-") as tmp:
        parent=Path(tmp)
        clean=parent/"clean"
        write_fixture(clean,files)
        before=a.snapshot(clean,NAMES)
        valid=a.admit(clean,contract,before)
        if valid["worlds"]!=6 or valid["episodes"]!=12 or valid[FLAG] is not False:
            raise ValueError("clean fixture failed")
        clean_sig=signature(clean)
        for index,(family,identifier,args) in enumerate(order):
            root=parent/f"case-{index:03}"
            write_fixture(root,files)
            if signature(root)!=clean_sig:
                raise ValueError("fixture changed before mutation")
            mutate(root,family,args)
            witness=signature(root)
            if witness==clean_sig:
                raise ValueError("fault made no observable change: "+identifier)
            observed=None
            detail=None
            try:
                if family=="REPLAY":
                    a.require_same_snapshot(before,a.snapshot(root,NAMES))
                else:
                    a.admit(root,contract)
            except a.EvidenceViolation as exc:
                observed=exc.code
                detail=str(exc)
            except Exception as exc:
                observed="INVALID_EXCEPTION"
                detail=type(exc).__name__+": "+str(exc)
            records.append({"family":family,"case":identifier,"fault":args,
                            "fixture_sha256":clean_sig,"mutated_fixture_sha256":witness,
                            "expected":family,"observed":observed,"detail":detail,
                            "disposition":"REJECTED_EXPECTED" if observed==family else
                            "SURVIVED" if observed is None else "INVALID"})
        a.admit(clean,contract,before)
    records.sort(key=lambda x:x["case"])
    for family in FAMILIES:
        witnesses=[x["mutated_fixture_sha256"] for x in records if x["family"]==family]
        if len(set(witnesses))!=24:
            raise ValueError("duplicate injected fixture within "+family)
    counts={f:{"cases":sum(x["family"]==f for x in records),
               "rejected":sum(x["family"]==f and x["disposition"]=="REJECTED_EXPECTED" for x in records)}
            for f in FAMILIES}
    return {"schema":"cneh-seven-axis-evidence-ratchet-v2","python":sys.version.split()[0],
            "seed":seed,"case_count":len(records),"fixture_sha256":clean_sig,
            "checker_sha256":a.sha(Path(a.__file__).read_bytes()),"harness_sha256":a.sha(Path(__file__).read_bytes()),
            "family_counts":counts,"clean_before_after":"PASS",
            "all_attacks_pass":all(x["disposition"]=="REJECTED_EXPECTED" for x in records),
            "scientific_promotion_authorized":False,"records":records}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed",type=int,required=True)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    report=campaign(args.seed)
    with args.out.open("xb") as out:
        out.write(a.canonical(report))
    print(a.canonical({**{k:v for k,v in report.items() if k!="records"},
                       "nonconforming":[x for x in report["records"] if x["disposition"]!="REJECTED_EXPECTED"]}).decode(),end="")
    return 0 if report["all_attacks_pass"] else 2


if __name__=="__main__":
    raise SystemExit(main())
