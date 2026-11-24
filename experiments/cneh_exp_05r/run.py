"""Cross-worker numerical-domain diagnostic; exact mismatch is never rounded away."""
from __future__ import annotations

import argparse
import contextlib
import gzip
import hashlib
import io
import itertools
import json
import math
import os
import platform
import struct
import sys
import zipfile
from pathlib import Path
from unittest.mock import patch

from experiments.cneh_exp_04d import run as d
from experiments.cneh_exp_04e import audit as e
from experiments.cneh_exp_04g import run as g
from experiments.cneh_exp_05 import policy as p,run as prior

HERE=Path(__file__).resolve().parent
ARCHIVE_SHA="db78569d633a4fd1ae5649ab02e53a86b48e97f0317b45a849a56cd73e993ea8"
SEEDS=(90001,90101)
WORKERS=("A","B")
PROFILES=("DEFAULT","BASELINE")
NAMES={"certificate.json","episodes.json.gz","implementation.json","preregistration.md","verdict.json","worlds.json"}
LOCK=HERE.parent/"cneh_exp_01"/"bnsyn_integration_contract.json"
REQUIREMENTS=HERE.parent/"cneh_exp_01"/"bnsyn-requirements.lock"
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
    require(buf.startswith("["),"archive array")
    buf=buf[1:]
    first=True
    while True:
        nonempty()
        require(bool(buf),"truncated array")
        if buf.startswith("]"):
            require(not buf[1:].strip() and not stream.read().strip(),"archive trailing bytes")
            return
        if not first:
            require(buf.startswith(","),"array separator")
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
        require(isinstance(value,dict),"episode object")
        buf=buf[end:]
        first=False
        yield value


def archived_panel(path):
    require(path.is_file() and not path.is_symlink() and e.sha_file(path)==ARCHIVE_SHA,"archive hash")
    prefix="cneh05/"
    found={}
    seen=set()
    with zipfile.ZipFile(path) as z:
        names=[i.filename for i in z.infolist() if not i.is_dir()]
        require(len(names)==len(set(names)) and set(names)=={prefix+x for x in NAMES|{"SHA256SUMS"}}|{"cneh05-install.json"},"archive members")
        hashes={}
        for name in sorted(NAMES):
            with z.open(prefix+name) as stream:
                hashes[name]=hashlib.file_digest(stream,"sha256").hexdigest()
        require(z.read(prefix+"SHA256SUMS")=="".join(f"{hashes[k]}  {k}\n" for k in sorted(hashes)).encode("ascii"),"manifest")
        impl=json.loads(z.read(prefix+"implementation.json"))
        for field,file in {"runner_sha256":Path(prior.__file__),"policy_sha256":Path(p.__file__),"runtime_lock_sha256":LOCK}.items():
            require(impl[field]==e.sha_file(file),"original code drift")
        require(hashes["preregistration.md"]==e.sha_file(Path(prior.__file__).parent/"PREREGISTRATION.md"),"parent protocol")
        verdict=json.loads(z.read(prefix+"verdict.json"))
        require(verdict["all_instrument_checks_passed"] is True and verdict["episodes"]==80 and verdict["valid_worlds"]==16
                and verdict["exact_emulator_equal_worlds"]==16,"parent validity")
        with z.open(prefix+"episodes.json.gz") as zipped,gzip.GzipFile(fileobj=zipped) as raw,io.TextIOWrapper(raw,encoding="utf-8") as stream:
            for ep in stream_array(stream):
                key=(ep["seed"],ep["arm"])
                require(key not in seen and ep["valid"] is True,"archive episode roster")
                seen.add(key)
                if ep["seed"] in SEEDS:
                    require(len(ep["trace"])==d.STEPS+1,"archive sample count")
                    found[key]=ep
    require(seen==set(itertools.product(prior.SEEDS,p.ARMS)) and set(found)==set(itertools.product(SEEDS,p.ARMS)),"archive complete roster")
    return found,hashes


def features(np):
    core=np._core._multiarray_umath
    return {"baseline":list(core.__cpu_baseline__),"dispatch":list(core.__cpu_dispatch__),
            "enabled":{k:bool(v) for k,v in sorted(core.__cpu_features__.items())}}


def optional_features(np):
    f=features(np)
    return sorted(x for x in f["dispatch"] if f["enabled"].get(x,False) and x not in f["baseline"])


