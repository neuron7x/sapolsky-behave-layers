"""Raw native first-chunk reconstruction; distinguish new from sealed execution."""
from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import struct
from unittest.mock import patch
import zipfile

import numpy as np

from experiments.cneh_exp_05j import integrator as j
from experiments.cneh_exp_05x import trace as x
from experiments.cneh_exp_05x import worlds as w

ANCHORS={
 "x86_64":(14899772570,"6b138b35b41cd5d525fd34c769672d250481c4f6ae40adaaab0272593aa2ee88","c90c9c716a5931a0ba678cfda1bfac56326eb2bdcd4fd76670877712ded8a4dd"),
 "aarch64":(14900142922,"f4ea0aaceebb522c44c92b9d05eda419619a64dcb64b67cd7aed0530d032a56a","7b00be82e289818f193b17e836e376fb4d5dba594be27826a911e56cb7d14577")
}


class StopChunk(Exception):
    pass


def capture(world,arch,archive):
    _,zipsha,expected=ANCHORS[arch]
    w.need(w.sha(archive.read_bytes())==zipsha,"sealed original ZIP digest")
    with zipfile.ZipFile(archive) as z:
        for line in z.read("SHA256SUMS").decode().splitlines():
            digest,name=line.split("  ")
            w.need(w.sha(z.read(name))==digest,"original manifest")
        with gzip.GzipFile(fileobj=z.open("episodes.jsonl.gz")) as stream:
            row=json.loads(stream.readline())
    w.need(row["id"]==0 and row["input_sha256"]==w.digest(world) and row["status"]=="COMPLETE"
           and row["result"]["ledgers"][24][0]["chunks"][0]==expected,"original chunk binding")
    records=[]
    tracker=x.Trace()
    base_add=tracker.add
    base_cross=j.dense_crossing
    def add(raw):
        records.append(raw.hex())
        base_add(raw)
    tracker.add=add
    def crossing(dense):
        event=base_cross(dense)
        tracker.accept(dense,event)
        if tracker.active["accepted"]==64:
            raise StopChunk()
        return event
    initial=np.array([w.f(a[24]) for a in world["initial"]])
    with patch.object(j,"MODES",tuple(w.MODES[k] for k in world["mode_order"])),patch.object(j,"SWITCHES",tuple(map(w.f,world["switches"]))),patch.object(j,"CURRENT_SWITCHES",tuple(map(w.f,world["current_switches"]))),patch.object(j,"RK45",tracker.solver_class()),patch.object(j,"dense_crossing",crossing):
        try:
            j.cell(initial,list(map(w.f,world["external"][24])),{},world["arm"],24,"TIGHT")
        except StopChunk:
            pass
        else:
            raise ValueError("first chunk capture incomplete")
    raw=b"".join(bytes.fromhex(v) for v in records)
    digest=w.sha(raw)
    w.need(tracker.active["chunks"]==[digest],"captured chunk instrumentation mismatch")
    return {"arch":arch,"world":0,"neuron":24,"segment":0,"chunk":0,
            "sealed_chunk_sha256":expected,"captured_sha256":digest,
            "matches_sealed":digest==expected,"records":records,
            "accepted_steps":64,"trial_records":sum(v.startswith("54") for v in records)}


def label(record,offset):
    if offset==0:return "record_tag"
    idx=(offset-1)//8
    if record[:1]==b"T":
        names=["trial_t","trial_h","error_norm"]+[f"K[{k//2},{k%2}]" for k in range(14)]+["scale[0]","scale[1]"]
    elif record[:1]==b"A":
        names=["t_old","t_end","next_h_abs","committed_stop","next_V","next_w","old_V","old_w"]+[f"Q[{k//4},{k%4}]" for k in range(8)]
    else:return "unknown_record"
    return names[idx] if idx<len(names) else "event_encoding"


def compare(left,right):
    for item,arch in ((left,"x86_64"),(right,"aarch64")):
        w.need(item["arch"]==arch and item["sealed_chunk_sha256"]==ANCHORS[arch][2] and
               w.sha(b"".join(bytes.fromhex(x) for x in item["records"]))==item["captured_sha256"] and
               item["matches_sealed"] is (item["captured_sha256"]==ANCHORS[arch][2]),"raw capture binding")
    a,b=([bytes.fromhex(v) for v in item["records"]] for item in (left,right))
    offset=0
    first=None
    for ri,(x0,y0) in enumerate(zip(a,b)):
        if x0!=y0:
            k=next((k for k,(u,v) in enumerate(zip(x0,y0)) if u!=v),min(len(x0),len(y0)))
            first={"record_index_zero_based":ri,"record_byte_offset":k,"field":label(x0,k),
                   "byte_index_in_chunk":offset+k}
            if k<min(len(x0),len(y0)):
                xor=x0[k]^y0[k]
                first["bit_index_in_chunk_MSB_zero_based"]=(offset+k)*8+8-xor.bit_length()
                if k>0 and 1+8*((k-1)//8+1)<=min(len(x0),len(y0)) and x0[:1]==y0[:1]:
                    start=1+8*((k-1)//8)
                    first["x86_hex"]=struct.unpack(">d",x0[start:start+8])[0].hex()
                    first["arm_hex"]=struct.unpack(">d",y0[start:start+8])[0].hex()
            break
        offset+=len(x0)
    if first is None and len(a)!=len(b):
        first={"record_index_zero_based":min(len(a),len(b)),"field":"record_count"}
    return {"scope":"SEALED_CHUNK_REPRODUCED" if left["matches_sealed"] and right["matches_sealed"] else "NEW_EXECUTION_ONLY",
            "first_difference":first,"x86_chunk":left["captured_sha256"],"arm_chunk":right["captured_sha256"],
            "matches_original":{"x86_64":left["matches_sealed"],"aarch64":right["matches_sealed"]},
            "scientific_promotion":"BLOCKED","scientific_promotion_authorized":False}


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--arch",choices=tuple(ANCHORS))
    ap.add_argument("--archive",type=Path)
    ap.add_argument("--manifest",type=Path)
    ap.add_argument("--profiles",type=Path)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    if args.arch:
        raw=args.manifest.read_bytes()
        w.need(w.sha(raw)=="cdd4a4b03af103436346c78aeb928241cef95e4c660f0ecb3dbcd2601568376d","manifest anchor")
        value=capture(json.loads(raw)["worlds"][0],args.arch,args.archive)
    else:
        value=compare(*(json.loads((args.profiles/f"cneh05y-forensic-{arch}"/"report.json").read_bytes()) for arch in ANCHORS))
    with args.out.open("xb") as out:
        out.write(w.canonical(value))
    print(w.canonical({k:v for k,v in value.items() if k!="records"}).decode(),end="")


if __name__=="__main__":
    main()
