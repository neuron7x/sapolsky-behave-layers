"""Native exact-rational synthetic measurement qualification and raw admission."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import sys
import zipfile

from experiments.cneh_exp_06c import algebra as a,fixtures as f
from scripts import cneh_promotion_gate as promotion

EXPERIMENT="CNEH-EXP-06C"
PARENT_ID=14926773571
PARENT_SHA="1088d75b4f145bd1294c673b3e9a35e19d7bd3a485910e029349d24cbfc83ab3"
PARENT_HEAD="c6ee3455baeb1bbe2b0f5075613ad369caf81515"
PARENT_REPORT="ca5fd38b1689c982af9e3075045fb0f3cfd51220d7225b58700c9522d04dde05"
ARCHES=("x86_64","aarch64")
MAX_RAW=32*1024*1024


def sha(x):
    return hashlib.sha256(x).hexdigest()


def canonical(x):
    return (json.dumps(x,sort_keys=True,separators=(",",":"),allow_nan=False)+"\n").encode()


def authenticate_parent(path):
    raw=path.read_bytes()
    a.need(sha(raw)==PARENT_SHA,"sealed parent archive")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        a.need(len(z.infolist())==2 and set(z.namelist())=={"report.json","SHA256SUMS"},"parent archive roster")
        data=z.read("report.json")
        a.need(sha(data)==PARENT_REPORT and z.read("SHA256SUMS")==f"{PARENT_REPORT}  report.json\n".encode(),"parent inner manifest")
    value=promotion.strict_json(data)
    a.need(value["head_sha"]==PARENT_HEAD and value["run_id"]=="45406856117"
           and value["qualification"]=="PASS_FINITE_ONLY" and value["exact_cross_cpu_shards"]==13
           and value["r0_payload_exact_shards"]==13 and value["native_primary_executions"]==2274
           and value["native_public_admission_checks"]==6822 and value["negative_controls_rejected"]==32
           and value["observability_global_injectivity"]=="FAIL_COUNTEREXAMPLE"
           and value["finite_horizon_graph_distinguishability"]=="FAIL_COUNTEREXAMPLE"
           and value["sensitivity_gramian_rank"]==0 and value["continuous_state_nullity"]==160
           and value["scientific_promotion_authorized"] is False and value["blind_causal_cohort"]=="BLOCKED","parent scope")
    promotion.check_verdict("CNEH-EXP-06B",value)
    return PARENT_REPORT


def fingerprint(arch):
    a.need(arch in ARCHES and platform.machine()==os.uname().machine==arch
           and platform.system()=="Linux" and os.environ["RUNNER_ARCH"]==("X64" if arch=="x86_64" else "ARM64")
           and os.environ["RUNNER_ENVIRONMENT"]=="github-hosted"
           and platform.python_implementation()=="CPython" and sys.version_info[:3]==(3,12,16),"native interpreter contract")
    exe=Path(sys.executable).resolve()
    raw=exe.read_bytes()
    machine=62 if arch=="x86_64" else 183
    a.need(raw[:6]==b"\x7fELF\x02\x01" and int.from_bytes(raw[18:20],"little")==machine,"native ELF architecture")
    return {"arch":arch,"elf_machine":machine,"python_version":list(sys.version_info[:3]),
            "interpreter_sha256":sha(raw),"runner_arch":os.environ["RUNNER_ARCH"],"runner_environment":"github-hosted",
            "head_sha":os.environ["HEAD_SHA"],"run_id":os.environ["GITHUB_RUN_ID"],
            "source_sha256":{p.name:sha(p.read_bytes()) for p in sorted(Path("experiments/cneh_exp_06c").glob("*.py"))}}


def calculate():
    count=f.independent_coefficients()
    records,noise=f.nominal()
    graph,graph_metrics=f.graph_panel()
    negatives=f.negative_controls()
    aliases=f.aliases()
    summary={"conditional_measurement_certificate":a.matrix_certificate(),"independent_coefficient_checks":count,
             "nominal_cases":len(records),"noise_profiles":noise,"false_exclusions":0,
             "negative_controls":negatives,"graph_metrics":graph_metrics,
             "ood_aliases":aliases,"reachability":a.reachability(),
             "live_measurement_calibration":"NOT_TESTED","biophysical_validity":"NOT_TESTED",
             "multiscale_scientific_coherence":"NOT_TESTED","statistical_generalization":"NOT_TESTED",
             "independent_blind_custody":"NOT_ESTABLISHED","closed_loop_efficacy":"BLOCKED",
             "historical_count_observability":"FAIL_PRESERVED",
             "scientific_promotion_authorized":False,"scientific_promotion":"BLOCKED",
             "blind_causal_cohort":"BLOCKED"}
    payload={"nominal_records":records,"graph_records":graph,"summary":summary}
    return payload


def write(folder,report,raw=None):
    folder.mkdir()
    (folder/"report.json").write_bytes(canonical(report))
    if raw is not None:
        (folder/"raw.json.gz").write_bytes(gzip.compress(raw,mtime=0))
    paths=sorted(folder.iterdir())
    (folder/"SHA256SUMS").write_text("".join(f"{sha(p.read_bytes())}  {p.name}\n" for p in paths))


def authenticate(folder):
    a.need(folder.is_dir() and {p.name for p in folder.iterdir()}=={"report.json","raw.json.gz","SHA256SUMS"}
           and all(p.is_file() and not p.is_symlink() for p in folder.iterdir()),"native artifact roster")
    names=("raw.json.gz","report.json")
    a.need((folder/"SHA256SUMS").read_text()=="".join(f"{sha((folder/n).read_bytes())}  {n}\n" for n in names),"native manifest")
    report=promotion.strict_json((folder/"report.json").read_bytes())
    with gzip.open(folder/"raw.json.gz","rb") as stream:
        raw=stream.read(MAX_RAW+1)
    a.need(len(raw)<=MAX_RAW and sha(raw)==report["payload_sha256"],"raw payload binding")
    return report,raw


def run(args):
    parent=authenticate_parent(args.parent)
    fp=fingerprint(args.arch)
    payload=calculate();raw=canonical(payload)
    a.need(len(raw)<=MAX_RAW,"raw result bound")
    report={"experiment":EXPERIMENT,"parent_report_sha256":parent,"fingerprint":fp,
            "payload_sha256":sha(raw),"summary":payload["summary"],
            "scientific_promotion_authorized":False,"scientific_promotion":"BLOCKED"}
    promotion.check_verdict(EXPERIMENT,report)
    write(args.out,report,raw)
    print(canonical({"arch":args.arch,"payload_sha256":sha(raw),"noise_profiles":payload["summary"]["noise_profiles"],
                     "graph_profiles":payload["summary"]["graph_metrics"]["profiles"],
                     "certificate":payload["summary"]["conditional_measurement_certificate"]}).decode(),end="")


def aggregate(args):
    parent=authenticate_parent(args.parent)
    a.need({p.name for p in args.profiles.iterdir()}=={f"cneh06c-{arch}" for arch in ARCHES},"native roster")
    # Fresh exact recomputation of all fixtures; the independent Decimal
    # generator checks the rational enclosure before any verdict is emitted.
    payload=calculate()
    expected=canonical(payload)
    receipts=[]
    sources={p.name:sha(p.read_bytes()) for p in sorted(Path("experiments/cneh_exp_06c").glob("*.py"))}
    for arch in ARCHES:
        report,raw=authenticate(args.profiles/f"cneh06c-{arch}")
        promotion.check_verdict(EXPERIMENT,report)
        fp=report["fingerprint"]
        a.need(report["parent_report_sha256"]==parent and fp["arch"]==arch
               and fp["head_sha"]==args.head and fp["run_id"]==args.run_id
               and fp["python_version"]==[3,12,16] and fp["source_sha256"]==sources
               and fp["runner_arch"]==("X64" if arch=="x86_64" else "ARM64")
               and fp["elf_machine"]==(62 if arch=="x86_64" else 183)
               and fp["runner_environment"]=="github-hosted","native identity")
        a.need(raw==expected and canonical(report["summary"])==canonical(payload["summary"]),"cross-CPU or independently recomputed payload differs")
        receipts.append({"fingerprint":fp,"payload_sha256":sha(raw)})
    summary=payload["summary"]
    a.need(summary["nominal_cases"]==3072 and summary["independent_coefficient_checks"]==25
           and len(summary["negative_controls"])==14 and len(payload["graph_records"])==128,"complete fixture metrics")
    report={"experiment":EXPERIMENT,"head_sha":args.head,"run_id":args.run_id,
            "qualification":"PASS_CONDITIONAL_SYNTHETIC_ONLY","native_architectures":list(ARCHES),
            "native_exact_payload_pairs":1,"native_nominal_cases":6144,"native_graph_cases":256,
            "native_negative_controls":28,"parent_report_sha256":parent,"payload_sha256":sha(expected),
            "summary":summary,"native_receipts":receipts,
            "scientific_promotion_authorized":False,"scientific_promotion":"BLOCKED",
            "blind_causal_cohort":"BLOCKED","closed_loop_efficacy":"BLOCKED"}
    promotion.check_verdict(EXPERIMENT,report)
    write(args.out,report)
    print(canonical({k:v for k,v in report.items() if k!="native_receipts"}).decode(),end="")


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    sub=ap.add_subparsers(dest="command",required=True)
    r=sub.add_parser("run");g=sub.add_parser("aggregate")
    for p in (r,g):
        p.add_argument("--parent",type=Path,required=True)
        p.add_argument("--out",type=Path,required=True)
    r.add_argument("--arch",choices=ARCHES,required=True)
    g.add_argument("--profiles",type=Path,required=True)
    g.add_argument("--head",required=True);g.add_argument("--run-id",required=True)
    args=ap.parse_args()
    if args.command=="run":
        run(args)
    else:
        aggregate(args)


if __name__=="__main__":
    main()
