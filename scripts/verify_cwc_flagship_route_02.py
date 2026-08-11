from __future__ import annotations

import argparse, copy, hashlib, json
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from experiments.cwc_flagship_route_02 import core

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/cwc-flagship-route-02'


def _select(scores: np.ndarray, n: int, ids: list[str], largest: bool=True) -> np.ndarray:
    order = sorted(range(len(scores)), key=lambda i: ((-scores[i] if largest else scores[i]), ids[i]))
    m=np.zeros(len(scores),dtype=bool)
    for i in order[:n]: m[i]=True
    return m


def _rand(ids: list[str], n: int) -> np.ndarray:
    s=[int(hashlib.sha256((core.EXPERIMENT_ID+'|RANDOM|'+x).encode()).hexdigest(),16) for x in ids]
    order=sorted(range(len(ids)), key=lambda i:(s[i],ids[i]))
    m=np.zeros(len(ids),dtype=bool)
    for i in order[:n]: m[i]=True
    return m


def _ridge_predict(raw: dict, x: np.ndarray) -> np.ndarray:
    mean=np.asarray(raw['mean'],dtype=float); scale=np.asarray(raw['scale'],dtype=float); coef=np.asarray(raw['coef'],dtype=float)
    return ((x-mean)/scale)@coef+float(raw['intercept'])


def recompute_cell(seed:int, cohort:str, family:str) -> dict:
    cp=OUT/'checkpoints'/f'seed{seed}.pt'; pp=OUT/'policies'/f'seed{seed}.json'
    payload=torch.load(cp,map_location='cpu',weights_only=False)
    if payload.get('experiment')!=core.EXPERIMENT_ID or int(payload.get('seed',-1))!=seed: raise RuntimeError('checkpoint identity')
    model=core.DualExitLM(); model.load_state_dict(payload['state_dict']); model.eval()
    pol=json.loads(pp.read_text())
    if int(pol.get('seed',-1))!=seed: raise RuntimeError('policy identity')
    cases=core.window_cases(family,cohort)
    x=torch.tensor([c.x for c in cases],dtype=torch.long); y=torch.tensor([c.y for c in cases],dtype=torch.long)
    with torch.no_grad():
        h1=model.first_hidden(x); l1=model.logits(h1); h2=model.second_hidden(h1); l2=model.logits(h2)
        ce1=F.cross_entropy(l1.transpose(1,2),y,reduction='none').mean(dim=1).numpy()
        ce2=F.cross_entropy(l2.transpose(1,2),y,reduction='none').mean(dim=1).numpy()
        z=h1.mean(dim=1).float().numpy()
    famcol=np.zeros((len(cases),1)) if family=='PROSE' else np.ones((len(cases),1))
    feat=np.concatenate([z,famcol],axis=1)
    gain=ce1-ce2; ids=[c.case_id for c in cases]
    pg=_ridge_predict(pol['gain_model'],feat); pd=_ridge_predict(pol['difficulty_model'],feat)
    f=core.flop_contract(); slope=float(pol['frontier'][family]['gain_per_flop'])
    cand=pg > slope*f.block; n=int(cand.sum()); q=n/len(cases)
    comp=float(f.fixed_depth1+f.route+q*f.block); outside=comp>f.fixed_depth2+1e-9
    hn=np.linalg.norm(feat[:,:core.D_MODEL],axis=1)
    masks={'DECISION_RELEVANT':cand,'RANDOM_MATCHED':_rand(ids,n),'HIDDEN_NORM_MATCHED':_select(hn,n,ids,True),
           'DIFFICULTY_MATCHED':_select(pd,n,ids,True),'ORACLE_MATCHED':_select(gain,n,ids,True)}
    losses={k:float(np.mean(np.where(m,ce2,ce1))) for k,m in masks.items()}
    L1=float(np.mean(ce1)); L2=float(np.mean(ce2)); frontier=None
    if not outside:
        if L2>=L1: frontier=L1
        else:
            qq=min(1.0,max(0.0,(comp-f.fixed_depth1)/(f.fixed_depth2-f.fixed_depth1)))
            frontier=float(L1+qq*(L2-L1))
    eps=1e-12
    ep={'within_fixed_frontier':not outside,
        'beats_fixed_frontier':frontier is not None and losses['DECISION_RELEVANT']<frontier-eps,
        'beats_random_matched':losses['DECISION_RELEVANT']<losses['RANDOM_MATCHED']-eps,
        'no_worse_hidden_norm':losses['DECISION_RELEVANT']<=losses['HIDDEN_NORM_MATCHED']+eps,
        'beats_difficulty_matched':losses['DECISION_RELEVANT']<losses['DIFFICULTY_MATCHED']-eps,
        'oracle_sanity':losses['ORACLE_MATCHED']<=losses['DECISION_RELEVANT']+eps,
        'matched_counts':all(int(m.sum())==n for m in masks.values()),'anti_reuse':core.assert_no_r1_overlap()['overlaps']==0}
    return {'continue_count':n,'continue_rate':q,'logical_flops_per_window':comp,'fixed_frontier_loss':frontier,
            'candidate_advantage_vs_fixed_frontier':None if frontier is None else frontier-losses['DECISION_RELEVANT'],
            'loss1':L1,'loss2':L2,'losses':losses,'endpoints':ep,'passed':all(ep.values())}


