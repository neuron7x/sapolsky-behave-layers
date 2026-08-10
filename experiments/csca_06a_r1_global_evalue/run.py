from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))

import numpy as np

from cwc.counterfactual.falsifiability import (
    AlternativeComponent, FixedCheckpointCompositeEValue, GaussianInterventionalLaw,
    InterventionDesign, NuisanceEnvelope, model_class_falsifiability_state,
    separation_rate_per_cost,
)
from experiments.csca_06a_falsifiability.run import Family, FAMILIES

PROTOCOL=json.loads(Path(__file__).with_name('protocol.json').read_text())
NUIS=NuisanceEnvelope(**PROTOCOL['nuisance_envelope'])
COSTS={float(k):float(v) for k,v in PROTOCOL['action_costs'].items()}
DESIGN=InterventionDesign({float(k):int(v) for k,v in PROTOCOL['confirmatory_block'].items()},COSTS)
ART=ROOT/'artifacts/csca-06a-r1-global-evalue'
RES=ROOT/'research/results/CSCA-06A-R1'


def alt(model_slope: float):
    return [AlternativeComponent(model_slope+off,h,sd) for off in PROTOCOL['alternative_slope_offsets'] for h in (-.5,0.,.5) for sd in (.8,1.2,1.8)]


def draw(rng,fam,design):
    return [fam.true_slope*a+fam.intercept+fam.gamma*float(rng.normal())+fam.sigma*float(rng.normal()) for a in design.actions]


def run_one(fam:Family, seed:int, design=DESIGN):
    law=GaussianInterventionalLaw(fam.true_slope,fam.intercept,fam.total_sd)
    rate=separation_rate_per_cost(law,design,model_slope=fam.model_slope,nuisance=NUIS)
    if design.distinct_actions<2:
        return {'seed':seed,'rejected':False,'cost':0.0,'separation_rate_per_cost':rate,'state':'UNRESOLVED_INTERVENTIONAL_EQUIVALENCE','looks':[]}
    p=FixedCheckpointCompositeEValue(model_slope=fam.model_slope,nuisance=NUIS,alternative=alt(fam.model_slope),alpha=PROTOCOL['alpha'],checkpoints_cost=PROTOCOL['checkpoint_costs'],max_cost=PROTOCOL['max_cost'])
    rng=np.random.default_rng(seed); looks=[]
    while p.cost < PROTOCOL['max_cost']-1e-12 and not p.rejected:
        rec=p.add_block(draw(rng,fam,design),design)
        if rec['checkpoint']: looks.append(rec)
    final_log=looks[-1]['log_e'] if looks else None
    state=model_class_falsifiability_state(separation_rate=rate,observed_rejection=p.rejected,nuisance_scope_certified=fam.nuisance_scope_certified,budget_exhausted=(not p.rejected and p.cost>=PROTOCOL['max_cost']-1e-12))
    return {'seed':seed,'rejected':p.rejected,'cost':p.cost,'separation_rate_per_cost':rate,'state':state,'looks':looks,'final_log_e':final_log}


def metrics(rows):
    rej=[r for r in rows if r['rejected']]
    return {'n':len(rows),'rejection_count':len(rej),'rejection_rate':len(rej)/len(rows),'median_cost_if_rejected':statistics.median([r['cost'] for r in rej]) if rej else None,'separation_rate_per_cost':rows[0]['separation_rate_per_cost'],'states':{s:sum(r['state']==s for r in rows) for s in sorted({r['state'] for r in rows})}}


def cohort(name,base):
    out={}
    n=PROTOCOL['seeds_per_family']
    for fi,fam in enumerate(FAMILIES):
        rows=[run_one(fam,base+fi*1000+i) for i in range(n)]
        out[fam.family_id]={'family':asdict(fam),'metrics':metrics(rows),'rows':rows}
    e=Family('E0_SINGLE_ACTION_EQUIVALENCE',0.0,0.7,0.0,0.0,1.0,'INTERVENTIONALLY_EQUIVALENT')
    ed=InterventionDesign({1.0:8},{1.0:1.0})
    rows=[run_one(e,base+99000+i,ed) for i in range(n)]
    out[e.family_id]={'family':asdict(e),'metrics':metrics(rows),'rows':rows}
    return {'cohort':name,'families':out}


