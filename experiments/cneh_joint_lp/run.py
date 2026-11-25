"""Native evidence and fresh reconstruction for JOINT-LP-01."""
from __future__ import annotations

import argparse
from fractions import Fraction as F
from pathlib import Path
import platform
import re

from experiments.cneh_exp_06f.run import canonical,directory,read_receipt,sha
from experiments.cneh_exp_06h import reference as h
from experiments.cneh_exp_06i import panel as ip
from experiments.cneh_joint_lp import kernel as k,panel as p,search as s

PARENT="bdc3d736692aeb1362c12918afc022fa11c7ca2c"
PARENT_SHA256="2f127a7590a9f6e5f01858c185be70d07ed28d78fd226a97807fa3443e729479"
ARCHES=("x86_64","aarch64")
PYTHON="3.12.16"


def identity(args):
    k.need(all(re.fullmatch(r"[0-9a-f]{40}",x) for x in
               (args.head,args.base,args.checkout)) and args.base==PARENT,"commit identity")
    k.need(all(re.fullmatch(r"[1-9][0-9]*",x) for x in
               (args.run_id,args.attempt)),"run identity")
    k.need(sha(read_receipt(args.parent))==PARENT_SHA256,"sealed J archive mismatch")


def metadata(args,arch,raw):
    identity(args)
    k.need(arch in ARCHES,"native architecture")
    return {"experiment":"CNEH-JOINT-LP-01","head_sha":args.head,"base_sha":args.base,
            "checkout_sha":args.checkout,"run_id":args.run_id,"run_attempt":args.attempt,
            "arch":arch,"python":PYTHON,"parent_head":PARENT,
            "parent_sha256":PARENT_SHA256,"payload_sha256":sha(raw),
            "scientific_promotion_authorized":False}


def telemetry(rows):
    k.need(type(rows) is list and 1<=len(rows)<=9,"proposal telemetry roster")
    k.need(all(type(item["pivots"]) is int and 0<=item["pivots"]<=s.MAX_PIVOTS
               and type(item["reason"]) is str for item in rows),"proposal pivot accounting")
    return sum(item["pivots"] for item in rows)


def validate(value):
    k.need(value["qualification"]==p.QUALIFIED and value["failures"]==[],
           "frozen LP qualification failed")
    k.need(value["scope"]==k.SCOPE and value["experiment"]=="CNEH-JOINT-LP-01"
           and all(type(value.get(key)) is type(v) and value[key]==v
                   for key,v in k.NEGATIVE.items()),"scope or negative evidence changed")
    toy=value["toy"]
    roster={(F(cap),F(delta),j,sign) for cap in (0,F(1,2),1,2)
            for delta in (-1,F(-1,2),0,1) for j in range(2) for sign in (-1,1)}
    actual={(F(x["cap"]),F(x["delta"]),x["coordinate"],x["sign"]) for x in toy}
    k.need(len(toy)==len(actual)==64 and actual==roster,"exact toy roster")
    for item in toy:
        rows=p.toy_rows(F(item["cap"]),F(item["delta"]))
        vertices=p.vertices2(rows)
        if vertices:
            objective=k.unit(2,item["coordinate"],item["sign"])
            exact=max(k.dot(objective,point) for point in vertices)
            k.need(item["disposition"]=="EXACT_BOUND" and
                   k.check(rows,objective,item["proof"])==F(item["bound"])==exact,
                   "independent toy upper bound")
        else:
            k.need(item["disposition"]=="CERTIFIED_INFEASIBLE" and
                   k.check_infeasible(rows,item["proof"]),"independent toy exclusion")
        k.need(type(item["search"]["pivots"]) is int and
               0<=item["search"]["pivots"]<=s.MAX_PIVOTS,"toy pivot budget")
    rows=value["cases"]
    expected={(family,idx,j) for family in ("CLEAN","STRESS")
              for idx in ip.TRUTHS for j in range(2)}
    k.need(len(rows)==len(expected)==32 and {tuple(row["id"]) for row in rows}==expected,
           "compatible record roster")
    improvements=0;pivots=0
    for row in rows:
        record,proof=row["record"],row["proof"]
        system=k.checked_system(record)
        world=tuple(map(F,row["known_world"]))
        z=k.lift(world)
        k.need(z==tuple(map(F,row["lifted_world"])) and
               min(rhs-k.dot(coef,z) for _,coef,rhs in system)==F(row["minimum_row_slack"])>=0,
               "lifted truth proof")
        k.need(k.verify(record,proof,h.BOUNDED,s.MAX_PIVOTS) and proof["status"]==k.OUTER and
               all(F(lo)<=x<=F(hi) for x,(lo,hi) in zip(world[:4],proof["outer_bounds"],strict=True)),
               "compatible world omitted")
        delta=F(proof["max_width"])-F(row["H_max_width"])
        k.need(delta==F(row["width_delta"]),"width comparison mismatch")
        improvements+=int(delta<0)
        pivots+=telemetry(row["search"])
    neg=value["contradictions"]
    expected_neg={("REFERENCE",b,sign) for b in (-8,8) for sign in (-1,1)}
    expected_neg.update((("GROSS",0,900),("GROSS",60,-100),("SUBTLE",-1),("SUBTLE",1)))
    k.need(len(neg)==8 and {tuple(row["id"]) for row in neg}==expected_neg,"negative roster")
    for row in neg:
        record,proof=row["record"],row["proof"]
        k.need(k.verify(record,proof,h.BOUNDED,s.MAX_PIVOTS),"negative proof verification")
        required=row["id"][0]!="SUBTLE"
        k.need(row["required"] is required,"required-negative identity")
        if required:
            k.need(proof["status"]==k.EXCLUDED and
                   k.check_infeasible(k.checked_system(record),proof["exclusion"]),
                   "required contradiction certificate absent")
        pivots+=telemetry(row["search"])
    k.need(improvements==value["strict_width_improvements"] and
           max(F(row["proof"]["max_width"]) for row in rows)==F(value["max_lp_width"]) and
           max(F(row["H_max_width"]) for row in rows)==F(value["max_H_width"]),
           "enclosure metric accounting")
    controls=value["controls"]
    k.need(len(controls)==23 and sum(v=="REJECTED" for v in controls.values())==18,
           "mutation roster")
    return pivots


