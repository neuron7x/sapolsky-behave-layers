"""Sealed causal action-time ambiguity audit. No native state re-materialization."""
from __future__ import annotations

import argparse
import hashlib
import itertools
import math
from pathlib import Path
import shutil
import struct
import tempfile
import zipfile

from experiments.cneh_exp_04c import qualification as q
from experiments.cneh_exp_04d import run as d
from experiments.cneh_exp_05 import policy as p, run as prior
from experiments.cneh_exp_05i import causal as c
from scripts import cneh_evidence_admission as evidence
from scripts import cneh_promotion_gate as promotion

HERE=Path(__file__).resolve().parent
ARCHIVE_ID=14890028886
ARCHIVE_SHA="db78569d633a4fd1ae5649ab02e53a86b48e97f0317b45a849a56cd73e993ea8"
HEAD="8c9b71f366af32fdfc5ffd8618198b4fe22af244"
ARMS=("DUAL","CONTROL_ONLY","INFO_ONLY","FIXED_ALTERNATE")
STRATA=("NOMINAL_PRE_SWITCH","OOD_REACHABLE","OOD_DISCONNECTED","NO_CHANGE")
need=c.need
FIELDS=("ticks","transition_ticks","old_singleton","old_correct_action_singleton","old_wrong_action_singleton",
        "old_excludes_action_truth","old_past_correct_but_action_wrong","old_singleton_full_ambiguous",
        "window_observed_singleton","window_full_singleton","window_full_ambiguous",
        "window_erasure_enlarged","window_observed_past_singleton","window_full_past_singleton",
        "window_past_singleton_action_ambiguous","unrestricted_action_singleton","unrestricted_no_common_group",
        "window_no_common_group","window_full_no_common_group","window_disconnect_possible",
        "stim_ticks","stim_connected","stim_guaranteed","stim_full_guaranteed","stim_unguaranteed",
        "stim_disconnect_possible","no_source_spikes","full_structural_alias","erasure_extra_instant",
        "distinct_arrival_opportunity","instant_observed_singleton","instant_full_singleton")


def empty():
    return dict.fromkeys(FIELDS,0)


def topology_digests():
    # Independent row-major serialization of the frozen 32x24 E and 32x8 I
    # matrices. There are no recurrent inputs to source neurons 24..31.
    result={}
    for mode,(a,b) in enumerate(c.MODES):
        values=[0.]*(32*24)+[.5*(a if j<4 else b) if i<16 else 0.
                            for i in range(32) for j in range(8)]
        need(all(v==0 for v in values[32*24+24*8:]),"source incoming edge")
        result[mode]=hashlib.sha256(struct.pack(">"+str(len(values))+"d",*values)).hexdigest()
    need(len(set(result.values()))==4,"topology digests alias")
    return result


def first_run(flags,n):
    streak=0
    for i,flag in enumerate(flags):
        streak=streak+1 if flag else 0
        if streak==n:
            return i
    return None


