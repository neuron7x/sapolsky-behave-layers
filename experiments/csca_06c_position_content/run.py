from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path
import statistics
import sys
import time
from typing import FrozenSet

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

import torch
import torch.nn.functional as F

from cwc.credit.ablation_shapley import exact_ablation_shapley
from experiments.csca_05_shadow_pilot.direct_credit import PLAYERS, PromptInterventionSpec, candidate_spans
from experiments.csca_05_shadow_pilot.runtime_model import CODE_MARKER,PROSE_MARKER,load_checkpoint,state_dict_sha256
from experiments.csca_05_shadow_pilot.run import CONTEXT_FILES,_checkpoint_path
from experiments.csca_06b_operator_robustness.run import score_pair

PROTOCOL=json.loads((ROOT/'experiments/csca_06c_position_content/protocol.json').read_text())
ART=ROOT/'artifacts/csca-06c-position-content'
MARKER={'PROSE':PROSE_MARKER,'CODE':CODE_MARKER}
POSITIONS=tuple(PLAYERS)


def _json(path:Path,payload)->None:
 path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n')


def _read(paths:list[Path])->bytes:return b'\n'.join(p.read_bytes() for p in paths)


def _all_previous_prompt_hashes()->set[str]:
 out=set()
 cal=ROOT/'artifacts/csca-05-runtime/calibration/raw_records.json'
 if cal.is_file():out.update(str(x['prompt_hash']) for x in json.loads(cal.read_text()))
 for cohort in ('primary','replication'):
  for p in (ROOT/f'artifacts/csca-05-runtime/{cohort}/traces').glob('*.json'):out.add(str(json.loads(p.read_text())['prompt_hash']))
 diag=ROOT/'artifacts/csca-05-runtime/diagnostics/intervention_semantics/rows.json'
 if diag.is_file():out.update(str(x['prompt_hash']) for x in json.loads(diag.read_text()))
 for path in [ROOT/'artifacts/csca-06b-operator-robustness/calibration/rows.json',ROOT/'artifacts/csca-06b-operator-robustness/primary/rows.json',ROOT/'artifacts/csca-06b-operator-robustness/replication/rows.json']:
  if path.is_file():out.update(str(x['prompt_hash']) for x in json.loads(path.read_text()))
 return out


def _source(context:str,cohort:str)->bytes:return _read(CONTEXT_FILES[context][cohort])


def fresh_base_specs(context:str,cohort:str)->list[PromptInterventionSpec]:
 raw=_source(context,cohort);content=40;n=int(PROTOCOL['prompts_per_context']);old=_all_previous_prompt_hashes();used=set();specs=[]
 for i in range(n):
  digest=hashlib.sha256(f'CSCA06C-R1:PROMPT:{cohort}:{context}:{i}'.encode()).digest();off=int.from_bytes(digest[:8],'big')%(len(raw)-content);attempts=0
  while True:
   tokens=(MARKER[context],*raw[off:off+content]);spec=PromptInterventionSpec(tuple(int(x) for x in tokens),context,candidate_spans(len(tokens)))
   if off not in used and spec.prompt_hash not in old and all(spec.prompt_hash!=s.prompt_hash for s in specs):break
   off=(off+1)%(len(raw)-content);attempts+=1
   if attempts>len(raw):raise RuntimeError('unable to allocate fresh CSCA06C prompt')
  used.add(off);specs.append(spec)
 return specs


def original_blocks(spec:PromptInterventionSpec)->dict[str,tuple[int,...]]:
 return {p:tuple(spec.prompt_tokens[a:b]) for p,(a,b) in spec.spans.items()}


def rotation_mapping(rotation:int)->dict[str,str]:
 if rotation not in range(4):raise ValueError(rotation)
 return {pos:POSITIONS[(i-rotation)%4] for i,pos in enumerate(POSITIONS)}


def rotated_spec(base:PromptInterventionSpec,rotation:int)->tuple[PromptInterventionSpec,dict[str,str]]:
 blocks=original_blocks(base);mapping=rotation_mapping(rotation);tokens=list(base.prompt_tokens)
 for pos,identity in mapping.items():
  a,b=base.spans[pos];tokens[a:b]=blocks[identity]
 return PromptInterventionSpec(tuple(tokens),base.context,dict(base.spans)),mapping


