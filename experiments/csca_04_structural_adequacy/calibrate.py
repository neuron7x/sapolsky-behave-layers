from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cwc.counterfactual.structural_adequacy import best_family_audit, context_effect_audits, interventional_divergence_audit
from experiments.csca_04_structural_adequacy.common import (
    BUDGETS_PER_CELL, CALIBRATION_FAMILIES, TRUE_CAUSAL_SETS, prepare_case, select_probes,
)

SEEDS = range(82000, 82064)
STRATEGY = "BALANCED"


def q99(xs):
    return float(np.quantile(np.asarray(xs, dtype=float), 0.99, method="higher"))


def main() -> int:
    idrs={b:[] for b in BUDGETS_PER_CELL}
    znull={b:[] for b in BUDGETS_PER_CELL}
    records=[]
    for seed in SEEDS:
        for family in CALIBRATION_FAMILIES:
            case=prepare_case(seed,family)
            for budget in BUDGETS_PER_CELL:
                probes=select_probes(case,budget,STRATEGY)
                best=best_family_audit(interventional_divergence_audit(case.models,probes))
                idrs[budget].append(best.max_cell_idr)
                if family != "C1_CONTEXT_SIGN":
                    for ctx in context_effect_audits(probes):
                        if ctx.candidate in TRUE_CAUSAL_SETS[family] and not ctx.sign_flip:
                            znull[budget].append(ctx.standardized_difference)
                records.append({"seed":seed,"family":family,"budget_per_cell":budget,"best_family":best.family,"best_idr":best.idr,"best_max_cell_idr":best.max_cell_idr})
    thresholds={str(b):{"max_cell_idr_q99":q99(idrs[b]),"median":float(np.median(idrs[b])),"max":float(np.max(idrs[b])),"n":len(idrs[b])} for b in BUDGETS_PER_CELL}
    context_thresholds={str(b):{"stable_context_z_q99":q99(znull[b]),"n":len(znull[b])} for b in BUDGETS_PER_CELL}
    payload={"experiment":"CSCA-04-SA","phase":"P4_CALIBRATION","seed_range":[min(SEEDS),max(SEEDS)],"families":list(CALIBRATION_FAMILIES),"strategy":STRATEGY,"idr_thresholds":thresholds,"context_thresholds":context_thresholds,"primary_budget_per_cell":16,"primary_max_cell_idr_threshold":thresholds["16"]["max_cell_idr_q99"],"primary_context_z_threshold":context_thresholds["16"]["stable_context_z_q99"],"authority":"CALIBRATION_ONLY","records":records}
    out=ROOT/"research/results/CSCA-04-SA"; out.mkdir(parents=True,exist_ok=True)
    (out/"CALIBRATION.json").write_text(json.dumps(payload,indent=2,sort_keys=True)+"\n")
    print(json.dumps({k:v for k,v in payload.items() if k!="records"},indent=2,sort_keys=True))
    return 0

if __name__ == "__main__": raise SystemExit(main())
