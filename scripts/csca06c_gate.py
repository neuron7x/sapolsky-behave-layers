#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
R=Path(__file__).resolve().parents[1];A=R/'artifacts/csca-06c-position-content';V=R/'research/results/CSCA-06C-R1/verdict.json'
def main()->int:
 e=[]
 for p in (A/'SHA256SUMS',A/'verdict.json',A/'primary/result.json',A/'replication/result.json',V,R/'research/ruins/CSCA-06C-INVALID-SMOKE/BOUNDARY.md'):
  if not p.is_file():e.append('missing '+str(p.relative_to(R)))
 if e:print('CSCA06C-GATE FAIL',*e,sep='\n - ');return 1
 for line in (A/'SHA256SUMS').read_text().splitlines():
  sha,name=line.split('  ',1);p=A/name
  if hashlib.sha256(p.read_bytes()).hexdigest()!=sha:e.append('checksum '+name)
 v=json.loads(V.read_text())
 if v.get('verdict')!='POSITION_CONTENT_MECHANISM_UNRESOLVED' or v.get('scientific_pass') is not False:e.append('final unresolved verdict drift')
 if v.get('content_specific_claim_supported') is not False:e.append('content claim illegally promoted')
 if v.get('position_locality_claim_supported') is not False:e.append('position claim illegally promoted despite replication coverage')
 for k in ('semantic_causality_authorized','student_authorized','replay_authorized','active_control_authorized'):
  if v.get(k) is not False:e.append('illegal promotion '+k)
 pat=v['resolved_case_pattern']
 for k in ('primary_position_tracking','replication_position_tracking'):
  if abs(float(pat[k])-1.0)>1e-12:e.append(k+' drift')
 for k in ('primary_content_tracking','replication_content_tracking'):
  if abs(float(pat[k])-.25)>1e-12:e.append(k+' drift')
 rb=v['replication_coverage_block']
 if not (rb['PROSE']<rb['required'] and rb['pooled']<rb['required']):e.append('replication coverage failure erased')
 if v['prompt_overlap_previous']['primary']!=0 or v['prompt_overlap_previous']['replication']!=0:e.append('prompt overlap')
 if any(v['model_state_mutated'].values()):e.append('model mutation')
 if e:print('CSCA06C-GATE FAIL',*e,sep='\n - ');return 1
 print('CSCA06C-GATE PASS: content-specific credit not supported; position pattern exact on resolved cases but replication coverage blocks promotion.')
 return 0
if __name__=='__main__':sys.exit(main())