def audit_episode(ep):
    seed,arm=ep["seed"],ep["arm"]
    rows=ep["trace"]
    need(ep["valid"] is True and len(rows)==d.STEPS+1,"invalid episode")
    p.audit_tape(rows,arm)
    tape=d.sensor_tape(seed)
    schedule=prior.world(seed)["schedule"]
    hidden=dict(schedule)
    matrices=topology_digests()
    observed=c.Observer()
    full=c.Observer(retain_paths=True)
    counts=[]
    truth_bits=[]
    actual_path=[]
    action_log=[]
    blocks=[]
    metrics={key:empty() for key in STRATA}
    witnesses={}
    previous=None
    g_hat=0.
    used=0
    max_residual=max_obs_error=max_public_reconstruction_error=0.
    truth=0
    for t,row in enumerate(rows):
        need(row["tick"]==t,"nonconsecutive archive")
        obs=d.parse_obs(row)
        bits=tuple(row["true_bits"])
        gaba=tuple(float.fromhex(x) for x in row["true_gaba"])
        need(len(bits)==8 and all(type(x) is int and x in (0,1) for x in bits),"invalid full bits")
        need(len(gaba)==16 and all(math.isfinite(x) and x>=0 for x in gaba),"invalid conductance")
        noise,mask=tape[t]
        expected=d.public_observation(t,gaba,bits,noise,mask)
        need(obs==expected and row["noise"]==[x.hex() for x in noise] and row["erasures"]==list(mask),"sensor tape mismatch")
        old=tuple(row["policy"]["filter"]["candidates"])
        if t:
            need(row["transition_mode"]==truth and previous is not None,"transition truth mismatch")
            old_obs,old_bits,old_g=previous
            residual=q.observed_residual(old_obs.gaba,obs.gaba)
            n=c.decode_count(residual)
            need(n==c.native_count(truth,old_bits),"decoded arrival disagrees with actual count")
            compatible=c.compatible_count(n,old_obs.bits)
            complete=c.compatible_count(n,old_bits)
            need(compatible==q.support(d.ALL,old_obs.bits,residual) and list(compatible)==row["policy"]["filter"]["instant"]
                 and complete==q.support(d.ALL,old_bits,residual),"instantaneous support mismatch")
            need(truth in complete and set(complete)<=set(compatible),"full support false exclusion")
            last_obs,current_obs=observed.step(t,compatible)
            last_full,current_full=full.step(t,complete)
            need(truth in last_obs and truth in last_full and set(last_full)<=set(last_obs),"past path support violation")
            expected_g=[q.DECAY*(x+.5*n) for x in old_g]
            err=max(abs(y-x) for x,y in zip(expected_g,gaba,strict=True))
            max_residual=max(max_residual,err)
            need(err<=c.TOL,"native recurrence")
            g_hat=q.DECAY*(g_hat+.5*n)
            counts.append(n)
            truth_bits.append(old_bits)
            n0,n1=sum(old_bits[:4]),sum(old_bits[4:])
            old_truth=truth
        else:
            need(row["transition_mode"] is None and all(x==0. for x in gaba),"initial latent state")
            last_obs,current_obs=observed.step(0)
            last_full,current_full=full.step(0)
            n0=n1=0
            compatible=complete=()
            old_truth=None
        g_error=max(abs(g_hat-x) for x in gaba)
        obs_error=max(abs(g_hat-x) for x in obs.gaba)
        max_public_reconstruction_error=max(max_public_reconstruction_error,g_error)
        max_obs_error=max(max_obs_error,obs_error)
        need(g_error<=c.TOL and obs_error<=q.EPS+c.TOL,"global public conductance reconstruction")
        truth=hidden.get(t,truth)
        need(row["next_mode"]==truth and truth in current_full and truth in current_obs
             and set(current_full)<=set(current_obs),"action-time path support violation")
        actual_path.append(truth)
        previous=obs,bits,gaba
        if t==d.STEPS:
            break
        stratum=("NO_CHANGE" if not schedule else "NOMINAL_PRE_SWITCH" if t<schedule[0][0] else
                 "OOD_DISCONNECTED" if truth==3 else "OOD_REACHABLE")
        z=metrics[stratum]
        z["ticks"]+=1
        z["old_singleton"]+=len(old)==1
        z["old_correct_action_singleton"]+=old==(truth,)
        z["old_wrong_action_singleton"]+=len(old)==1 and truth not in old
        z["old_excludes_action_truth"]+=truth not in old
        z["old_past_correct_but_action_wrong"]+=t>0 and old==(old_truth,) and old_truth!=truth
        z["old_singleton_full_ambiguous"]+=len(old)==1 and len(current_full)>1
        z["window_observed_singleton"]+=len(current_obs)==1
        z["window_full_singleton"]+=len(current_full)==1
        z["window_full_ambiguous"]+=len(current_full)>1
        z["window_erasure_enlarged"]+=set(current_full)<set(current_obs)
        z["window_observed_past_singleton"]+=t>0 and len(last_obs)==1
        z["window_full_past_singleton"]+=t>0 and len(last_full)==1
        z["window_past_singleton_action_ambiguous"]+=t>0 and len(last_full)==1 and len(current_full)>1
        z["unrestricted_action_singleton"]+=t==0
        z["unrestricted_no_common_group"]+=t>0
        cg=c.common_groups(current_obs)
        fg=c.common_groups(current_full)
        z["window_no_common_group"]+=not cg
        z["window_full_no_common_group"]+=not fg
        z["window_disconnect_possible"]+=3 in current_obs
        if t:
            z["transition_ticks"]+=1
            z["no_source_spikes"]+=n0==0 and n1==0
            z["full_structural_alias"]+=n0+n1>0 and len(complete)>1
            z["erasure_extra_instant"]+=set(complete)<set(compatible)
            z["distinct_arrival_opportunity"]+=n0>0 and n1>0 and n0!=n1
            z["instant_observed_singleton"]+=len(compatible)==1
            z["instant_full_singleton"]+=len(complete)==1
        group=row["group"]
        need(group is None or type(group) is int and group in (0,1),"bad group")
        need(row["topology_sha256"]==matrices[truth] and row["direct_B_pA"]==300.
             and row["applied_gain"]==1. and row["source_inputs_pA"]==[500. if group==j else 0. for j in (0,1)],"topology/current mismatch")
        if group is not None:
            used+=1
            z["stim_ticks"]+=1
            connected=bool(c.MODES[truth][group])
            guaranteed=group in cg
            full_guaranteed=group in fg
            need(not guaranteed or full_guaranteed,"guarantee not monotone")
            need(not full_guaranteed or connected,"false route guarantee")
            z["stim_connected"]+=connected
            z["stim_guaranteed"]+=guaranteed
            z["stim_full_guaranteed"]+=full_guaranteed
            z["stim_unguaranteed"]+=not guaranteed
            z["stim_disconnect_possible"]+=3 in current_obs
        need(row["cumulative_stim_ticks"]==used,"budget ledger")
        if (t+1)%p.BLOCK==0:
            need(used==(t+1)//p.BLOCK*p.ON,"block budget")
        action_log.append({"mode":truth,"old":old,"observed":current_obs,"full":current_full})
        # Select counterexample witnesses by fixed semantic trigger, not
        # numerical outcomes. No future sensor sample is used in a witness.
        triggers=[]
        if stratum.startswith("OOD"):
            if len(current_full)>1:
                triggers.append("FIRST_OOD_FULL_AMBIGUITY")
                if len(old)==1:
                    triggers.append("FIRST_ORIGINAL_SINGLETON_WITH_FULL_AMBIGUITY")
            if t in hidden:
                triggers.append("FIRST_HIDDEN_SWITCH")
        for trigger in triggers:
            if trigger in witnesses:
                continue
            alt=full.alternate(truth)
            if alt is None:
                witnesses[trigger]=None
            else:
                changes=c.validate_path(alt,counts,truth_bits)
                need(alt[-1] in current_full and alt[-1]!=truth,"alternate final mode")
                witnesses[trigger]={"tick":t,"actual_mode":truth,"alternative_mode":alt[-1],
                    "original_candidates":list(old),"full_path_support":list(current_full),
                    "observed_path_support":list(current_obs),"alternative_switches":changes,
                    "validated_prior_transitions":len(counts),
                    "same_prior_arrivals":True,"same_fixed_actions_and_source_history":True}
        if t%p.BLOCK==0:
            selected=tuple(row["decision"]["selected"])
            groups=[p.action(selected,i) for i in range(p.BLOCK)]
            need(sum(x is not None for x in groups)==p.ON
                 and groups==[x["group"] for x in rows[t:t+p.BLOCK]],"selected plan replay")
            guarantee=c.block_feasibility(observed.states,t,groups)
            privileged=c.block_feasibility(full.states,t,groups)
            actual=sum(group is not None and c.MODES[rows[t+i]["next_mode"]][group]
                       for i,group in enumerate(groups))
            need(0<=guarantee<=privileged<=actual<=p.ON,"block route guarantee violated")
            blocks.append({"start":t,"plan":list(selected),"actual_mode":truth,"stratum":stratum,
                "observed_support":list(current_obs),"full_support":list(current_full),
                "guaranteed_connected_slots":guarantee,"full_guaranteed_connected_slots":privileged,
                "actual_connected_slots":actual,"stimulated_slots":p.ON})
    need(used==1600 and ep["source_current_l1_pA_ticks"]==3200000 and len(blocks)==10 and len(action_log)==d.STEPS,"episode roster")
    actual_changes=c.validate_path(actual_path,counts,truth_bits)
    need(actual_changes==[list(x) for x in schedule],"archive switch grammar")
    need(sum(z["ticks"] for z in metrics.values())==d.STEPS and sum(z["stim_ticks"] for z in metrics.values())==1600,"stratum ledger")
    events=[]
    for i,(tau,m) in enumerate(schedule):
        end=schedule[i+1][0] if i+1<len(schedule) else d.STEPS
        log=action_log[tau:end]
        need(all(x["mode"]==m for x in log),"mixed OOD segment")
        original=ep["segments"][i]
        need(original["start"]==tau and original["end"]==end and original["mode"]==m,"parent segment mismatch")
        events.append({"switch":tau,"end":end,"mode":m,
            "first_observed_action_singleton_delay":first_run([x["observed"]==(m,) for x in log],1),
            "first_full_action_singleton_delay":first_run([x["full"]==(m,) for x in log],1),
            "original_action_I20_completion_delay":first_run([x["old"]==(m,) for x in log],20),
            "parent_transition_I20_completion_latency":original["I20_latency"]})
    for trigger in ("FIRST_OOD_FULL_AMBIGUITY","FIRST_ORIGINAL_SINGLETON_WITH_FULL_AMBIGUITY","FIRST_HIDDEN_SWITCH"):
        witnesses.setdefault(trigger,None)
    return {"seed":seed,"arm":arm,"metrics":metrics,"blocks":blocks,"witnesses":witnesses,
        "events":events,"max_recurrence_residual_nS":max_residual,
        "max_public_conductance_error_nS":max_public_reconstruction_error,"max_sensor_error_nS":max_obs_error}


def aggregate_counts(cells):
    return {k:sum(x[k] for x in cells) for k in FIELDS}


def denom(field):
    if field=="ticks":
        return None
    if field.startswith("stim_") and field!="stim_ticks":
        return "stim_ticks"
    if field in ("no_source_spikes","full_structural_alias","erasure_extra_instant","distinct_arrival_opportunity",
                 "instant_observed_singleton","instant_full_singleton","window_observed_past_singleton",
                 "window_full_past_singleton","window_past_singleton_action_ambiguous"):
        return "transition_ticks"
    return "ticks"


def ratio(cell,field):
    key=denom(field)
    return None if key is None or not cell[key] else cell[field]/cell[key]


def summarize(rows):
    def per_world(row,stratum):
        if stratum=="OOD_ALL":
            return aggregate_counts([row["metrics"]["OOD_REACHABLE"],row["metrics"]["OOD_DISCONNECTED"]])
        return row["metrics"][stratum]
    scopes=STRATA+("OOD_ALL",)
    by={arm:[x for x in rows if x["arm"]==arm] for arm in ARMS}
    output={}
    for arm,episodes in by.items():
        table={}
        for scope in scopes:
            cells=[per_world(row,scope) for row in episodes]
            eligible=[x for x in cells if x["ticks"]]
            total=aggregate_counts(eligible)
            means={}
            for field in FIELDS:
                values=[v for x in eligible if (v:=ratio(x,field)) is not None]
                if values:
                    means[field]={"mean":math.fsum(values)/len(values),"worlds":len(values)}
            table[scope]={"counts":total,"equal_world_rates":means}
        block_sets={}
        for scope in scopes:
            blocks=[b for row in episodes for b in row["blocks"]
                    if b["stratum"]==scope or scope=="OOD_ALL" and b["stratum"].startswith("OOD")]
            block_sets[scope]={"blocks":len(blocks),"stimulated_slots":sum(b["stimulated_slots"] for b in blocks),
                "guaranteed_connected_slots":sum(b["guaranteed_connected_slots"] for b in blocks),
                "full_guaranteed_connected_slots":sum(b["full_guaranteed_connected_slots"] for b in blocks),
                "actual_connected_slots":sum(b["actual_connected_slots"] for b in blocks),
                "all_slots_guaranteed":sum(b["guaranteed_connected_slots"]==p.ON for b in blocks)}
        events=[x for row in episodes for x in row["events"]]
        table["switches"]={"segments":len(events),
            "observed_action_singleton_segments":sum(x["first_observed_action_singleton_delay"] is not None for x in events),
            "full_action_singleton_segments":sum(x["first_full_action_singleton_delay"] is not None for x in events),
            "parent_transition_I20_segments":sum(x["parent_transition_I20_completion_latency"] is not None for x in events)}
        table["held_blocks"]=block_sets
        table["witnesses"]={k:sum(row["witnesses"][k] is not None for row in episodes)
                             for k in ("FIRST_OOD_FULL_AMBIGUITY","FIRST_ORIGINAL_SINGLETON_WITH_FULL_AMBIGUITY","FIRST_HIDDEN_SWITCH")}
        output[arm]=table
    contrasts={}
    for arm in ARMS[1:]:
        left={x["seed"]:x for x in by["DUAL"]}
        right={x["seed"]:x for x in by[arm]}
        need(set(left)==set(right),"paired cohort mismatch")
        pair={}
        for scope in ("OOD_REACHABLE","OOD_DISCONNECTED","OOD_ALL"):
            fields={}
            for f in FIELDS:
                diffs=[]
                for seed in sorted(left):
                    a,b=ratio(per_world(left[seed],scope),f),ratio(per_world(right[seed],scope),f)
                    if a is not None and b is not None:
                        diffs.append({"seed":seed,"difference":a-b})
                if diffs:
                    vals=[x["difference"] for x in diffs]
                    fields[f]={"paired_worlds":len(vals),"mean":math.fsum(vals)/len(vals),
                        "positive":sum(v>1e-12 for v in vals),"negative":sum(v< -1e-12 for v in vals),
                        "ties":sum(abs(v)<=1e-12 for v in vals),"per_world":diffs}
            pair[scope]=fields
        contrasts["DUAL_MINUS_"+arm]=pair
    return output,contrasts


def audit(archive):
    need(q.MODES==c.MODES and tuple(d.WINDOWS)==c.WINDOWS and q.DECAY==d.neural.DECAY,"parent model drift")
    contract=evidence.trusted_contract("CNEH-EXP-05")
    admission=evidence.admit_archive(archive,contract)
    need(admission["historical_archive_id"]==ARCHIVE_ID and admission["historical_archive_sha256"]==ARCHIVE_SHA,"historical source")
    need(evidence.file_hash(archive)==ARCHIVE_SHA,"archive changed")
    episodes=[]
    seen=set()
    with tempfile.TemporaryDirectory(prefix="cneh05i-") as tmp,zipfile.ZipFile(archive) as z:
        path=Path(tmp)/"episodes.json.gz"
        with z.open("cneh05/episodes.json.gz") as source,path.open("xb") as out:
            shutil.copyfileobj(source,out,1024*1024)
        need(evidence.file_hash(path)==admission["manifest"]["files"]["episodes.json.gz"],"archive member changed")
        for ep in evidence.strict_array(path):
            key=ep["seed"],ep["arm"]
            need(key not in seen,"duplicate archive episode")
            seen.add(key)
            episodes.append(audit_episode(ep))
        need(evidence.file_hash(path)==admission["manifest"]["files"]["episodes.json.gz"],"stream member changed")
    need(seen==set(itertools.product(prior.SEEDS,p.ARMS)) and len(episodes)==80 and evidence.file_hash(archive)==ARCHIVE_SHA,"complete archive roster")
    by={(x["seed"],x["arm"]):x for x in episodes}
    need(all({k:v for k,v in by[seed,"DUAL"].items() if k!="arm"}==
             {k:v for k,v in by[seed,"EXACT_EMULATOR"].items() if k!="arm"} for seed in prior.SEEDS),"diagnostic emulator mismatch")
    summary,contrasts=summarize(episodes)
    report={"experiment":"CNEH-EXP-05I","authority":"RETROSPECTIVE_CAUSAL_IDENTIFIABILITY_DIAGNOSTIC_ONLY",
            "all_instrument_checks_passed":True,"scientific_promotion_authorized":False,
            "external_replication":"NOT_TESTED","native_cross_worker_replay":"NOT_TESTED_BY_THIS_DIAGNOSTIC",
            "source_head":HEAD,"source_artifact":ARCHIVE_ID,"source_archive_sha256":ARCHIVE_SHA,
            "source_admission":admission,"protocol_sha256":evidence.file_hash(HERE/"PROTOCOL.md"),
            "implementation_sha256":{x.name:evidence.file_hash(x) for x in (Path(__file__),Path(c.__file__))},
            "count_qualification":c.count_qualification(),"worlds":16,"episodes":80,"unique_arms":4,
            "decoded_transitions":80*d.STEPS,"action_ticks":80*d.STEPS,
            "max_public_conductance_error_nS":max(x["max_public_conductance_error_nS"] for x in episodes),
            "max_recurrence_residual_nS":max(x["max_recurrence_residual_nS"] for x in episodes),
            "summary":summary,"paired_contrasts":contrasts,"per_episode":episodes}
    promotion.check_verdict("CNEH-EXP-05I",report)
    return report


def compact(report):
    return {k:report[k] for k in ("experiment","authority","all_instrument_checks_passed","worlds","episodes",
                 "decoded_transitions","count_qualification","max_public_conductance_error_nS","max_recurrence_residual_nS")} | {
        "arms":{a:{"OOD_ALL":x["OOD_ALL"],"held_blocks":x["held_blocks"]["OOD_ALL"],
                   "switches":x["switches"],"witnesses":x["witnesses"]} for a,x in report["summary"].items()}}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--archive",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    ap.add_argument("--verify",action="store_true")
    args=ap.parse_args()
    if not args.verify and (args.out.exists() or args.out.is_symlink()):
        raise FileExistsError("immutable output")
    report=audit(args.archive)
    files={"report.json":evidence.canonical(report)}
    if not args.verify:
        d.parent.write_bundle(args.out,files)
    d.parent.verify_payload(args.out,files)
    print(evidence.canonical(compact(report)).decode().strip())


if __name__=="__main__":
    main()