def gate(c):
    f=c['families']; errors=[]
    nulls=('N0_NULL_CLEAN','N1_NULL_LATENT_CONFOUNDING','N2_NULL_ALEATORIC','N3_NULL_MIXED_NUISANCE')
    nr=sum(f[k]['metrics']['rejection_count'] for k in nulls); nn=sum(f[k]['metrics']['n'] for k in nulls)
    if nr/nn>0.01: errors.append('pooled null FPR >0.01')
    for k in nulls:
        if f[k]['metrics']['rejection_rate']>0.02: errors.append(k+' FPR >0.02')
    for k in ('S1_MISSING_TRUE_EDGE','S2_MISSING_TRUE_EDGE_NEGATIVE','S3_SPURIOUS_CANDIDATE_EDGE'):
        if f[k]['metrics']['rejection_rate']<0.95: errors.append(k+' power <0.95')
    if f['E0_SINGLE_ACTION_EQUIVALENCE']['metrics']['rejection_count']!=0: errors.append('E0 false reject')
    if any('GRAPH_COMPONENT_FALSIFIED' in s for s in f['O1_OUT_OF_ENVELOPE_NOISE']['metrics']['states']): errors.append('O1 topology over-attribution')
    return not errors,errors


def write(p,obj): p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2,sort_keys=True)+'\n')

def main():
    ART.mkdir(parents=True,exist_ok=True);RES.mkdir(parents=True,exist_ok=True)
    p=cohort('PRIMARY',PROTOCOL['primary_seed_start']); r=cohort('REPLICATION',PROTOCOL['replication_seed_start'])
    pp,pe=gate(p); rp,re=gate(r)
    write(ART/'primary.json',p);write(ART/'replication.json',r)
    summary=lambda c:{k:v['metrics'] for k,v in c['families'].items()}
    v={'experiment_id':'CSCA-06A-R1','parent_verdict':'INTERVENTIONAL_FALSIFIABILITY_INSTRUMENT_NOT_QUALIFIED','verdict':'GLOBAL_CHECKPOINT_FALSIFIABILITY_QUALIFIED_NARROWED' if pp and rp else 'GLOBAL_CHECKPOINT_FALSIFIABILITY_NOT_QUALIFIED','scientific_pass':pp and rp,'primary_pass':pp,'replication_pass':rp,'primary_errors':pe,'replication_errors':re,'alpha':PROTOCOL['alpha'],'checkpoint_alpha':PROTOCOL['alpha']/len(PROTOCOL['checkpoint_costs']),'checkpoint_evalue_threshold':len(PROTOCOL['checkpoint_costs'])/PROTOCOL['alpha'],'max_cost':PROTOCOL['max_cost'],'graph_truth_authorized':False,'shadow_inference_promotion_authorized':False,'replay_authorized':False,'active_causal_control_authorized':False,'primary_summary':summary(p),'replication_summary':summary(r),'boundary':'Composite model-class falsification only; omitted nuisance mechanisms can mimic topology failure and latent-vs-aleatoric variance remains non-identifiable from scalar Y.'}
    write(RES/'verdict.json',v);write(ART/'verdict.json',v)
    files=[x for x in sorted(ART.rglob('*')) if x.is_file() and x.name!='SHA256SUMS']
    (ART/'SHA256SUMS').write_text(''.join(f"{hashlib.sha256(x.read_bytes()).hexdigest()}  {x.relative_to(ART)}\n" for x in files))
    print(json.dumps({'verdict':v['verdict'],'primary_pass':pp,'replication_pass':rp},indent=2))

if __name__=='__main__': main()
