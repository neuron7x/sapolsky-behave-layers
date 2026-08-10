#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1]; A=R/'artifacts/csca-06b-operator-robustness'; V=R/'research/results/CSCA-06B-OP/verdict.json'
def main()->int:
 e=[]
 for p in (A/'SHA256SUMS',A/'verdict.json',A/'primary/result.json',A/'replication/result.json',A/'calibration/frozen_policy.json',V):
  if not p.is_file():e.append('missing '+str(p.relative_to(R)))
 if e: print('CSCA06B-GATE FAIL',*e,sep='\n - ');return 1
 for line in (A/'SHA256SUMS').read_text().splitlines():
  sha,name=line.split('  ',1);p=A/name
  if hashlib.sha256(p.read_bytes()).hexdigest()!=sha:e.append('checksum '+name)
 v=json.loads(V.read_text())
 if v.get('verdict')!='OPERATOR_FAMILY_ROBUSTNESS_QUALIFIED_NARROWED' or v.get('scientific_pass') is not True:e.append('verdict drift')
 for key in ('semantic_causality_authorized','amortized_student_authorized','replay_authorized','active_control_authorized'):
  if v.get(key) is not False:e.append('illegal promotion '+key)
 for cohort in ('primary_metrics','replication_metrics'):
  for stratum in ('pooled','PROSE','CODE'):
   m=v[cohort][stratum]
   if m['top_agreement_rate']<.90:e.append(cohort+'/'+stratum+' top agreement')
   if m['sign_agreement_rate']<.90:e.append(cohort+'/'+stratum+' sign agreement')
   if m['robust_authority_coverage']<.50:e.append(cohort+'/'+stratum+' coverage')
 if v['prompt_overlap_with_csca05']['primary']!=0 or v['prompt_overlap_with_csca05']['replication']!=0:e.append('prompt overlap')
 if any(v['model_state_mutated'].values()):e.append('model mutation')
 b=v['recency_boundary']
 if b['primary_robust_nonrecent']!=0 or b['replication_robust_nonrecent']!=0:e.append('recency boundary drift')
 if b['architectural_utility_status']!='BLOCKED_RECENCY_DOMINATED_ZERO_NONRECENT_ROBUST_CASES':e.append('architectural utility improperly unblocked')
 if e: print('CSCA06B-GATE FAIL',*e,sep='\n - ');return 1
 print('CSCA06B-GATE PASS: operator-family robustness qualified, but all robust cases are A_RECENT; semantic/student promotion remains blocked.')
 return 0
if __name__=='__main__':sys.exit(main())