def fingerprint(np):
    cpu={}
    path=Path("/proc/cpuinfo")
    if path.is_file():
        first=path.read_text().split("\n\n",1)[0]
        for line in first.splitlines():
            key,sep,value=line.partition(":")
            if sep and key.strip() in ("vendor_id","model name","cpu family","model","stepping","microcode","flags","Features","CPU implementer","CPU part"):
                cpu[key.strip()]=value.strip()
    out=io.StringIO()
    with contextlib.redirect_stdout(out):
        np.show_runtime()
    probes=(-40.,-10.,-2.,-.5,0.,.5,2.,10.,20.)
    x=np.arange(32*32,dtype=np.float64).reshape(32,32)/127.-3.
    y=x.T.copy()
    return {"platform":platform.platform(),"machine":platform.machine(),"libc":list(platform.libc_ver()),
            "python":sys.version,"numpy":np.__version__,"cpu":cpu,"features":features(np),
            "requested_disabled":os.environ.get("NPY_DISABLE_CPU_FEATURES",""),
            "runner_image_os":os.environ.get("ImageOS",""),"runner_image_version":os.environ.get("ImageVersion",""),
            "thread_environment":{k:os.environ.get(k,"") for k in ("OPENBLAS_NUM_THREADS","OMP_NUM_THREADS","MKL_NUM_THREADS","BNSYN_USE_TORCH")},
            "numpy_extension_sha256":e.sha_file(Path(np._core._multiarray_umath.__file__)),
            "numpy_runtime":out.getvalue(),"runtime_lock_sha256":e.sha_file(LOCK),"requirements_sha256":e.sha_file(REQUIREMENTS),
            "math_exp_hex":[math.exp(v).hex() for v in probes],
            "numpy_exp_hex":[float(v).hex() for v in np.exp(np.array(probes,dtype=np.float64))],
            "dense_dot_sha256":pinned.sha(np.dot(x,y).astype(">f8").tobytes(order="C"))}


def capture(net,np):
    def raw(values):
        arr=np.asarray(values,dtype=np.float64)
        require(np.isfinite(arr).all(),"nonfinite captured state")
        return arr.astype(">f8").tobytes(order="C")
    arrays={"V":net.state.V_mV,"w":net.state.w_pA,"g_ampa":net.g_ampa,
            "g_nmda":net.g_nmda,"g_gabaa":net.g_gabaa}
    packed={k:raw(v) for k,v in arrays.items()}
    packed["spikes"]=np.asarray(net.state.spiked,dtype=np.uint8).tobytes()
    packed["gain"]=struct.pack(">d",float(net.gain))
    state=pinned.sha(b"".join(packed[k] for k in ("V","w","g_ampa","g_nmda","g_gabaa","spikes","gain")))
    require(state==parent.physical_state_digest(net,np),"component digest reconstruction")
    parts={k:pinned.sha(v) for k,v in packed.items()}
    for k in ("V","w"):
        parts[k+"_source"]=pinned.sha(raw(arrays[k][list(g.SOURCES)]))
        parts[k+"_receiver"]=pinned.sha(raw(arrays[k][list(d.B)]))
    return {"state_sha256":state,"rng_sha256":pinned.sha(pinned.canonical(net.rng.bit_generator.state)),"parts":parts}


def archive_difference(archived,replayed):
    if archived==replayed:
        return {"exact":True,"first_tick":None,"fields":[],"top_level_fields":[]}
    ar,rr=archived.get("trace",[]),replayed.get("trace",[])
    top=sorted(k for k in set(archived)|set(replayed) if k!="trace" and archived.get(k)!=replayed.get(k))
    for x,y in zip(ar,rr):
        if x!=y:
            fields=sorted(k for k in set(x)|set(y) if x.get(k)!=y.get(k))
            deltas={}
            for k in ("source_V","source_w","true_gaba"):
                if k in fields and isinstance(x.get(k),list) and isinstance(y.get(k),list) and len(x[k])==len(y[k]):
                    deltas[k]=max(abs(float.fromhex(a)-float.fromhex(b)) for a,b in zip(x[k],y[k],strict=True))
            return {"exact":False,"first_tick":x["tick"],"fields":fields,"top_level_fields":top,
                    "archive_rows":len(ar),"replay_rows":len(rr),"known_array_max_abs_delta":deltas,
                    "first_values":{k:{"archive":x.get(k),"replay":y.get(k)} for k in ("state_sha256","rng_sha256","group") if k in fields}}
    return {"exact":False,"first_tick":None,"fields":[],"top_level_fields":top,
            "archive_rows":len(ar),"replay_rows":len(rr)}


