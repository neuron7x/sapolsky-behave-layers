"""Fail-closed same-run artifact transport for CNEH X/Y campaigns."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def canonical(x):
    return (json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()


def expected(spec):
    if spec not in ("x","y"):
        raise ValueError("unknown campaign")
    prefix=f"cneh05{spec}-"
    groups=[(prefix+"pair-*",{prefix+f"pair-{i}" for i in range(40)}),
            (prefix+"preflight-*",{prefix+"preflight-x86_64",prefix+"preflight-aarch64"})]
    if spec=="y":
        groups.extend([(prefix+"reference-*",{prefix+f"reference-{i}" for i in range(8)}),
                       (prefix+"forensic-aggregate",{prefix+"forensic-aggregate"})])
    return groups


def fetch(spec,run_id,repo,head,profiles,upstream_ok,download):
    if repo!="neuron7x/sapolsky-behave-layers" or not run_id.isdecimal() or len(head)!=40 or any(c not in "0123456789abcdef" for c in head):
        raise ValueError("invalid exact run identity")
    if upstream_ok not in ("true","false"):
        raise ValueError("invalid upstream status")
    profiles.mkdir(parents=True,exist_ok=False)
    receipts=[]
    for pattern,names in expected(spec):
        if len(names)==1:
            name=next(iter(names))
            code=download(["gh","run","download",run_id,"--repo",repo,"--name",name,"--dir",str(profiles/name)])
        else:
            code=download(["gh","run","download",run_id,"--repo",repo,"--pattern",pattern,"--dir",str(profiles)])
        if type(code) is not int:
            raise ValueError("invalid download exit code")
        receipts.append({"pattern":pattern,"exit_code":code,"expected":sorted(names)})
    required=set().union(*(names for _,names in expected(spec)))
    paths=list(profiles.iterdir())
    actual={p.name for p in paths if p.is_dir() and not p.is_symlink()}
    malformed=sorted(p.name for p in paths if not p.is_dir() or p.is_symlink())
    missing=sorted(required-actual);unexpected=sorted(actual-required)
    ok=(upstream_ok=="true" and all(r["exit_code"]==0 for r in receipts) and not missing and not unexpected and not malformed)
    return {"schema":"CNEH-ARTIFACT-TRANSPORT-V1","spec":spec,"repo":repo,"run_id":run_id,"head_sha":head,
            "upstream_ok":upstream_ok=="true","downloads":receipts,"missing":missing,"unexpected":unexpected,
            "malformed":malformed,"status":"PASS" if ok else "BLOCKED","scientific_promotion_authorized":False}


def cli():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--spec",choices=("x","y"),required=True)
    ap.add_argument("--run-id",required=True);ap.add_argument("--repo",required=True);ap.add_argument("--head",required=True)
    ap.add_argument("--upstream-ok",choices=("true","false"),required=True)
    ap.add_argument("--profiles",type=Path,required=True);ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    def download(cmd):
        try:
            return subprocess.run(cmd,check=False).returncode
        except OSError:
            return 127
    result=fetch(args.spec,args.run_id,args.repo,args.head,args.profiles,args.upstream_ok,download)
    args.out.mkdir(parents=True,exist_ok=False)
    raw=canonical(result)
    (args.out/"report.json").write_bytes(raw)
    (args.out/"SHA256SUMS").write_text(hashlib.sha256(raw).hexdigest()+"  report.json\n")
    print(raw.decode(),end="")
    return 0 if result["status"]=="PASS" else 2


if __name__=="__main__":
    raise SystemExit(cli())
