from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

from experiments.csca_04_structural_adequacy.common import (
    CONFIRMATORY_FAMILIES, audit_case, prepare_case, select_probes,
)


def load_policy():
    return json.loads((ROOT/'research/results/CSCA-04-SA/FROZEN_POLICY.json').read_text())


def leverage(probes):
    vals={}
    for p in probes: vals.setdefault(p.candidate,[]).append(abs(p.effect))
    return max((float(np.mean(v)) for v in vals.values()), default=0.0)


def classify(audit, probes, policy):
    if audit.covered_cells < policy['required_cells'] or audit.min_cell_support < policy['min_probes_per_cell']:
        return 'ABSTAIN_INSUFFICIENT_STRUCTURAL_COVERAGE'
    if leverage(probes) < policy['zero_cause_leverage_floor']:
        return 'FALSIFIED_NO_CAUSAL_LEVERAGE'
    if audit.best_max_cell_idr > policy['max_cell_idr_threshold']:
        return 'ABSTAIN_STRUCTURAL_MISSPECIFICATION'
    if audit.context_shift_candidates:
        return 'CONTEXT_CONDITIONAL_ONLY'
    return 'STRUCTURAL_ADEQUACY_ACCEPTED_SYNTHETIC'


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--label',required=True); ap.add_argument('--start-seed',type=int,required=True); ap.add_argument('--count',type=int,default=64)
    args=ap.parse_args(); policy=load_policy(); records=[]
    for seed in range(args.start_seed,args.start_seed+args.count):
        for family in CONFIRMATORY_FAMILIES:
            case=prepare_case(seed,family)
            probes=select_probes(case,policy['primary_budget_per_cell'],policy['primary_strategy'])
            audit=audit_case(case,policy['primary_budget_per_cell'],policy['primary_strategy'],context_z_threshold=policy['context_z_threshold'])
            state=classify(audit,probes,policy)
            records.append({**asdict(audit), 'state': state, 'max_empirical_leverage': leverage(probes)})
    inadequate=[r for r in records if not r['expected_adequate']]
    adequate=[r for r in records if r['expected_adequate']]
    bad_states={'ABSTAIN_STRUCTURAL_MISSPECIFICATION','FALSIFIED_NO_CAUSAL_LEVERAGE','ABSTAIN_INSUFFICIENT_STRUCTURAL_COVERAGE'}
    good_states={'STRUCTURAL_ADEQUACY_ACCEPTED_SYNTHETIC','CONTEXT_CONDITIONAL_ONLY'}
    sensitivity=sum(r['state'] in bad_states for r in inadequate)/len(inadequate)
    specificity=sum(r['state'] in good_states for r in adequate)/len(adequate)
    m6=[r for r in records if r['family']=='M6_ZERO_CAUSE']
    m9=[r for r in records if r['family']=='M9_CONTEXT_SIGN_FLIP']
    m10=[r for r in records if r['family']=='M10_COLLINEAR_IDENTIFIABILITY']
    summary={
        'label':args.label,'seed_range':[args.start_seed,args.start_seed+args.count-1],'cases':len(records),
        'sensitivity_structural_misspecification':sensitivity,'specificity_known_adequate':specificity,
        'm6_global_authority':sum(r['state']=='STRUCTURAL_ADEQUACY_ACCEPTED_SYNTHETIC' for r in m6),
        'm9_global_direction_accept':sum(r['state']=='STRUCTURAL_ADEQUACY_ACCEPTED_SYNTHETIC' for r in m9),
        'm10_accepted':sum(r['state'] in good_states for r in m10),
        'm10_median_factual_rmse':float(np.median([r['factual_rmse'] for r in m10])),
        'state_counts':{s:sum(r['state']==s for r in records) for s in sorted(set(r['state'] for r in records))},
        'family_state_counts':{fam:{s:sum(r['family']==fam and r['state']==s for r in records) for s in sorted(set(r['state'] for r in records))} for fam in CONFIRMATORY_FAMILIES},
    }
    summary['qualification_pass']=bool(sensitivity>=0.95 and specificity>=0.95 and summary['m6_global_authority']==0 and summary['m9_global_direction_accept']==0 and summary['m10_accepted']==0)
    outdir=ROOT/'research/results/CSCA-04-SA'; outdir.mkdir(parents=True,exist_ok=True)
    out={'experiment':'CSCA-04-SA','policy':policy,'summary':summary,'records':records}
    path=outdir/f'{args.label}.json'; path.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
    print(json.dumps(summary,indent=2,sort_keys=True))
    return 0 if summary['qualification_pass'] else 3

if __name__=='__main__': raise SystemExit(main())