def episode(seed,arm,rt,archive):
    w=prior.world(seed)
    tape=d.sensor_tape(seed)
    ref=prior.episode(w,arm,rt,tape)
    require(ref["valid"] is True,"unmodified native episode failed")
    states=[]
    network=rt["network"]
    np=rt["np"]
    native=network.Network.step
    def passive(net,*args,**kwargs):
        if not states:
            states.append(capture(net,np))
        result=native(net,*args,**kwargs)
        states.append(capture(net,np))
        return result
    with patch.object(network.Network,"step",passive):
        instrumented=prior.episode(w,arm,rt,tape)
    require(instrumented==ref and len(states)==d.STEPS+1,"passive instrumentation altered episode")
    for row,state in zip(ref["trace"],states,strict=True):
        require(row["state_sha256"]==state["state_sha256"] and row["rng_sha256"]==state["rng_sha256"],"captured state alignment")
        state["public_policy_sha256"]=pinned.sha(pinned.canonical({k:row.get(k) for k in ("observed_gaba","observed_bits","policy","group","decision")}))
    return {"seed":seed,"arm":arm,"valid":True,"same_worker_passive_exact":True,
            "archive_comparison":archive_difference(archive,ref),"episode_sha256":pinned.sha(pinned.canonical(ref)),
            "states":states,"metrics":{k:v for k,v in ref.items() if k!="trace"}}


def profile_report(source,archive,worker,profile):
    require(worker in WORKERS and profile in PROFILES,"diagnostic roster")
    lock=pinned.strict_json(LOCK.read_bytes())
    require(lock["source"]["commit"]=="c1de425ce4ece362e7f2feb2d9f24da5d3231014","native runtime drift")
    before=pinned.validate_source(source,lock)
    rt=pinned.load_runtime(source,lock)
    fp=fingerprint(rt["np"])
    require(fp["thread_environment"]=={"OPENBLAS_NUM_THREADS":"1","OMP_NUM_THREADS":"1","MKL_NUM_THREADS":"1","BNSYN_USE_TORCH":"0"},"thread boundary")
    require(not fp["requested_disabled"] if profile=="DEFAULT" else not optional_features(rt["np"]),"dispatch profile not realized")
    old,hashes=archived_panel(archive)
    rows=[]
    for seed,arm in itertools.product(SEEDS,p.ARMS):
        try:
            rows.append(episode(seed,arm,rt,old[seed,arm]))
        except (ValueError,RuntimeError,ArithmeticError,TypeError) as exc:
            rows.append({"seed":seed,"arm":arm,"valid":False,"failure":str(exc)})
    by={(x["seed"],x["arm"]):x for x in rows}
    parity=all(by[seed,"DUAL"]["valid"] and by[seed,"EXACT_EMULATOR"]["valid"] and
               by[seed,"DUAL"]["states"]==by[seed,"EXACT_EMULATOR"]["states"] for seed in SEEDS)
    require(pinned.validate_source(source,lock)==before,"native source changed")
    return {"experiment":"CNEH-EXP-05R","authority":"RETROSPECTIVE_NUMERICAL_DIAGNOSTIC_ONLY",
            "worker":worker,"profile":profile,"fingerprint":fp,"source_archive_sha256":ARCHIVE_SHA,
            "source_file_sha256":hashes,"protocol_sha256":e.sha_file(HERE/"PROTOCOL.md"),
            "implementation_sha256":e.sha_file(Path(__file__)),"episodes":rows,"exact_emulator":parity,
            "all_instrument_checks_passed":all(x["valid"] for x in rows) and parity,
            "scientific_promotion_authorized":False}


def compare_states(a,b):
    require(len(a)==len(b)>0,"state roster")
    first=None
    counts={}
    for t,(x,y) in enumerate(zip(a,b,strict=True)):
        require(set(x["parts"])==set(y["parts"]),"component roster")
        diff=sorted(k for k in x["parts"] if x["parts"][k]!=y["parts"][k])
        diff.extend(k for k in ("state_sha256","rng_sha256","public_policy_sha256") if x[k]!=y[k])
        if diff and first is None:
            first={"tick":t,"fields":diff}
        for k in diff:
            counts[k]=counts.get(k,0)+1
    return {"exact":first is None,"first_difference":first,"differing_samples_by_field":counts}


