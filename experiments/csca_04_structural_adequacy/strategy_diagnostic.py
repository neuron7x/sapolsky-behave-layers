from __future__ import annotations
import json
from pathlib import Path
import sys
import numpy as np
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from cwc.counterfactual.structural_adequacy import best_family_audit, interventional_divergence_audit
from experiments.csca_04_structural_adequacy.common import CONFIRMATORY_FAMILIES, prepare_case, select_probes

SEEDS=range(112000,112004)
STRATEGIES=("BALANCED","DISAGREEMENT_ONLY","CREDIT_PRIORITY","COVERAGE_PLUS_DISAGREEMENT")


def main():
    policy=json.loads((ROOT/'research/results/CSCA-04-SA/FROZEN_POLICY.json').read_text())
    rows=[]
    for seed in SEEDS:
        for family in CONFIRMATORY_FAMILIES:
            case=prepare_case(seed,family)
            for strategy in STRATEGIES:
                probes=select_probes(case,16,strategy)
                supports={}
                for p in probes: supports[(p.candidate,p.context)]=supports.get((p.candidate,p.context),0)+1
                best=best_family_audit(interventional_divergence_audit(case.models,probes))
                rows.append({
                    'seed':seed,'family':family,'expected_adequate':case.expected_adequate,'strategy':strategy,
                    'covered_cells':len(supports),'min_cell_support':min(supports.values()) if supports else 0,
                    'best_max_cell_idr':best.max_cell_idr,
                    'structural_mismatch_flag':best.max_cell_idr>policy['max_cell_idr_threshold'],
                })
    summary={}
    for strategy in STRATEGIES:
        rr=[r for r in rows if r['strategy']==strategy]
        bad=[r for r in rr if not r['expected_adequate']]
        good=[r for r in rr if r['expected_adequate']]
        summary[strategy]={
            'cases':len(rr),
            'full_8_cell_coverage_rate':sum(r['covered_cells']==8 for r in rr)/len(rr),
            'meets_frozen_16_per_cell_support_rate':sum(r['covered_cells']==8 and r['min_cell_support']>=16 for r in rr)/len(rr),
            'diagnostic_bad_family_flag_rate':sum(r['structural_mismatch_flag'] for r in bad)/len(bad),
            'diagnostic_good_family_pass_rate':sum(not r['structural_mismatch_flag'] for r in good)/len(good),
            'median_min_cell_support':float(np.median([r['min_cell_support'] for r in rr])),
        }
    payload={'experiment':'CSCA-04-SA','phase':'P3_SECONDARY_INTERVENTION_ALLOCATION','seed_range':[min(SEEDS),max(SEEDS)],'authority':'DIAGNOSTIC_ONLY','summary':summary,'records':rows}
    out=ROOT/'research/results/CSCA-04-SA/STRATEGY_DIAGNOSTIC.json'; out.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')
    print(json.dumps(summary,indent=2,sort_keys=True))
if __name__=='__main__': main()