def verify(doc:dict|None=None) -> dict:
    d=json.loads((OUT/'verdict.json').read_text()) if doc is None else doc
    mism=[]; counts={}
    for cohort in ('PRIMARY','REPLICATION'):
        passed=0
        for cell in d['cells'][cohort]:
            seed=int(cell['seed']); fam=cell['family']; r=recompute_cell(seed,cohort,fam)
            if bool(cell['passed'])!=r['passed']: mism.append(f'{cohort}/{fam}/{seed}:passed')
            for k in ('continue_count','continue_rate','logical_flops_per_window','candidate_advantage_vs_fixed_frontier','loss1','loss2'):
                a,b=cell[k],r[k]
                if a is None or b is None:
                    if a!=b: mism.append(f'{cohort}/{fam}/{seed}:{k}')
                elif abs(float(a)-float(b))>2e-6: mism.append(f'{cohort}/{fam}/{seed}:{k}')
            for k,v in r['endpoints'].items():
                if bool(cell['endpoints'][k])!=bool(v): mism.append(f'{cohort}/{fam}/{seed}:endpoint:{k}')
            passed+=int(r['passed'])
        counts[cohort]=passed
    expected='CWC_FLAGSHIP_ROUTE_02_NOT_SUPPORTED' if counts['PRIMARY']<6 else ('CWC_FLAGSHIP_ROUTE_02_NOT_SUPPORTED_REPLICATION' if counts['REPLICATION']<6 else 'CWC_FLAGSHIP_ROUTE_02_SUPPORTED_NARROW')
    if d.get('verdict')!=expected: mism.append('verdict')
    return {'passed':not mism,'mismatches':mism,'primary_pass':counts['PRIMARY'],'replication_pass':counts['REPLICATION'],'verdict':expected}


def self_test() -> dict:
    base=json.loads((OUT/'verdict.json').read_text()); killed=[]
    muts=[]
    b=copy.deepcopy(base); b['verdict']='CWC_FLAGSHIP_ROUTE_02_SUPPORTED_NARROW'; muts.append(('verdict_flip',b))
    b=copy.deepcopy(base); b['cells']['PRIMARY'][0]['passed']=not b['cells']['PRIMARY'][0]['passed']; muts.append(('pass_flip',b))
    b=copy.deepcopy(base); b['cells']['PRIMARY'][0]['continue_count']+=1; muts.append(('count_drift',b))
    b=copy.deepcopy(base); b['cells']['PRIMARY'][0]['loss1']=0.0; muts.append(('loss_drift',b))
    b=copy.deepcopy(base); b['cells']['PRIMARY'][0]['endpoints']['beats_fixed_frontier']=False; muts.append(('endpoint_drift',b))
    for name,doc in muts:
        if not verify(doc)['passed']: killed.append(name)
    return {'passed':len(killed)==len(muts),'killed':len(killed),'expected':len(muts),'attacks':killed}


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--self-test',action='store_true'); a=ap.parse_args()
    print(json.dumps(self_test() if a.self_test else verify(),indent=2,sort_keys=True))

if __name__=='__main__': main()