def _pool(context:str,cohort:str,kernel:str)->bytes:
 if kernel=='K_TRAIN_CONTIG8':return CONTEXT_FILES[context]['train'].read_bytes()
 if kernel=='K_COHORT_CONTIG8':return _source(context,cohort)
 raise ValueError(kernel)


def shared_donors(base:PromptInterventionSpec,*,cohort:str,kernel:str)->tuple[dict[str,tuple[int,...]],...]:
 pool=_pool(base.context,cohort,kernel); forbidden=set(original_blocks(base).values());n=int(PROTOCOL['donor_assignments_per_kernel']);rows=[]
 for draw in range(n):
  row={}
  for pos in POSITIONS:
   digest=hashlib.sha256(f'CSCA06C:DONOR:{cohort}:{base.context}:{kernel}:{base.prompt_hash}:{pos}:{draw}'.encode()).digest();off=int.from_bytes(digest[:8],'big')%(len(pool)-4);attempt=0
   rep=tuple(int(x) for x in pool[off:off+4])
   while rep in forbidden:
    off=(off+1)%(len(pool)-4);rep=tuple(int(x) for x in pool[off:off+4]);attempt+=1
    if attempt>len(pool):raise RuntimeError('no admissible donor')
   row[pos]=rep
  rows.append(row)
 return tuple(rows)


@torch.inference_mode()
def base_target(model,spec:PromptInterventionSpec)->int:
 ids=torch.tensor([list(spec.prompt_tokens)],dtype=torch.long,device=model.get_device());lp=F.log_softmax(model(ids)[:,-1,:],dim=-1)[0];return int(torch.argmax(lp).item())

@torch.inference_mode()
def target_batch(model,prompts:list[list[int]],target:int)->list[float]:
 ids=torch.tensor(prompts,dtype=torch.long,device=model.get_device());lp=F.log_softmax(model(ids)[:,-1,:],dim=-1);return [float(x) for x in lp[:,target].cpu().tolist()]




def precomputed_finite_game(model,spec:PromptInterventionSpec,donors:tuple[dict[str,tuple[int,...]],...],target:int):
 coalitions=[]
 for r in range(len(POSITIONS)+1):
  for combo in itertools.combinations(POSITIONS,r):coalitions.append(frozenset(combo))
 prompts=[]
 for keep in coalitions:
  for row in donors:
   x=list(spec.prompt_tokens)
   for p,(a,b) in spec.spans.items():
    if p not in keep:x[a:b]=row[p]
   prompts.append(x)
 vals=target_batch(model,prompts,target)
 game={}
 n=len(donors)
 for i,keep in enumerate(coalitions):game[keep]=float(sum(vals[i*n:(i+1)*n])/n)
 return game, len(prompts), 1

class FixedTargetFiniteKernelOracle:
 def __init__(self,model,spec:PromptInterventionSpec,donors:tuple[dict[str,tuple[int,...]],...],target:int):
  self.model=model;self.spec=spec;self.donors=donors;self.target=target;self.logical=0;self.batch_calls=0
 def __call__(self,keep:FrozenSet[str])->float:
  prompts=[]
  for row in self.donors:
   x=list(self.spec.prompt_tokens)
   for p,(a,b) in self.spec.spans.items():
    if p not in keep:x[a:b]=row[p]
   prompts.append(x)
  vals=target_batch(self.model,prompts,self.target);self.logical+=len(prompts);self.batch_calls+=1
  return float(sum(vals)/len(vals))


