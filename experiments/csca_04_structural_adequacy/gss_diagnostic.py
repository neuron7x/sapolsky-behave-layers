from __future__ import annotations
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from experiments.csca_04_structural_adequacy.common import audit_case, prepare_case

SEEDS=range(113000,113016)
FAMILIES=('C0_LINEAR','M1_SHARED_WRONG_EDGE','M10_COLLINEAR_IDENTIFIABILITY')

def main():
    policy=json.loads((ROOT/'research/results/CSCA-04-SA/FROZEN_POLICY.json').read_text())
    rows=[]
    for seed in SEEDS:
        for family in FAMILIES:
            case=prepare_case(seed,family)
            a=audit_case(case,16,'BALANCED',context_z_threshold=policy['context_z_threshold'],compute_gss=True)
            rows.append({
                'seed':seed,'family':family,'true_causal_set':list(a.true_causal_set),
                'gss_top_factual_candidate':a.gss_top_factual_candidate,
                'gss_top_interventional_candidate':a.gss_top_interventional_candidate,
                'best_max_cell_idr':a.best_max_cell_idr,
                'factual_rmse':a.factual_rmse,
            })
    summary={}
    for family in FAMILIES:
        rr=[r for r in rows if r['family']==family]
        summary[family]={
            'n':len(rr),
            'gss_factual_top_is_true_cause_rate':sum(r['gss_top_factual_candidate'] in r['true_causal_set'] for r in rr)/len(rr),
            'gss_factual_top_C_rate':sum(r['gss_top_factual_candidate']=='C' for r in rr)/len(rr),
            'idr_reject_rate':sum(r['best_max_cell_idr']>policy['max_cell_idr_threshold'] for r in rr)/len(rr),
        }
    payload={'experiment':'CSCA-04-SA','phase':'P6_GSS_DIAGNOSTIC','authority':'DIAGNOSTIC_ONLY','seed_range':[min(SEEDS),max(SEEDS)],'summary':summary,'records':rows}
    (ROOT/'research/results/CSCA-04-SA/GSS_DIAGNOSTIC.json').write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')
    print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=='__main__': main()
