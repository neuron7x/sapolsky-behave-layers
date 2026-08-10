from __future__ import annotations
import argparse,csv,json,math
from pathlib import Path
BUDGETS=(8,16,32,64,128,256)

def load(p):
 with p.open(newline='') as f:return list(csv.DictReader(f))
def sel(rows,fam,method,b):return [r for r in rows if r['family']==fam and r['method']==method and int(r['budget'])==b]
def mean(xs):return sum(xs)/len(xs) if xs else 0.0
def mse(rows,field='rmse_true_teacher'):return mean([float(r[field])**2 for r in rows])
def rmse(rows,field='rmse_true_teacher'):return math.sqrt(mse(rows,field))
def maxfalse(rows):return max(float(r['false_credit_mass_true']) for r in rows)
def topset(rows):return mean([float(r['topset_recovery']) for r in rows])
def meanmodel(rows):return mean([float(r['model_teacher_false_mass_true']) for r in rows])
def meanvar(rows):return mean([float(r['max_estimator_variance']) for r in rows])

def evaluate(primary:Path,replication:Path)->dict:
 p=load(primary/'case_results.csv'); r=load(replication/'case_results.csv'); pa=load(primary/'context_authority.csv');ra=load(replication/'context_authority.csv')
 predicates={}; diagnostics={'metric_definition':'aggregate_MSE=mean(per_row_RMSE^2)'}
 for name,table in (('primary',p),('replication',r)):
  predicates[f'{name}_e0_crn_zero_false']=all(maxfalse(sel(table,'E0_SINGLE_CAUSE','CRN_CHAIN_MC',b))<=1e-12 for b in BUDGETS)
  predicates[f'{name}_e0_crn_beats_legacy']=all(rmse(sel(table,'E0_SINGLE_CAUSE','CRN_CHAIN_MC',b))<rmse(sel(table,'E0_SINGLE_CAUSE','LEGACY_INDEPENDENT_MC',b)) for b in BUDGETS)
  predicates[f'{name}_e0_crn_topset']=all(topset(sel(table,'E0_SINGLE_CAUSE','CRN_CHAIN_MC',b))==1.0 for b in BUDGETS)
  predicates[f'{name}_e1_crn_zero_false']=all(maxfalse(sel(table,'E1_TWO_CAUSE_INTERACTION','CRN_CHAIN_MC',b))<=1e-12 for b in BUDGETS)
  ratios={};wins=0
  for b in BUDGETS:
   ratio=mse(sel(table,'E1_TWO_CAUSE_INTERACTION','ANTITHETIC_CRN_MC',b))/mse(sel(table,'E1_TWO_CAUSE_INTERACTION','CRN_CHAIN_MC',b))
   ratios[str(b)]=ratio; wins+=ratio<=0.90
  diagnostics[f'{name}_e1_antithetic_mse_ratio']=ratios
  predicates[f'{name}_e1_antithetic_4of6']=wins>=4
 predicates['primary_context_no_global_direction']=all(x['state']!='GLOBAL_DIRECTION_ACCEPT' for x in pa)
 predicates['replication_context_no_global_direction']=all(x['state']!='GLOBAL_DIRECTION_ACCEPT' for x in ra)
 e3={};checks=[]
 for name,table in (('primary',p),('replication',r)):
  for b in (64,128,256):
   rows=sel(table,'E3_PRECISELY_WRONG_MODEL','ANTITHETIC_CRN_MC',b); key=f'{name}:{b}'
   e3[key]={'rmse_to_wrong_model_teacher':rmse(rows,'rmse_model_teacher'),'wrong_model_false_mass':meanmodel(rows),'mean_reported_estimator_variance':meanvar(rows)}
   checks.append(e3[key]['rmse_to_wrong_model_teacher']<=1e-12 and e3[key]['wrong_model_false_mass']>=0.5 and e3[key]['mean_reported_estimator_variance']<=1e-12)
 diagnostics['variance_only_counterexample']=e3; predicates['variance_only_authority_counterexample']=all(checks)
 core=all(v for k,v in predicates.items() if not k.endswith('antithetic_4of6'))
 anti=predicates['primary_e1_antithetic_4of6'] and predicates['replication_e1_antithetic_4of6']
 verdict='CSCA_03R_COUPLED_ESTIMATOR_NOT_QUALIFIED' if not core else ('CSCA_03R_COUPLED_QUALIFIED_ANTITHETIC_NOT_QUALIFIED' if not anti else 'CSCA_03R_COUPLED_ESTIMATOR_QUALIFIED')
 return {'experiment_id':'CSCA-03R','analyzer_version':'1.0-fresh-deterministic-baseline','verdict':verdict,'scientific_pass':verdict=='CSCA_03R_COUPLED_ESTIMATOR_QUALIFIED','predicates':predicates,'diagnostics':diagnostics,'architecture_promotion_authority':False,'shadow_inference_authority':False,'variance_only_authority':False,'human_h5_required':True}

def main():
 q=argparse.ArgumentParser();q.add_argument('--primary',type=Path,required=True);q.add_argument('--replication',type=Path,required=True);q.add_argument('--out',type=Path,required=True);a=q.parse_args();d=evaluate(a.primary,a.replication);a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d,indent=2,sort_keys=True))
if __name__=='__main__':main()
