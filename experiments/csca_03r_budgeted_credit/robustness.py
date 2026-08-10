from __future__ import annotations
import argparse,csv,json,math
from collections import Counter
from pathlib import Path
from experiments.csca_03_budgeted_credit.environment import generate_cases,make_evaluator
B=(8,16,32,64,128,256); CEIL=0.00791605240667618

def load(p):
 with p.open(newline='') as f:return list(csv.DictReader(f))
def sel(rows,f,m,b):return [r for r in rows if r['family']==f and r['method']==m and int(r['budget'])==b]
def mean(xs):return sum(xs)/len(xs)
def mse(rows,field='rmse_true_teacher'):return mean([float(r[field])**2 for r in rows])
def rmse(rows,field='rmse_true_teacher'):return math.sqrt(mse(rows,field))
def factual_rmse(seed_start,count):
 errs=[]
 for seed in range(seed_start,seed_start+count):
  for case in generate_cases(family='E3_PRECISELY_WRONG_MODEL',seed=seed,n=8):
   t=make_evaluator(case,model='TRUE')(case.factual);w=make_evaluator(case,model='WRONG_SHARED_SPURIOUS_EDGE')(case.factual);errs.append((w-t)**2)
 return math.sqrt(mean(errs))

def cohort(path:Path,seed_start:int)->dict:
 rows=load(path/'case_results.csv');auth=load(path/'context_authority.csv')
 ratios={}
 for b in B:
  ratios[str(b)]=mse(sel(rows,'E1_TWO_CAUSE_INTERACTION','ANTITHETIC_CRN_MC',b))/mse(sel(rows,'E1_TWO_CAUSE_INTERACTION','CRN_CHAIN_MC',b))
 nonnec={}
 for b in B:
  rr=sel(rows,'E0_SINGLE_CAUSE','CRN_CHAIN_MC',b)
  nonnec[str(b)]={'mean_max_component_estimator_variance':mean([float(r['max_estimator_variance']) for r in rr]),'max_false_credit_mass':max(float(r['false_credit_mass_true']) for r in rr),'exceeds_diagnostic_ceiling':mean([float(r['max_estimator_variance']) for r in rr])>CEIL}
 wrong={}
 for b in (64,128,256):
  rr=sel(rows,'E3_PRECISELY_WRONG_MODEL','ANTITHETIC_CRN_MC',b)
  wrong[str(b)]={'mean_estimator_variance':mean([float(r['max_estimator_variance']) for r in rr]),'rmse_to_wrong_model_teacher':rmse(rr,'rmse_model_teacher'),'rmse_to_true_teacher':rmse(rr,'rmse_true_teacher'),'mean_false_credit_mass_true':mean([float(r['false_credit_mass_true']) for r in rr])}
 return {'antithetic_mse_ratio':ratios,'context_authority_states':dict(Counter(r['state'] for r in auth)),'variance_ceiling_nonnecessity':nonnec,'precisely_wrong_model':wrong,'precisely_wrong_model_factual_rmse':factual_rmse(seed_start,128)}

def main():
 p=argparse.ArgumentParser();p.add_argument('--primary',type=Path,required=True);p.add_argument('--replication',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d={'status':'POST_CONFIRMATORY_ROBUSTNESS_NO_CLAIM_UPGRADE_AUTHORITY','variance_diagnostic_ceiling':CEIL,'primary':cohort(a.primary,62000),'replication':cohort(a.replication,72000)};a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d,indent=2,sort_keys=True))
if __name__=='__main__':main()
