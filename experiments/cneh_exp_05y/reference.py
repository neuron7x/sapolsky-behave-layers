"""Independent comparison of the new arithmetic lineage to sealed H references."""
import argparse
import os
from pathlib import Path

from experiments.cneh_exp_05j import run as j
from experiments.cneh_exp_05j import verify as v
from experiments.cneh_exp_05x import verify as x
from experiments.cneh_exp_05x import worlds as w
from experiments.cneh_exp_05y import portable as p


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--index",type=int,choices=range(8),required=True)
    ap.add_argument("--archives",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    ep,initial,tape,reference=j.inputs(args.archives,args.index)
    world={"id":args.index,"arm":ep["arm"],"initial":[[w.hx(z) for z in row] for row in initial],
           "external":[[w.hx(t/10.) for t in range(512) if tape[t,i]] for i in range(32)],
           "mode_order":[0,1,2,3],"switches":[w.hx(t) for t in (12.8,25.6,38.4)],
           "current_switches":[w.hx(t) for t in w.CURRENT]}
    result=p.simulate(world)
    check=x.audit(world,result)
    physical=result["physical"]
    times=v.event_times(physical)
    comparisons=[{"reference":name,**v.comparison(physical["samples"],times,ref["states"],ref["events"])}
                 for name,ref in reference.items()]
    report={"index":args.index,"seed":ep["seed"],"arm":ep["arm"],"head_sha":os.environ["HEAD_SHA"],
            "run_id":os.environ["GITHUB_RUN_ID"],"comparisons":comparisons,"boundary_audit":check,
            "physical_sha256":result["physical_sha256"],"trace_sha256":result["trace_sha256"],
            "status":"PASS_FINITE" if all(c["status"]=="PASS_FINITE" for c in comparisons) else "FAIL",
            "scientific_promotion_authorized":False,"scientific_promotion":"BLOCKED"}
    args.out.mkdir()
    data=w.canonical(report)
    (args.out/"report.json").write_bytes(data)
    (args.out/"SHA256SUMS").write_text(w.sha(data)+"  report.json\n")
    print(data.decode(),end="")


if __name__=="__main__":
    main()
