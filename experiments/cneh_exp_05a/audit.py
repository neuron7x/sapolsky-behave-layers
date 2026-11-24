"""Authenticate sealed EXP05, replay all native menu branches, aggregate shards."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib
import io
import itertools
import json
import math
import zipfile
from fractions import Fraction
from pathlib import Path

from experiments.cneh_exp_04c import qualification as q
from experiments.cneh_exp_04d import run as d
from experiments.cneh_exp_04e import audit as e
from experiments.cneh_exp_04f import policy as f
from experiments.cneh_exp_05 import policy as p,run as prior
from experiments.cneh_exp_05a import bounds as b,counterfactual as c

HERE=Path(__file__).resolve().parent
ARCHIVE_SHA="db78569d633a4fd1ae5649ab02e53a86b48e97f0317b45a849a56cd73e993ea8"
SOURCE_HEAD="8c9b71f366af32fdfc5ffd8618198b4fe22af244"
NAMES={"certificate.json","episodes.json.gz","implementation.json","preregistration.md","verdict.json","worlds.json"}
pinned,parent,neural=d.pinned,d.parent,d.neural
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
        require(bool(buf),"truncated array")
        if buf.startswith("]"):
            require(first or not buf.startswith(",]"),"invalid array closure")
            buf=buf[1:]
            require(not buf.strip() and not stream.read().strip(),"trailing archive data")
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


def authenticate(z: zipfile.ZipFile) -> tuple[dict,list,dict]:
    prefix="cneh05/"
    names=[i.filename for i in z.infolist() if not i.is_dir()]
    require(len(names)==len(set(names)) and set(names)=={prefix+x for x in NAMES|{"SHA256SUMS"}}|{"cneh05-install.json"},"archive member roster")
    hashes={}
    for name in sorted(NAMES):
        with z.open(prefix+name) as stream:
            hashes[name]=hashlib.file_digest(stream,"sha256").hexdigest()
    manifest="".join(f"{hashes[k]}  {k}\n" for k in sorted(hashes)).encode("ascii")
    require(z.read(prefix+"SHA256SUMS")==manifest,"inner SHA256 mismatch")
    impl=json.loads(z.read(prefix+"implementation.json"))
    paths={"runner_sha256":Path(prior.__file__),"policy_sha256":Path(p.__file__),
           "runtime_lock_sha256":HERE.parent/"cneh_exp_01"/"bnsyn_integration_contract.json"}
    require(all(impl[k]==e.sha_file(path) for k,path in paths.items()),"original implementation mismatch")
    require(hashes["preregistration.md"]==e.sha_file(Path(prior.__file__).parent/"PREREGISTRATION.md"),"parent protocol mismatch")
    require(json.loads(z.read(prefix+"certificate.json"))==p.certificate(),"parent certificate mismatch")
    verdict=json.loads(z.read(prefix+"verdict.json"))
    worlds=json.loads(z.read(prefix+"worlds.json"))
    require(verdict["all_instrument_checks_passed"] is True and verdict["valid_worlds"]==16
            and verdict["exact_emulator_equal_worlds"]==16 and verdict["episodes"]==80,"parent instrument not valid")
    require(len(worlds)==len(prior.SEEDS) and {w["seed"] for w in worlds}==set(prior.SEEDS),"world roster")
    for w in worlds:
        require(w["valid"] is True and w["exact_emulator_equal"] is True and
                w["schedule"]==[list(x) for x in prior.world(w["seed"])["schedule"]],"parent world integrity")
    return hashes,worlds,verdict


def certificate() -> dict:
    result=b.bounds(d.STEPS)
    coarse,fine=(result["grids"][key] for key in ("1/100","1/200"))
    require(all(Fraction(fine["width_nS"])*a>=Fraction(coarse["width_nS"])*z
                for a,z in zip(fine["minimum_loss_units"],coarse["minimum_loss_units"],strict=True)),
            "grid refinement lowered conservative lower bound")
    require(all(a<=z for a,z in zip(fine["maximum_occupancy"],coarse["maximum_occupancy"],strict=True)),
            "grid refinement increased conservative upper bound")
    return result


def episode(ep: dict,rt: dict,cert: dict) -> dict:
    seed,arm,rows=ep["seed"],ep["arm"],ep["trace"]
    require(ep["valid"] is True and len(rows)==d.STEPS+1 and ep["source_current_l1_pA_ticks"]==3200000,"invalid parent episode")
    p.audit_tape(rows,arm)
    np,network,config=rt["np"],rt["network"],rt["config"]
    net=network.Network(network.NetworkParams(N=32,frac_inhib=.25,p_conn=0.),
                        config.AdExParams(),config.SynapseParams(),config.CriticalityParams(),
                        dt_ms=.1,rng=np.random.default_rng(seed),backend="reference")
    require(net.nE==24 and net.nI==8 and not net._use_torch and net.syn.tau_GABAA_ms==6.,"runtime boundary")
    connectivity=importlib.import_module("bnsyn.connectivity").SparseConnectivity
    neural.apply_mode(net,0,np,connectivity)
    filt=f.Policy(f.ARMS[0])
    tape=d.sensor_tape(seed)
    gaba,bits=c.state_values(net)
    filt.observe(d.public_observation(0,gaba,bits,*tape[0]))
    c.verify_selected(net,np,rows[0],filt)
    schedule=dict(prior.world(seed)["schedule"])
    actual_values=[math.fsum(float.fromhex(x) for x in row["true_gaba"])/len(d.B) for row in rows[1:]]
    b.trace_bounds(actual_values,cert)
    blocks=[]
    for start in range(0,d.STEPS,p.BLOCK):
        block,net,filt=c.evaluate_block(net,filt,rows,start,arm,schedule,rt,tape,cert)
        blocks.append(block)
    c.verify_selected(net,np,rows[-1],filt)
    require(len(blocks)==10 and all(len(x["plans"])==8 for x in blocks),"incomplete block roster")
    return {"seed":seed,"arm":arm,"valid":True,"blocks":blocks,
            "selected_replay_samples":d.STEPS+1,"native_rollouts":80,"native_transitions":80*p.BLOCK}


def reduce_blocks(blocks: list[dict]) -> dict:
    require(bool(blocks),"empty block cohort")
    plans=[plan for block in blocks for plan in block["plans"]]
    selected=[next(x for x in block["plans"] if x["plan"]==block["selected"]) for block in blocks]
    def mean(xs):
        return math.fsum(xs)/len(xs) if xs else None
    fields=("selected_shadow_interval_regret","selected_native_endpoint_regret","selected_native_interval_regret",
            "selected_observed_pair_regret","selected_physical_mae_regret_nS","selected_physical_band_regret")
    regrets={}
    for key in fields:
        values=[x[key] for x in blocks if x[key] is not None]
        regrets[key]={"eligible":len(values),"mean":mean(values),"positive":sum(v>c.TOL for v in values),
                      "maximum":max(values) if values else None}
    mode_reports=[x for plan in plans for x in plan["shadow_cost"]["mode_reports"]]
    witness=None
    for block in blocks:
        for plan in block["plans"]:
            for mode in plan["shadow_cost"]["mode_reports"]:
                if witness is None or mode["excess"]>witness["excess"]:
                    witness={"seed":block["seed"],"start":block["start"],"plan":plan["plan"],
                             "initial_interval_nS":block["initial_interval_nS"],**mode}
    ranks={name:{field:sum(x[name][field] for x in blocks) for field in ("strict_pairs","inversions","tie_disagreements")}
           for name in ("rank_shadow_vs_native","rank_info_proxy_vs_observed")}
    return {"blocks":len(blocks),"plans":len(plans),"shadow_mode_cases":len(mode_reports),
            "interior_excess_cases":sum(x["excess"]>c.TOL for x in mode_reports),
            "blocks_with_interior_excess":sum(x["max_interior_excess"]>c.TOL for x in blocks),
            "selected_plans_with_interval_excess":sum(x["selected_interval_excess"]>c.TOL for x in blocks),
            "interval_minimizer_changes":sum(x["shadow_endpoint_best"]!=x["shadow_interval_best"] for x in blocks),
            "native_minimizer_changes":sum(x["shadow_endpoint_best"]!=x["native_endpoint_best"] for x in blocks),
            "observed_pair_minimizer_changes":sum(x["shadow_endpoint_best"]!=x["observed_pair_best"] for x in blocks),
            "max_interval_witness":witness,"stale_at_action_blocks":sum(x["stale_at_action"] for x in blocks),
            "selected_mean_stale_fraction":mean([x["stale_fraction"] for x in selected]),
            "selected_mean_correct_fraction":mean([x["correct_fraction"] for x in selected]),
            "mean_source_count_mismatch_ticks":mean([x["source_count_mismatch_ticks"] for x in plans]),
            "mean_source_bit_errors":mean([x["source_bit_errors"] for x in plans]),
            "mean_shadow_proxy_abs_error_vs_observed":mean([abs(x["shadow_info"]["proxy"]-x["native_info"]["observed_directed_elimination"]) for x in plans]),
            "mean_native_proxy_abs_error_vs_observed":mean([abs(x["native_info"]["proxy"]-x["native_info"]["observed_directed_elimination"]) for x in plans]),
            "mean_native_observed_pair_elimination":mean([x["native_info"]["observed_directed_elimination"] for x in plans]),
            "mean_native_full_pair_elimination":mean([x["native_info"]["full_directed_elimination"] for x in plans]),
            "ranking":ranks,"regret":regrets}


def summarize(episodes: list[dict]) -> dict:
    def blocks(rows):
        return [{**b0,"seed":ep["seed"]} for ep in rows for b0 in ep["blocks"]]
    ood=[ep for ep in episodes if ep["seed"]<90101]
    controls=[ep for ep in episodes if ep["seed"]>=90101]
    require(len(ood)==12 and len(controls)==4,"cohort roster")
    return {"ood":reduce_blocks(blocks(ood)),"no_change":reduce_blocks(blocks(controls)),
            "per_world":[{"seed":ep["seed"],**reduce_blocks(blocks([ep]))} for ep in episodes]}


def first_episode_difference(archived: dict,replayed: dict) -> dict:
    """Exact first difference; a diagnostic, never an alternative acceptance gate."""
    if archived==replayed:
        return {"exact_match":True,"first_different_tick":None}
    ar,rr=archived.get("trace",[]),replayed.get("trace",[])
    differing_top=sorted(k for k in set(archived)|set(replayed)
                         if k!="trace" and archived.get(k)!=replayed.get(k))
    for left,right in zip(ar,rr):
        if left!=right:
            keys=sorted(k for k in set(left)|set(right) if left.get(k)!=right.get(k))
            digests={k:{"archive":left.get(k),"replay":right.get(k)}
                     for k in ("state_sha256","rng_sha256","group","next_mode","transition_mode")
                     if k in keys}
            return {"exact_match":False,"first_different_tick":left.get("tick"),
                    "first_different_fields":keys,"digest_or_action_difference":digests,
                    "archived_rows":len(ar),"replayed_rows":len(rr),
                    "different_top_level_fields":differing_top}
    return {"exact_match":False,"first_different_tick":None,
            "archived_rows":len(ar),"replayed_rows":len(rr),
            "different_top_level_fields":differing_top}


def forensic_reference(ep: dict,rt: dict) -> dict:
    """Replay unmodified parent without any counterfactual cloning, after a failure."""
    try:
        reference=prior.episode(prior.world(ep["seed"]),ep["arm"],rt,d.sensor_tape(ep["seed"]))
        return {"reference_valid":reference.get("valid") is True,
                "reference_failure":reference.get("failure"),
                "archive_digest":pinned.sha(pinned.canonical(ep)),
                "reference_digest":pinned.sha(pinned.canonical(reference)),
                "comparison":first_episode_difference(ep,reference)}
    except (ValueError,RuntimeError,ArithmeticError,TypeError) as exc:
        return {"reference_valid":False,"reference_exception":str(exc)}


def run_shard(archive: Path,source: Path,arm: str) -> dict:
    require(archive.is_file() and not archive.is_symlink() and e.sha_file(archive)==ARCHIVE_SHA,"archive digest mismatch")
    lock_path=HERE.parent/"cneh_exp_01"/"bnsyn_integration_contract.json"
    lock=pinned.strict_json(lock_path.read_bytes())
    require(lock["source"]["commit"]=="c1de425ce4ece362e7f2feb2d9f24da5d3231014","native runtime drift")
    before=pinned.validate_source(source,lock)
    rt=pinned.load_runtime(source,lock)
    cert=certificate()
    episodes=[]
    seen=set()
    emulator={}
    paired={}
    with zipfile.ZipFile(archive) as z:
        hashes,worlds,verdict=authenticate(z)
        by_world={w["seed"]:w for w in worlds}
        with z.open("cneh05/episodes.json.gz") as zipped,gzip.GzipFile(fileobj=zipped) as raw,io.TextIOWrapper(raw,encoding="utf-8") as stream:
            for ep in stream_array(stream):
                seed,name=ep["seed"],ep["arm"]
                key=(seed,name)
                require(seed in prior.SEEDS and name in p.ARMS and key not in seen and ep["valid"] is True,"episode roster")
                seen.add(key)
                rows=ep["trace"]
                require(len(rows)==d.STEPS+1 and ep["source_current_l1_pA_ticks"]==3200000,"invalid episode length or budget")
                require({k:v for k,v in ep.items() if k not in ("trace","seed","arm")}==by_world[seed]["endpoints"][name],"parent endpoint mismatch")
                signature=pinned.sha(pinned.canonical([rows[0]["state_sha256"],
                     [(x["rng_sha256"],x["noise"],x["erasures"]) for x in rows]]))
                require(seed not in paired or paired[seed]==signature,"archive paired tape mismatch")
                paired[seed]=signature
                if name in ("DUAL","EXACT_EMULATOR"):
                    digest=pinned.sha(pinned.canonical({k:v for k,v in ep.items() if k!="arm"}))
                    require(seed not in emulator or emulator[seed]==digest,"archive exact emulator mismatch")
                    emulator[seed]=digest
                if name!=arm:
                    continue
                try:
                    episodes.append(episode(ep,rt,cert))
                except (ValueError,RuntimeError,ArithmeticError,TypeError) as exc:
                    episodes.append({"seed":seed,"arm":arm,"valid":False,"failure":str(exc),
                                     "unmodified_parent_replay":forensic_reference(ep,rt)})
        require(seen==set(itertools.product(prior.SEEDS,p.ARMS)) and len(emulator)==16,"incomplete archive roster")
    require(pinned.validate_source(source,lock)==before,"native source changed")
    passed=len(episodes)==len(prior.SEEDS) and all(x["valid"] for x in episodes)
    report={"experiment":"CNEH-EXP-05A","authority":"RETROSPECTIVE_FINITE_MENU_COUNTERFACTUAL_ONLY",
            "arm":arm,"source_head":SOURCE_HEAD,"source_artifact":14890028886,"source_archive_sha256":ARCHIVE_SHA,
            "source_file_sha256":hashes,"protocol_sha256":e.sha_file(HERE/"PROTOCOL.md"),
            "implementation_sha256":{path.name:e.sha_file(path) for path in (Path(__file__),Path(b.__file__),Path(c.__file__))},
            "all_instrument_checks_passed":passed,"scientific_promotion_authorized":False,
            "certificate":cert,"episodes":episodes}
    if passed:
        report["summary"]=summarize(episodes)
        report["native_rollouts"]=sum(x["native_rollouts"] for x in episodes)
        report["native_transitions"]=sum(x["native_transitions"] for x in episodes)
    else:
        report["aggregate_status"]="BLOCKED_NO_SURVIVOR_AVERAGING"
    return report


def aggregate(root: Path) -> dict:
    paths={arm:root/f"cneh-exp-05a-shard-{arm}" for arm in c.UNIQUE}
    require(root.is_dir() and {x.name for x in root.iterdir()}=={x.name for x in paths.values()},"aggregate shard roster")
    reports={}
    digests={}
    for arm,path in paths.items():
        require(path.is_dir() and not path.is_symlink() and {x.name for x in path.iterdir()}=={"report.json","SHA256SUMS"},"shard bundle roster")
        raw=(path/"report.json").read_bytes()
        sha=pinned.sha(raw)
        require((path/"SHA256SUMS").read_bytes()==f"{sha}  report.json\n".encode("ascii"),"shard checksum")
        row=json.loads(raw)
        require(row["arm"]==arm and row["all_instrument_checks_passed"] is True and row["source_archive_sha256"]==ARCHIVE_SHA
                and row["native_rollouts"]==1280 and row["native_transitions"]==409600,"invalid shard")
        require({x["seed"] for x in row["episodes"]}==set(prior.SEEDS) and
                all(x["valid"] and x["arm"]==arm and len(x["blocks"])==10 for x in row["episodes"]),"shard episode roster")
        require(row["summary"]==summarize(row["episodes"]),"shard summary mismatch")
        reports[arm]=row
        digests[arm]=sha
    ref=reports[c.UNIQUE[0]]
    for row in reports.values():
        require(all(row[k]==ref[k] for k in ("certificate","source_file_sha256","protocol_sha256","implementation_sha256","source_head")),"shard lineage mismatch")
    all_blocks=[{**block,"seed":ep["seed"]} for row in reports.values() for ep in row["episodes"] for block in ep["blocks"]]
    return {"experiment":"CNEH-EXP-05A","authority":"SEALED_RETROSPECTIVE_FINITE_MENU_DIAGNOSTIC",
            "all_instrument_checks_passed":True,"scientific_promotion_authorized":False,"external_replication":"NOT_TESTED",
            "source_head":SOURCE_HEAD,"source_archive_sha256":ARCHIVE_SHA,"source_artifact":14890028886,
            "source_file_sha256":ref["source_file_sha256"],"protocol_sha256":ref["protocol_sha256"],
            "implementation_sha256":ref["implementation_sha256"],"shard_sha256":digests,
            "native_rollouts":sum(x["native_rollouts"] for x in reports.values()),
            "native_transitions":sum(x["native_transitions"] for x in reports.values()),
            "worlds":16,"unique_arms":len(reports),"decision_blocks":len(all_blocks),
            "reachability_bounds":{key:value["horizons"] for key,value in ref["certificate"]["grids"].items()},
            "overall_ood":reduce_blocks([x for x in all_blocks if x["seed"]<90101]),
            "arm_summary":{arm:row["summary"] for arm,row in reports.items()}}


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive",type=Path)
    parser.add_argument("--source",type=Path)
    parser.add_argument("--arm",choices=c.UNIQUE)
    parser.add_argument("--shards",type=Path)
    parser.add_argument("--out",type=Path,required=True)
    parser.add_argument("--verify",action="store_true")
    args=parser.parse_args()
    require((args.shards is not None) != (args.archive is not None and args.source is not None and args.arm is not None),"choose shard or aggregate")
    if not args.verify and (args.out.exists() or args.out.is_symlink()):
        raise FileExistsError("immutable output")
    report=aggregate(args.shards) if args.shards is not None else run_shard(args.archive,args.source,args.arm)
    files={"report.json":pinned.canonical(report)}
    if not args.verify:
        parent.write_bundle(args.out,files)
    parent.verify_payload(args.out,files)
    if args.shards is not None:
        print(pinned.canonical({k:v for k,v in report.items() if k!="arm_summary"}).decode().strip())
    else:
        print(pinned.canonical({k:v for k,v in report.items() if k not in ("episodes","certificate","summary")}).decode().strip())
        if report["all_instrument_checks_passed"]:
            print(pinned.canonical({"arm":report["arm"],"ood":report["summary"]["ood"],"no_change":report["summary"]["no_change"]}).decode().strip())
        else:
            print(pinned.canonical({"invalid_episodes":[x for x in report["episodes"] if not x["valid"]]}).decode().strip())
    raise SystemExit(0 if report["all_instrument_checks_passed"] else 2)


if __name__=="__main__":
    main()