def aggregate(root):
    labels=[(w,p0) for w in WORKERS for p0 in PROFILES]
    expected={f"cneh-exp-05r-{w}-{p0}" for w,p0 in labels}
    require(root.is_dir() and {x.name for x in root.iterdir()}==expected,"profile artifact roster")
    reports={}
    digests={}
    for w,p0 in labels:
        folder=root/f"cneh-exp-05r-{w}-{p0}"
        require({x.name for x in folder.iterdir()}=={"report.json.gz","SHA256SUMS"},"profile file roster")
        raw=(folder/"report.json.gz").read_bytes()
        digest=pinned.sha(raw)
        require((folder/"SHA256SUMS").read_bytes()==f"{digest}  report.json.gz\n".encode("ascii"),"profile checksum")
        row=json.loads(gzip.decompress(raw))
        require(row["worker"]==w and row["profile"]==p0 and row["all_instrument_checks_passed"] is True and
                row["source_archive_sha256"]==ARCHIVE_SHA and row["exact_emulator"] is True,"invalid profile")
        require(len(row["episodes"])==len(SEEDS)*len(p.ARMS) and
                {(x["seed"],x["arm"]) for x in row["episodes"]}==set(itertools.product(SEEDS,p.ARMS)),"profile episode roster")
        reports[w,p0]=row
        digests[f"{w}/{p0}"]=digest
    ref=reports["A","DEFAULT"]
    require(all(all(row[k]==ref[k] for k in ("source_file_sha256","protocol_sha256","implementation_sha256")) for row in reports.values()),"profile lineage")
    pairs=[]
    for a,b in itertools.combinations(labels,2):
        left,right=reports[a],reports[b]
        lm={(x["seed"],x["arm"]):x for x in left["episodes"]}
        rm={(x["seed"],x["arm"]):x for x in right["episodes"]}
        comparisons=[]
        for key in sorted(lm):
            x,y=lm[key],rm[key]
            comparisons.append({"seed":key[0],"arm":key[1],"episode_exact":x["episode_sha256"]==y["episode_sha256"],
                                **compare_states(x["states"],y["states"])})
        pairs.append({"left":list(a),"right":list(b),
                      "contrast":"WITHIN_WORKER_DISPATCH" if a[0]==b[0] else "CROSS_WORKER_FIXED_PROFILE" if a[1]==b[1] else "BOTH_FACTORS",
                      "cpu_fingerprint_equal":left["fingerprint"]["cpu"]==right["fingerprint"]["cpu"],
                      "feature_fingerprint_equal":left["fingerprint"]["features"]==right["fingerprint"]["features"],
                      "math_exp_equal":left["fingerprint"]["math_exp_hex"]==right["fingerprint"]["math_exp_hex"],
                      "numpy_exp_equal":left["fingerprint"]["numpy_exp_hex"]==right["fingerprint"]["numpy_exp_hex"],
                      "dense_dot_equal":left["fingerprint"]["dense_dot_sha256"]==right["fingerprint"]["dense_dot_sha256"],
                      "episodes":comparisons})
    return {"experiment":"CNEH-EXP-05R","authority":"RETROSPECTIVE_NUMERICAL_DIAGNOSTIC_ONLY",
            "all_instrument_checks_passed":True,"scientific_promotion_authorized":False,
            "source_archive_sha256":ARCHIVE_SHA,"profile_sha256":digests,
            "profiles":{f"{w}/{p0}":{"fingerprint":row["fingerprint"],"archive_exact_episodes":sum(x["archive_comparison"]["exact"] for x in row["episodes"]),
                       "archive_comparisons":[{"seed":x["seed"],"arm":x["arm"],**x["archive_comparison"]} for x in row["episodes"]]}
                       for (w,p0),row in reports.items()},"pairwise":pairs}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source",type=Path)
    ap.add_argument("--archive",type=Path)
    ap.add_argument("--worker",choices=WORKERS)
    ap.add_argument("--profile",choices=PROFILES)
    ap.add_argument("--profiles",type=Path)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--verify",action="store_true")
    args=ap.parse_args()
    require((args.profiles is not None)!=(args.source is not None and args.archive is not None and args.worker is not None and args.profile is not None),"choose profile or aggregate")
    if not args.verify and (args.out.exists() or args.out.is_symlink()):
        raise FileExistsError("immutable output")
    report=aggregate(args.profiles) if args.profiles is not None else profile_report(args.source,args.archive,args.worker,args.profile)
    files={"report.json.gz":gzip.compress(pinned.canonical(report),mtime=0)}
    if not args.verify:
        parent.write_bundle(args.out,files)
    parent.verify_payload(args.out,files)
    if args.profiles is not None:
        print(pinned.canonical({"archive_exact":{k:x["archive_exact_episodes"] for k,x in report["profiles"].items()},
                 "pairwise":[{"left":x["left"],"right":x["right"],"contrast":x["contrast"],"exact_episodes":sum(y["exact"] for y in x["episodes"]),
                    "first_differences":[y["first_difference"] for y in x["episodes"] if not y["exact"]]} for x in report["pairwise"]]}).decode().strip())
    else:
        print(pinned.canonical({"worker":report["worker"],"profile":report["profile"],
                 "all_instrument_checks_passed":report["all_instrument_checks_passed"],
                 "archive_comparisons":[{k:v for k,v in x.items() if k not in ("states","metrics")} for x in report["episodes"]]}).decode().strip())
    raise SystemExit(0 if report["all_instrument_checks_passed"] else 2)


if __name__=="__main__":
    main()
