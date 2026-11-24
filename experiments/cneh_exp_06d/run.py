"""Exact native model-set admission and immutable parent evidence."""
from __future__ import annotations

import argparse
import io
import os
from pathlib import Path
import zipfile

from experiments.cneh_exp_06c import algebra as a,run as custody
from experiments.cneh_exp_06d import audit
from scripts import cneh_promotion_gate as promotion

EXPERIMENT="CNEH-EXP-06D"
PARENT_ID=14934382112
PARENT_SHA="103a8268cffa855e661760e69f93bb1187ecc92c85f53996949a745cb3f1f2ae"
PARENT_REPORT="6b40ea25b81af033d0ffddd96df4f89f301fe961ff3cc9879dbc382673f19a5e"
PARENT_HEAD="48c0a596803b8410d39ac86f4974c01115e794da"
ARCHES=custody.ARCHES


def parent(path):
    raw=path.read_bytes()
    a.need(custody.sha(raw)==PARENT_SHA,"sealed C archive")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        a.need(len(z.infolist())==2 and set(z.namelist())=={"report.json","SHA256SUMS"},"parent roster")
        report=z.read("report.json")
        a.need(custody.sha(report)==PARENT_REPORT and z.read("SHA256SUMS")==f"{PARENT_REPORT}  report.json\n".encode(),"parent manifest")
    value=promotion.strict_json(report)
    a.need(value["head_sha"]==PARENT_HEAD and value["run_id"]=="45422851184"
           and value["qualification"]=="PASS_CONDITIONAL_SYNTHETIC_ONLY" and value["native_nominal_cases"]==6144
           and value["native_exact_payload_pairs"]==1 and value["summary"]["ood_aliases"]["ood_model_qualification"]=="FAIL_COUNTEREXAMPLE"
           and value["scientific_promotion_authorized"] is False and value["closed_loop_efficacy"]=="BLOCKED","parent conditional scope")
    promotion.check_verdict("CNEH-EXP-06C",value)
    return PARENT_REPORT


def sources():
    return {p.name:custody.sha(p.read_bytes()) for p in sorted(Path("experiments/cneh_exp_06d").glob("*.py"))}


def calculate():
    rows,stats=audit.panel()
    result={"nominal_noise_counterexample":audit.prove_noise_alias(),"parameter_cover":audit.model_cover_check(),
            "profiles":stats,"recovered_C_aliases":audit.recover_aliases(),"negative_controls":audit.negatives(),
            "model_set_cases":len(rows),"false_joint_exclusions":0,
            "calibration":"NOT_TESTED","biophysical_validity":"NOT_TESTED",
            "historical_count_observability":"FAIL_PRESERVED","historical_nominal_ood":"FAIL_PRESERVED",
            "statistical_generalization":"NOT_TESTED","multiscale_scientific_coherence":"NOT_TESTED",
            "closed_loop_efficacy":"BLOCKED","blind_causal_cohort":"BLOCKED",
            "scientific_promotion_authorized":False,"scientific_promotion":"BLOCKED"}
    return {"records":rows,"summary":result}


def run(args):
    anchor=parent(args.parent)
    fp=custody.fingerprint(args.arch)
    payload=calculate()
    raw=custody.canonical(payload)
    a.need(len(raw)<=custody.MAX_RAW,"raw payload bound")
    report={"experiment":EXPERIMENT,"parent_report_sha256":anchor,"fingerprint":fp,
            "d_source_sha256":sources(),"payload_sha256":custody.sha(raw),"summary":payload["summary"],
            "scientific_promotion_authorized":False,"scientific_promotion":"BLOCKED"}
    promotion.check_verdict(EXPERIMENT,report)
    custody.write(args.out,report,raw)
    print(custody.canonical({"arch":args.arch,"payload_sha256":custody.sha(raw),"profiles":payload["summary"]["profiles"]}).decode(),end="")


def aggregate(args):
    anchor=parent(args.parent)
    a.need({p.name for p in args.profiles.iterdir()}=={f"cneh06d-{arch}" for arch in ARCHES},"complete native roster")
    payload=calculate()
    raw=custody.canonical(payload)
    receipts=[]
    for arch in ARCHES:
        report,data=custody.authenticate(args.profiles/f"cneh06d-{arch}")
        fp=report["fingerprint"]
        promotion.check_verdict(EXPERIMENT,report)
        a.need(report["parent_report_sha256"]==anchor and report["d_source_sha256"]==sources()
               and fp["arch"]==arch and fp["elf_machine"]==(62 if arch=="x86_64" else 183)
               and fp["head_sha"]==args.head and fp["run_id"]==args.run_id
               and fp["runner_arch"]==("X64" if arch=="x86_64" else "ARM64")
               and fp["runner_environment"]=="github-hosted" and fp["python_version"]==[3,12,16],
               "exact native source/head binding")
        a.need(data==raw and custody.canonical(report["summary"])==custody.canonical(payload["summary"]),"independent exact payload")
        receipts.append({"fingerprint":fp,"d_source_sha256":sources(),"payload_sha256":custody.sha(data)})
    s=payload["summary"]
    a.need(s["model_set_cases"]==576 and s["false_joint_exclusions"]==0 and len(s["recovered_C_aliases"])==3
           and len(s["negative_controls"])==7,"fixed qualification roster")
    report={"experiment":EXPERIMENT,"head_sha":args.head,"run_id":args.run_id,"parent_report_sha256":anchor,
            "qualification":"PASS_CONDITIONAL_OUTER_ENCLOSURE_ONLY","native_exact_payload_pairs":1,
            "native_model_set_cases":1152,"native_alias_recoveries":6,"native_negative_controls":14,
            "payload_sha256":custody.sha(raw),"summary":s,"native_receipts":receipts,
            "scientific_promotion_authorized":False,"scientific_promotion":"BLOCKED",
            "closed_loop_efficacy":"BLOCKED","blind_causal_cohort":"BLOCKED"}
    promotion.check_verdict(EXPERIMENT,report)
    custody.write(args.out,report)
    print(custody.canonical({k:v for k,v in report.items() if k!="native_receipts"}).decode(),end="")


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    sub=ap.add_subparsers(dest="command",required=True)
    r=sub.add_parser("run");g=sub.add_parser("aggregate")
    for p in (r,g):
        p.add_argument("--parent",type=Path,required=True);p.add_argument("--out",type=Path,required=True)
    r.add_argument("--arch",choices=ARCHES,required=True)
    g.add_argument("--profiles",type=Path,required=True);g.add_argument("--head",required=True);g.add_argument("--run-id",required=True)
    args=ap.parse_args()
    if args.command=="run":
        run(args)
    else:
        aggregate(args)


if __name__=="__main__":
    main()
