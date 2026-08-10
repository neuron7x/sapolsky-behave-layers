#!/usr/bin/env python3
import hashlib,json,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];A=R/'artifacts/csca-06a-r1-global-evalue';V=R/'research/results/CSCA-06A-R1/verdict.json'
def main():
 e=[]
 for p in [A/'primary.json',A/'replication.json',A/'verdict.json',A/'SHA256SUMS',V]:
  if not p.is_file():e.append('missing '+str(p.relative_to(R)))
 if e:
  print('CSCA06A-R1-GATE FAIL',*e,sep='\n - ');return 1
 for line in (A/'SHA256SUMS').read_text().splitlines():
  sha,name=line.split('  ',1)
  if hashlib.sha256((A/name).read_bytes()).hexdigest()!=sha:e.append('checksum '+name)
 v=json.loads(V.read_text())
 if v.get('verdict')!='GLOBAL_CHECKPOINT_FALSIFIABILITY_QUALIFIED_NARROWED' or v.get('scientific_pass') is not True:e.append('scientific verdict not qualified')
 for k in ('graph_truth_authorized','shadow_inference_promotion_authorized','replay_authorized','active_causal_control_authorized'):
  if v.get(k) is not False:e.append('illegal promotion '+k)
 for c in ('primary_summary','replication_summary'):
  s=v[c]
  for k in ('N0_NULL_CLEAN','N1_NULL_LATENT_CONFOUNDING','N2_NULL_ALEATORIC','N3_NULL_MIXED_NUISANCE'):
   if s[k]['rejection_rate']>0.02:e.append(c+' '+k+' FPR')
  for k in ('S1_MISSING_TRUE_EDGE','S2_MISSING_TRUE_EDGE_NEGATIVE','S3_SPURIOUS_CANDIDATE_EDGE'):
   if s[k]['rejection_rate']<0.95:e.append(c+' '+k+' power')
  if s['E0_SINGLE_ACTION_EQUIVALENCE']['rejection_count']!=0:e.append(c+' E0')
  if any('GRAPH_COMPONENT_FALSIFIED' in x for x in s['O1_OUT_OF_ENVELOPE_NOISE']['states']):e.append(c+' O1 over-attribution')
 if e:
  print('CSCA06A-R1-GATE FAIL',*e,sep='\n - ');return 1
 print('CSCA06A-R1-GATE PASS: global fixed-checkpoint model-class falsification replicated; no graph-truth promotion.')
 return 0
if __name__=='__main__':sys.exit(main())
