from __future__ import annotations
import argparse,json,time
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from experiments.csca_06c_position_content.run import ART,PROTOCOL,_all_previous_prompt_hashes,_json,classify,metrics

def main():
 ap=argparse.ArgumentParser();ap.add_argument('cohort',choices=['primary','replication']);a=ap.parse_args();rows=[];mut=[]
 n=int(PROTOCOL['prompts_per_context']);expected=set(range(n))
 for context in PROTOCOL['contexts']:
  got=[]
  for path in sorted((ART/'staging'/a.cohort/context).glob('*.json')):
   d=json.loads(path.read_text());
   if d['cohort']!=a.cohort.upper() or d['context']!=context:raise RuntimeError('shard identity mismatch')
   mut.append(bool(d['model_state_mutated']));got.extend(d['rows'])
  inds=[int(r['index']) for r in got]
  if set(inds)!=expected or len(inds)!=n:raise RuntimeError(f'incomplete/duplicate shard set {context}: {inds}')
  rows.extend(sorted(got,key=lambda r:int(r['index'])))
 old=_all_previous_prompt_hashes();overlap=sum(r['prompt_hash'] in old for r in rows)
 hashes=[r['prompt_hash'] for r in rows]
 if len(set(hashes))!=len(hashes):raise RuntimeError('duplicate prompt hash across cohort')
 strata={'pooled':metrics(rows)}
 for c in PROTOCOL['contexts']:strata[c]=metrics([r for r in rows if r['context']==c])
 checks=classify(strata);mutation=any(mut)
 if checks['content_pass'] and not mutation and overlap==0:verdict='CONTENT_SPECIFIC_CAUSAL_CREDIT_QUALIFIED_NARROWED'
 elif checks['position_pass'] and not mutation and overlap==0:verdict='POSITION_LOCALITY_EXPLANATION_SUPPORTED_NARROWED'
 else:verdict='POSITION_CONTENT_MECHANISM_UNRESOLVED'
 payload={'experiment_id':'CSCA-06C-R1','cohort':a.cohort.upper(),'verdict':verdict,'metrics':strata,'decision_checks':checks,'prompt_overlap_previous':overlap,'model_state_mutated':mutation,'logical_intervention_realizations':sum(r['logical_intervention_realizations'] for r in rows),'physical_model_batch_calls':sum(r['physical_model_batch_calls'] for r in rows),'semantic_causality_authorized':False,'student_authorized':False,'replay_authorized':False,'active_control':False}
 _json(ART/f'{a.cohort}/rows.json',rows);_json(ART/f'{a.cohort}/result.json',payload);print(json.dumps(payload,indent=2,sort_keys=True))
if __name__=='__main__':main()
