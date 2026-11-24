"""Frozen input tape adapter. Runtime sees only one Frame, never this world."""
from __future__ import annotations

from bisect import bisect_right
import gzip
import io
from pathlib import Path
import zipfile

from experiments.cneh_exp_05j import run as history
from experiments.cneh_exp_05j import verify as v
from experiments.cneh_exp_05v import audit as evidence
from experiments.cneh_exp_05x import worlds as w
from experiments.cneh_exp_05y import run as custody
from experiments.cneh_exp_06a import runtime as rt

R1=(14904511434,"b6fec832e38e6aca61ffa35388cf3b45b32cf86a61000f719a49c966a0632266")
MANIFEST=(14899403821,"753636d73f9c09a22330e5ee6ef6003af10a2bec37600125410f5351ee18dfd9")
MANIFEST_SHA="cdd4a4b03af103436346c78aeb928241cef95e4c660f0ecb3dbcd2601568376d"
R1_HEAD="ae9c3b28914773de16be825010f755508d08389e"
OOD=(0,251,502,753)
SHARDS=((14902978232,"b4412d238ea16d0608fde69ba43747c77b484e3148cf62564fee7d0d50410860"),
        (14902358635,"5b9dc14e71682a7763427e6473d421cf2a970d56c49b2b82d0290a7c642e1633"),
        (14903751209,"a6d75cf4cbb156e265542c0fee9cd0fbc82aee13b686dcf7d1ed04a80bec6a0a"),
        (14903532208,"fd5b86bad8d1582b295d2a712dd5b7b86d820be64be9f88e8ca6c02012f7f16c"))


def archive(root,anchor,members,manifest=True):
    aid,sha=anchor
    raw=(root/f"{aid}.zip").read_bytes()
    rt.need(w.sha(raw)==sha,"external archive anchor")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        expected=set(members)|({"SHA256SUMS"} if manifest else set())
        rt.need(len(z.namelist())==len(expected) and set(z.namelist())==expected,"archive roster")
        rt.need(all(0<=x.file_size<=256*1024*1024 and not x.is_dir() for x in z.infolist()),"archive member size")
        files={n:z.read(n) for n in expected}
    if manifest:
        sums="".join(w.sha(files[n])+"  "+n+"\n" for n in sorted(members)).encode()
        rt.need(files["SHA256SUMS"]==sums,"archive member digest")
    return files


def qualify_r1(root):
    raw=archive(root,R1,{"report.json"})["report.json"]
    value=custody.json_strict(raw)
    rt.need(value["head_sha"]==R1_HEAD and value["run_id"]=="45356915631"
            and value["manifest_sha256"]==MANIFEST_SHA and value["complete_evidence"] is True
            and value["exact_pairs"]==value["exact_raw_samples"]==value["exact_event_tapes"]==value["exact_step_schedules"]==1000
            and value["reference_qualified"]==8 and value["scientific_promotion_authorized"] is False
            and value["blind_causal_cohort"]=="BLOCKED","R1 scope")
    return value


def load_case(root,index):
    rt.need(type(index) is int and 0<=index<12,"case roster")
    agg=qualify_r1(root)
    if index<8:
        ep,initial,tape,refs=history.inputs(root,index)
        world={"id":index,"arm":ep["arm"],"initial":rt.state_encode(initial),
               "external":[[w.hx(t/10.) for t in range(512) if tape[t,i]] for i in range(32)],
               "mode_order":[0,1,2,3],"switches":[w.hx(t) for t in (12.8,25.6,38.4)],
               "current_switches":[w.hx(t) for t in w.CURRENT]}
        return world,refs,None
    i=OOD[index-8]
    raw=archive(root,MANIFEST,{"manifest.json"},False)["manifest.json"]
    rt.need(w.sha(raw)==MANIFEST_SHA,"OOD manifest identity")
    manifest=custody.json_strict(raw)
    world=manifest["worlds"][i]
    rt.need(world==w.world(i) and agg["reports"][i]["id"]==i and agg["reports"][i]["comparison"]["exact"] is True,"OOD world anchor")
    data=archive(root,SHARDS[index-8],{"receipt.json","episodes.jsonl.gz","repeat.json","install.json"})
    receipt=custody.json_strict(data["receipt.json"])
    rt.need(receipt["arch"]=="x86_64" and receipt["shard"]==i//25 and receipt["manifest_sha256"]==MANIFEST_SHA
            and receipt["fingerprint"]["head_sha"]==R1_HEAD and receipt["fingerprint"]["run_id"]=="45356915631"
            and receipt["episode_file_sha256"]==w.sha(data["episodes.jsonl.gz"]),"R1 native shard identity")
    with gzip.GzipFile(fileobj=io.BytesIO(data["episodes.jsonl.gz"])) as f:
        found=None
        for n in range(i//25*25,(i//25+1)*25):
            line=f.readline(16*1024*1024)
            row=custody.json_strict(line)
            rt.need(row["id"]==n and row["status"]=="COMPLETE","R1 episode roster")
            if n==i:
                found=row
        rt.need(not f.read(1),"extra episode")
    rt.need(found is not None and found["input_sha256"]==w.digest(world),"R1 world identity")
    old=found["result"]
    rt.need(old["physical_sha256"]==w.digest(old["physical"]) and old["trace_sha256"]==w.digest(old["ledgers"]),"R1 raw digest")
    physical=old["physical"]
    refs={"R1_ARCHIVE":{"states":physical["samples"],"events":v.event_times(physical)}}
    return world,refs,old


def frame_at(world,k,perturb=False):
    start,end=k/10.,(k+1)/10.
    times=[w.f(t) for t in world["switches"]]
    order=world["mode_order"]
    mode=order[bisect_right(times,start)]
    switches=tuple((w.hx(t),order[i+1]) for i,t in enumerate(times) if start<t<end)
    external=tuple(tuple(t for t in row if start<=w.f(t)<end) for row in world["external"])
    arm=world["arm"]
    action=arm if arm!="ALTERNATE" else ("G0","G1")[bisect_right([w.f(t) for t in world["current_switches"]],start)%2]
    if perturb and k==256:
        action="G0" if action=="WAIT" else "WAIT"
        mode=next(m for m in range(4) if m!=mode and (not switches or m!=switches[0][1]))
        ex=list(external)
        impulse=next(w.hx(start+d*(end-start)) for d in (.5,.25,.75) if w.hx(start+d*(end-start)) not in ex[0])
        ex[0]=tuple(sorted((*ex[0],impulse),key=w.f))
        external=tuple(ex)
    f=rt.Frame(k,mode,switches,external)
    rt.validate_frame(f,k)
    return f,action
