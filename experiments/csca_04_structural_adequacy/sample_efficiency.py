from __future__ import annotations
import argparse, json
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from cwc.counterfactual.structural_adequacy import best_family_audit, interventional_divergence_audit
from experiments.csca_04_structural_adequacy.common import BUDGETS_PER_CELL, CONFIRMATORY_FAMILIES, prepare_case, select_probes


def max_leverage(probes):
    d={}
    for p in probes: d.setdefault(p.candidate,[]).append(abs(p.effect))
    return max(float(np.mean(v)) for v in d.values())


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--label',required=True); ap.add_argument('--start-seed',type=int,required=True); ap.add_argument('--count',type=int,default=64); args=ap.parse_args()
    cal=json.loads((ROOT/'research/results/CSCA-04-SA/CALIBRATION.json').read_text())
    rows=[]
    for seed in range(args.start_seed,args.start_seed+args.count):
        for family in CONFIRMATORY_FAMILIES:
            case=prepare_case(seed,family)
            for b in BUDGETS_PER_CELL:
                probes=select_probes(case,b,'BALANCED')
                best=best_family_audit(interventional_divergence_audit(case.models,probes))
                threshold=cal['idr_thresholds'][str(b)]['max_cell_idr_q99']
                no_lev=max_leverage(probes)<0.1
                detected=(best.max_cell_idr>threshold) or no_lev
                rows.append({'seed':seed,'family':family,'budget_per_cell':b,'expected_adequate':case.expected_adequate,'best_max_cell_idr':best.max_cell_idr,'threshold':threshold,'no_leverage':no_lev,'detected_inadequate':detected})
    summary={}
    for b in BUDGETS_PER_CELL:
        rr=[r for r in rows if r['budget_per_cell']==b]; bad=[r for r in rr if not r['expected_adequate']]; good=[r for r in rr if r['expected_adequate']]
        summary[str(b)]={'sensitivity':sum(r['detected_inadequate'] for r in bad)/len(bad),'specificity':sum(not r['detected_inadequate'] for r in good)/len(good),'cases':len(rr),'threshold':cal['idr_thresholds'][str(b)]['max_cell_idr_q99']}
    payload={'experiment':'CSCA-04-SA','phase':'POST_CONFIRMATORY_SAMPLE_EFFICIENCY','authority':'DIAGNOSTIC_ONLY','label':args.label,'seed_range':[args.start_seed,args.start_seed+args.count-1],'summary':summary,'records':rows}
    out=ROOT/'research/results/CSCA-04-SA'/f'SAMPLE_EFFICIENCY_{args.label}.json'; out.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')
    print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=='__main__': main()