def write_native(args,value):
    raw=canonical(value)
    args.out.mkdir(parents=True,exist_ok=False)
    (args.out/"payload.json").write_bytes(raw)
    meta=metadata(args,args.arch,raw)
    (args.out/"receipt.json").write_bytes(canonical(meta))
    print(canonical(meta).decode("ascii"),end="")


def native(args):
    identity(args)
    k.need(platform.machine()==args.arch and platform.python_version()==PYTHON,
           "native execution profile")
    value=None
    try:
        value=p.report()
        validate(value)
    except Exception as exc:
        write_native(args,{"experiment":"CNEH-JOINT-LP-01","qualification":"FAIL_FROZEN_GATE",
                           "error_type":type(exc).__name__,"error":str(exc),
                           "unadmitted_observation":value,**k.NEGATIVE})
        print("FAIL_FROZEN_GATE:",type(exc).__name__,str(exc))
        return 1
    write_native(args,value)
    print(p.QUALIFIED)
    return 0


def verify_profiles(args,raw):
    directory(args.profiles,{"cnehjointlp-"+arch for arch in ARCHES})
    receipts=[]
    for arch in ARCHES:
        root=args.profiles/("cnehjointlp-"+arch)
        directory(root,{"primary","replay"})
        expected=metadata(args,arch,raw)
        for replica in ("primary","replay"):
            folder=root/replica
            directory(folder,{"payload.json","receipt.json"})
            k.need(read_receipt(folder/"payload.json")==raw,"fresh reconstruction mismatch")
            k.need(read_receipt(folder/"receipt.json")==canonical(expected),"native identity mismatch")
        receipts.append(expected)
    return receipts


def aggregate(args):
    identity(args)
    k.need(platform.python_version()==PYTHON,"aggregate execution profile")
    value=None
    try:
        value=p.report()
        pivots=validate(value)
        raw=canonical(value)
        receipts=verify_profiles(args,raw)
    except Exception as exc:
        args.out.mkdir(parents=True,exist_ok=False)
        (args.out/"unadmitted.json").write_bytes(canonical({
            "experiment":"CNEH-JOINT-LP-01","qualification":"FAIL_FROZEN_GATE",
            "error_type":type(exc).__name__,"error":str(exc),
            "unadmitted_observation":value,**k.NEGATIVE}))
        print("FAIL_FROZEN_GATE:",type(exc).__name__,str(exc))
        return 1
    summary={"experiment":"CNEH-JOINT-LP-01","qualification":p.QUALIFIED,
             "scope":k.SCOPE,"head_sha":args.head,"base_sha":args.base,
             "checkout_sha":args.checkout,"run_id":args.run_id,"run_attempt":args.attempt,
             "parent_sha256":PARENT_SHA256,"payload_sha256":sha(raw),
             "native_receipts":receipts,"native_process_receipts":4,
             "independent_reconstructions":1,"unique_continuous_records":40,
             "native_compatible_records":64,"native_continuous_negative_cases":16,
             "native_toy_checks":128,"native_rejected_mutations":36,
             "native_certified_continuous_exclusions":2*sum(row["proof"]["status"]==k.EXCLUDED
                                                          for row in value["contradictions"]),
             "subtle_dispositions_per_arch":[row["proof"]["status"] for row in value["contradictions"]
                                           if row["id"][0]=="SUBTLE"],
             "strict_width_improvements_per_arch":value["strict_width_improvements"],
             "max_lp_width":value["max_lp_width"],"max_H_width":value["max_H_width"],
             "continuous_proposal_pivots_per_arch":pivots,
             "joint_existence_established":False,**k.NEGATIVE}
    args.out.mkdir(parents=True,exist_ok=False)
    (args.out/"payload.json").write_bytes(raw)
    (args.out/"report.json").write_bytes(canonical(summary))
    (args.out/"SHA256SUMS").write_text("".join(
        sha((args.out/name).read_bytes())+"  "+name+"\n"
        for name in ("payload.json","report.json")),encoding="ascii")
    print(canonical(summary).decode("ascii"),end="")
    return 0


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    modes=parser.add_subparsers(dest="command",required=True)
    for name in ("native","aggregate"):
        sub=modes.add_parser(name)
        for arg in ("head","base","checkout","run-id","attempt"):
            sub.add_argument("--"+arg,required=True)
        sub.add_argument("--parent",required=True,type=Path)
        sub.add_argument("--out",required=True,type=Path)
        if name=="native":
            sub.add_argument("--arch",choices=ARCHES,required=True)
        else:
            sub.add_argument("--profiles",required=True,type=Path)
    args=parser.parse_args()
    return (native if args.command=="native" else aggregate)(args)


if __name__=="__main__":
    raise SystemExit(main())
