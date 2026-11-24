"""Read-only multiscale audit of authenticated EXP05 evidence; not native counterfactuals."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import itertools
import json
import math
import zipfile
from pathlib import Path

from experiments.cneh_exp_04c import qualification as q
from experiments.cneh_exp_04d import run as d
from experiments.cneh_exp_04e import audit as e
from experiments.cneh_exp_04g import run as g
from experiments.cneh_exp_05 import policy as p,run as prior
from experiments.cneh_exp_05m import scales as s

HERE=Path(__file__).resolve().parent
ARCHIVE_SHA="db78569d633a4fd1ae5649ab02e53a86b48e97f0317b45a849a56cd73e993ea8"
SOURCE_HEAD="8c9b71f366af32fdfc5ffd8618198b4fe22af244"
NAMES={"certificate.json","episodes.json.gz","implementation.json","preregistration.md","verdict.json","worlds.json"}
UNIQUE=("DUAL","CONTROL_ONLY","INFO_ONLY","FIXED_ALTERNATE")
pinned,parent=d.pinned,d.parent
require=p.require


def stream_array(stream):
    decoder=json.JSONDecoder()
    buf=""
    def fill():
        nonlocal buf
        chunk=stream.read(4*1024*1024)
        buf+=chunk
        return bool(chunk)
    def nonempty():
        nonlocal buf
        while True:
            buf=buf.lstrip()
            if buf or not fill():
                return
    nonempty()
    require(buf.startswith("["),"expected JSON array")
    buf=buf[1:]
    first=True
    while True:
        nonempty()
        require(bool(buf),"truncated archive array")
        if buf.startswith("]"):
            require(not buf[1:].strip() and not stream.read().strip(),"trailing archive data")
            return
        if not first:
            require(buf.startswith(","),"missing array separator")
            buf=buf[1:]
            nonempty()
            require(bool(buf) and not buf.startswith("]"),"trailing comma")
        while True:
            try:
                value,end=decoder.raw_decode(buf)
                break
            except json.JSONDecodeError:
                if not fill():
                    raise
        require(isinstance(value,dict),"invalid episode record")
        buf=buf[end:]
        first=False
        yield value


def authenticate(z):
    prefix="cneh05/"
    names=[i.filename for i in z.infolist() if not i.is_dir()]
    require(len(names)==len(set(names)) and set(names)=={prefix+x for x in NAMES|{"SHA256SUMS"}}|{"cneh05-install.json"},"archive roster")
    hashes={}
    for name in sorted(NAMES):
        with z.open(prefix+name) as stream:
            hashes[name]=hashlib.file_digest(stream,"sha256").hexdigest()
    manifest="".join(f"{hashes[k]}  {k}\n" for k in sorted(hashes)).encode("ascii")
    require(z.read(prefix+"SHA256SUMS")==manifest,"inner manifest")
    impl=json.loads(z.read(prefix+"implementation.json"))
    paths={"runner_sha256":Path(prior.__file__),"policy_sha256":Path(p.__file__),
           "runtime_lock_sha256":HERE.parent/"cneh_exp_01"/"bnsyn_integration_contract.json"}
    require(all(impl[k]==e.sha_file(path) for k,path in paths.items()),"parent implementation drift")
    require(hashes["preregistration.md"]==e.sha_file(Path(prior.__file__).parent/"PREREGISTRATION.md"),"parent protocol drift")
    require(json.loads(z.read(prefix+"certificate.json"))==p.certificate(),"parent certificate drift")
    verdict=json.loads(z.read(prefix+"verdict.json"))
    worlds=json.loads(z.read(prefix+"worlds.json"))
    require(verdict["all_instrument_checks_passed"] is True and verdict["valid_worlds"]==16
            and verdict["exact_emulator_equal_worlds"]==16 and verdict["episodes"]==80,"parent validity")
    require(len(worlds)==len(prior.SEEDS) and {w["seed"] for w in worlds}==set(prior.SEEDS),"world roster")
    for w in worlds:
        require(w["valid"] is True and w["exact_emulator_equal"] is True and
                w["schedule"]==[list(x) for x in prior.world(w["seed"])["schedule"]],"world integrity")
    return hashes,{w["seed"]:w for w in worlds},verdict


def numeric_rows(ep):
    rows=ep["trace"]
    require(ep["valid"] is True and len(rows)==d.STEPS+1 and [x["tick"] for x in rows]==list(range(d.STEPS+1)),"episode roster")
    p.audit_tape(rows,ep["arm"])
    schedule=dict(prior.world(ep["seed"])["schedule"])
    tape=d.sensor_tape(ep["seed"])
    prev=None
    data=[]
    used=0
    mode=0
    for t,row in enumerate(rows):
        gaba=tuple(float.fromhex(x) for x in row["true_gaba"])
        bits=tuple(row["true_bits"])
        require(len(gaba)==len(d.B) and all(math.isfinite(v) and v>=0 for v in gaba),"invalid true conductance")
        require(len(bits)==8 and all(type(v) is int and v in (0,1) for v in bits),"invalid source bits")
        noise,erased=tape[t]
        obs=d.public_observation(t,gaba,bits,noise,erased)
        require(d.obs_record(obs)=={k:row[k] for k in ("tick","observed_gaba","observed_bits")}
                and g.hx(noise)==row["noise"] and list(erased)==row["erasures"],"sensor tape mismatch")
        filter0=row["policy"]["filter"]
        candidates=tuple(filter0["candidates"])
        stamps=filter0["exclusion"]
        require(len(stamps)==4 and candidates and tuple(i for i,x in enumerate(stamps) if x is None)==candidates,"exclusion semantics")
        require(all(x is None or type(x) is int and 0<=x<=t and t-x<400 for x in stamps),"expired exclusion retained")
        if t:
            require(prev is not None and row["transition_mode"]==mode,"transition-mode truth")
            old_g,old_bits,old_obs=prev
            n=sum(q.MODES[mode][j]*sum(old_bits[j*4:j*4+4]) for j in range(2))
            require(max(abs(y-q.DECAY*(x+.5*n)) for x,y in zip(old_g,gaba,strict=True))<=1e-9,"native recurrence")
            residual=q.observed_residual(old_obs.gaba,obs.gaba)
            observed=q.support(d.ALL,old_obs.bits,residual)
            complete=q.support(d.ALL,old_bits,residual)
            require(mode in complete and set(complete)<=set(observed) and list(observed)==filter0["instant"],"support audit")
            value=math.fsum(gaba)/len(gaba)
            singleton=len(candidates)==1
            data.append({"tick":t,"mode":mode,"g":value,"band":.4<=value<=.6,
                         "correct":candidates==(mode,),"stale":mode not in candidates,
                         "ambiguous":len(candidates)>1,"observed":s.mask(observed),
                         "complete":s.mask(complete),"source_spike":any(old_bits),"arrival":n,
                         "age_bin":s.age_bin([x for x in stamps if x is not None],t) if singleton else None,
                         "stale_singleton":singleton and mode not in candidates})
        else:
            require(row["transition_mode"] is None,"initial transition")
        if t in schedule:
            mode=schedule[t]
        require(row["next_mode"]==mode,"next-mode truth")
        if t<d.STEPS:
            group=row["group"]
            require(group is None or type(group) is int and group in (0,1),"invalid group")
            require(row["source_inputs_pA"]==[500. if group==j else 0. for j in range(2)]
                    and row["direct_B_pA"]==300. and row["applied_gain"]==1.,"archived current envelope")
            used+=group is not None
            require(row["cumulative_stim_ticks"]==used,"cumulative effort")
            if (t+1)%p.BLOCK==0:
                require(used==(t+1)//p.BLOCK*p.ON,"block budget")
        prev=gaba,bits,obs
    require(used==1600 and ep["source_current_l1_pA_ticks"]==3200000 and len(data)==d.STEPS,"episode effort")
    p.certify_band([r["band"] for r in data])
    return data


def reduce_episode(ep):
    data=numeric_rows(ep)
    schedule=prior.world(ep["seed"])["schedule"]
    segments=[]
    events=[]
    if schedule:
        segments.append(("NOMINAL_PRE_SWITCH",data[:schedule[0][0]]))
        for i,(tau,mode) in enumerate(schedule):
            end=schedule[i+1][0] if i+1<len(schedule) else d.STEPS
            block=data[tau:end]
            require(all(r["mode"]==mode for r in block),"segment truth")
            segments.append(("OOD_DISCONNECTED" if mode==3 else "OOD_REACHABLE",block))
            events.append(s.boundary(block,tau,end))
    else:
        segments=[("NO_CHANGE",data)]
    require(sum(len(r) for _,r in segments)==d.STEPS,"segment coverage")
    windows,coverage=s.segment_windows(segments,data if schedule else [])
    ages={}
    for name,block in segments:
        for row in block:
            if row["age_bin"] is None:
                continue
            k=f"{name}/{row['age_bin']}"
            cell=ages.setdefault(k,{"correct":0,"stale":0})
            cell["stale" if row["stale_singleton"] else "correct"]+=1
    # Recompute original endpoints as a semantic cross-check, not a new estimator.
    checks=events if schedule else [s.boundary(data,0,d.STEPS)]
    for evt,original in zip(checks,ep["segments"],strict=True):
        require((evt["I20_latency_ticks"] is not None)==original["I20"]
                and evt["I20_latency_ticks"]==original["I20_latency"]
                and (None if evt["mode"]==3 else evt["J10_latency_ticks"] is not None)==original["J10"]
                and evt["J10_latency_ticks"]==original["J10_latency"],"original segment endpoint mismatch")
    return {"seed":ep["seed"],"arm":ep["arm"],"windows":windows,"coverage":coverage,"ages":ages,"switches":events,
            "episode_min_g":min(r["g"] for r in data),"episode_max_g":max(r["g"] for r in data),
            "episode_max_band_run":s.longest([r["band"] for r in data])}


def reduce_all(episodes):
    arms={arm:[row for row in episodes if row["arm"]==arm] for arm in p.ARMS}
    require(all(len(rows)==16 for rows in arms.values()),"arm roster")
    def ages(rows):
        out={}
        for row in rows:
            for key,cell in row["ages"].items():
                v=out.setdefault(key,{"correct":0,"stale":0})
                for field in v:
                    v[field]+=cell[field]
        return out
    def coverage(rows):
        out={}
        for row in rows:
            for key,cell in row["coverage"].items():
                v=out.setdefault(key,{k:0 for k in cell})
                for field in v:
                    v[field]+=cell[field]
        return out
    results={}
    for arm in UNIQUE:
        ood=[r for r in arms[arm] if r["seed"]<90101]
        controls=[r for r in arms[arm] if r["seed"]>=90101]
        results[arm]={"ood":s.summarize_arm(ood),"no_change":s.summarize_arm(controls),
                      "ood_ages":ages(ood),"no_change_ages":ages(controls),
                      "ood_coverage":coverage(ood),"no_change_coverage":coverage(controls)}
    contrasts={}
    dual=[r for r in arms["DUAL"] if r["seed"]<90101]
    for arm in UNIQUE[1:]:
        other=[r for r in arms[arm] if r["seed"]<90101]
        pairs=s.paired_contrasts(dual,other)
        contrasts[f"DUAL_MINUS_{arm}"]={"metrics":pairs,"phase_reversals":s.phase_reversals(pairs),
                 "pooled_equal_world_reversals":[{"scale":k,"metric":f,**v}
                      for k,m in pairs.items() for f,v in m.items() if v.get("sign_reversal")]}
    return results,contrasts


def audit(archive):
    require(archive.is_file() and not archive.is_symlink() and e.sha_file(archive)==ARCHIVE_SHA,"archive hash")
    seen=set()
    pairs={}
    emulator={}
    output=[]
    with zipfile.ZipFile(archive) as z:
        hashes,worlds,verdict=authenticate(z)
        with z.open("cneh05/episodes.json.gz") as zipped,gzip.GzipFile(fileobj=zipped) as raw,io.TextIOWrapper(raw,encoding="utf-8") as stream:
            for ep in stream_array(stream):
                seed,arm=ep["seed"],ep["arm"]
                key=(seed,arm)
                require(seed in prior.SEEDS and arm in p.ARMS and key not in seen,"episode roster")
                seen.add(key)
                rows=ep["trace"]
                require({k:v for k,v in ep.items() if k not in ("trace","seed","arm")}==worlds[seed]["endpoints"][arm],"archived endpoints")
                signature=pinned.sha(pinned.canonical([rows[0]["state_sha256"],[(r["rng_sha256"],r["noise"],r["erasures"]) for r in rows]]))
                require(seed not in pairs or pairs[seed]==signature,"paired initial/exogenous tape")
                pairs[seed]=signature
                if arm in ("DUAL","EXACT_EMULATOR"):
                    digest=pinned.sha(pinned.canonical({k:v for k,v in ep.items() if k!="arm"}))
                    require(seed not in emulator or emulator[seed]==digest,"exact emulator mismatch")
                    emulator[seed]=digest
                output.append(reduce_episode(ep))
    require(seen==set(itertools.product(prior.SEEDS,p.ARMS)) and len(emulator)==16 and len(output)==80,"complete roster")
    by={(x["seed"],x["arm"]):x for x in output}
    require(all({k:v for k,v in by[seed,"DUAL"].items() if k!="arm"}==
                {k:v for k,v in by[seed,"EXACT_EMULATOR"].items() if k!="arm"} for seed in prior.SEEDS),"diagnostic emulator mismatch")
    arms,contrasts=reduce_all(output)
    return {"experiment":"CNEH-EXP-05M","authority":"RETROSPECTIVE_MULTISCALE_DIAGNOSTIC_NOT_FRACTAL_PROOF",
            "all_instrument_checks_passed":True,"scientific_promotion_authorized":False,
            "external_replication":"NOT_TESTED","source_archive_sha256":ARCHIVE_SHA,"source_artifact":14890028886,
            "source_head":SOURCE_HEAD,"source_file_sha256":hashes,"protocol_sha256":e.sha_file(HERE/"PROTOCOL.md"),
            "implementation_sha256":{x.name:e.sha_file(x) for x in (Path(__file__),Path(s.__file__))},
            "worlds":16,"episodes":80,"unique_arms":4,"widths_ticks":list(s.WIDTHS),
            "arm_summary":arms,"contrasts":contrasts,"per_world":output}


def compact(report):
    keys=[f"SEGMENT/OOD_REACHABLE/{w}/0" for w in s.WIDTHS]
    fields=("raw_mae_nS","smoothed_abs_error_nS","cancellation_gap_nS","raw_band_fraction","mean_g_in_band",
            "joint_fraction","stale_fraction","observed_singleton","complete_singleton","false_cooccurrence")
    out={}
    for arm,row in report["arm_summary"].items():
        out[arm]={k:{f:x["equal_world_mean"] for f,x in row["ood"][k].items() if f in fields}
                  for k in keys if k in row["ood"]}
    return {"worlds":report["worlds"],"episodes":report["episodes"],"ood_reachable_scale_curves":out,
            "contrast_reversal_counts":{k:{"phase":len(x["phase_reversals"]),"pooled_vs_equal_world":len(x["pooled_equal_world_reversals"])}
                                        for k,x in report["contrasts"].items()}}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--archive",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--verify",action="store_true")
    args=ap.parse_args()
    if not args.verify and (args.out.exists() or args.out.is_symlink()):
        raise FileExistsError("immutable output")
    report=audit(args.archive)
    files={"report.json":pinned.canonical(report)}
    if not args.verify:
        parent.write_bundle(args.out,files)
    parent.verify_payload(args.out,files)
    print(pinned.canonical(compact(report)).decode().strip())


if __name__=="__main__":
    main()
