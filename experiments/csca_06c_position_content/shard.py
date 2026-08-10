from __future__ import annotations
import argparse,json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from experiments.csca_06c_position_content.run import ART,PROTOCOL,evaluate_base,fresh_base_specs
from experiments.csca_05_shadow_pilot.runtime_model import load_checkpoint,state_dict_sha256
from experiments.csca_05_shadow_pilot.run import _checkpoint_path

def main():
 ap=argparse.ArgumentParser();ap.add_argument('cohort',choices=['primary','replication']);ap.add_argument('context',choices=['PROSE','CODE']);ap.add_argument('start',type=int);ap.add_argument('--count',type=int,default=4);a=ap.parse_args()
 specs=fresh_base_specs(a.context,a.cohort);end=min(a.start+a.count,len(specs))
 if a.start<0 or a.start>=len(specs) or end-a.start!=a.count:raise SystemExit('invalid shard range')
 model=load_checkpoint(_checkpoint_path(a.cohort));before=state_dict_sha256(model);rows=[]
 for idx in range(a.start,end):
  row=evaluate_base(model,specs[idx],cohort=a.cohort);row['index']=idx;rows.append(row)
 after=state_dict_sha256(model)
 payload={'experiment_id':'CSCA-06C-R1','cohort':a.cohort.upper(),'context':a.context,'start':a.start,'count':a.count,'rows':rows,'model_state_mutated':before!=after}
 out=ART/'staging'/a.cohort/a.context/f'{a.start:02d}-{end-1:02d}.json';out.parent.mkdir(parents=True,exist_ok=True);out.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')
 print(f'SHARD_OK {a.cohort} {a.context} {a.start}:{end} rows={len(rows)} state_mutated={before!=after}')
if __name__=='__main__':main()