def evaluate_base(model,base:PromptInterventionSpec,*,cohort:str)->dict:
 target=base_target(model,base);donors={k:shared_donors(base,cohort=cohort,kernel=k) for k in PROTOCOL['operator_kernels']};rots=[];total_logical=0;total_batches=1
 for r in range(4):
  spec,mapping=rotated_spec(base,r);credits={};counts={}
  for k in PROTOCOL['operator_kernels']:
   game,logical,batches=precomputed_finite_game(model,spec,donors[k],target)
   est=exact_ablation_shapley(POSITIONS,lambda keep,g=game:g[frozenset(keep)])
   credits[k]=est.credits;counts[k]={'logical':logical,'batch_calls':batches};total_logical+=logical;total_batches+=batches
  score=score_pair(credits['K_TRAIN_CONTIG8'],credits['K_COHORT_CONTIG8'],delta=float(PROTOCOL['inherited_delta']))
  rots.append({'rotation':r,'content_at_position':mapping,'score':score,'credits':credits,'counts':counts})
 fully=all(x['score']['robust_authority'] for x in rots)
 p0=rots[0]['score']['candidate'] if fully else None;c0=rots[0]['content_at_position'][p0] if fully else None
 if fully:
  position_tracking=sum(x['score']['candidate']==p0 for x in rots)/4
  content_tracking=sum(x['content_at_position'][x['score']['candidate']]==c0 for x in rots)/4
 else:position_tracking=None;content_tracking=None
 return {'prompt_hash':base.prompt_hash,'context':base.context,'target_token':target,'fully_resolved':fully,'baseline_top_position':p0,'baseline_top_content_identity':c0,'position_tracking':position_tracking,'content_tracking':content_tracking,'rotations':rots,'logical_intervention_realizations':total_logical,'physical_model_batch_calls':total_batches}


def metrics(rows:list[dict])->dict:
 full=[r for r in rows if r['fully_resolved']];n=len(rows)
 return {'n':n,'fully_resolved_count':len(full),'fully_resolved_fraction':len(full)/max(n,1),'position_tracking':float(statistics.mean(r['position_tracking'] for r in full)) if full else 0.0,'content_tracking':float(statistics.mean(r['content_tracking'] for r in full)) if full else 0.0,'baseline_top_position_counts':{p:sum(r['baseline_top_position']==p for r in full) for p in POSITIONS}}


def classify(strata:dict)->dict:
 content={};position={};coverage={}
 for name,m in strata.items():
  coverage[name]=m['fully_resolved_fraction']>=float(PROTOCOL['min_fully_resolved_fraction'])
  content[name]=coverage[name] and m['content_tracking']>=float(PROTOCOL['content_tracking_min']) and m['content_tracking']-m['position_tracking']>=float(PROTOCOL['content_minus_position_min'])
  position[name]=coverage[name] and m['position_tracking']>=float(PROTOCOL['position_tracking_min']) and m['position_tracking']-m['content_tracking']>=float(PROTOCOL['position_minus_content_min'])
 return {'coverage':coverage,'content_specific':content,'position_locality':position,'content_pass':all(content.values()),'position_pass':all(position.values())}


def run(cohort:str)->dict:
 if cohort not in {'primary','replication'}:raise ValueError(cohort)
 model=load_checkpoint(_checkpoint_path(cohort));before=state_dict_sha256(model);old=_all_previous_prompt_hashes();rows=[];t=time.perf_counter()
 for c in PROTOCOL['contexts']:
  for spec in fresh_base_specs(c,cohort):rows.append(evaluate_base(model,spec,cohort=cohort))
 after=state_dict_sha256(model);strata={'pooled':metrics(rows)}
 for c in PROTOCOL['contexts']:strata[c]=metrics([r for r in rows if r['context']==c])
 checks=classify(strata);overlap=sum(r['prompt_hash'] in old for r in rows);mutation=before!=after
 if checks['content_pass'] and not mutation and overlap==0:verdict='CONTENT_SPECIFIC_CAUSAL_CREDIT_QUALIFIED_NARROWED'
 elif checks['position_pass'] and not mutation and overlap==0:verdict='POSITION_LOCALITY_EXPLANATION_SUPPORTED_NARROWED'
 else:verdict='POSITION_CONTENT_MECHANISM_UNRESOLVED'
 payload={'experiment_id':'CSCA-06C-R1','cohort':cohort.upper(),'verdict':verdict,'metrics':strata,'decision_checks':checks,'prompt_overlap_previous':overlap,'model_state_mutated':mutation,'wall_seconds':time.perf_counter()-t,'logical_intervention_realizations':sum(r['logical_intervention_realizations'] for r in rows),'physical_model_batch_calls':sum(r['physical_model_batch_calls'] for r in rows),'semantic_causality_authorized':False,'student_authorized':False,'replay_authorized':False,'active_control':False}
 _json(ART/f'{cohort}/rows.json',rows);_json(ART/f'{cohort}/result.json',payload);return payload


def main():
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('cohort',choices=['primary','replication']);a=ap.parse_args();print(json.dumps(run(a.cohort),indent=2,sort_keys=True))
if __name__=='__main__':main()
