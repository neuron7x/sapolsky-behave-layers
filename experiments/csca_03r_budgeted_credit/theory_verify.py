from __future__ import annotations

from fractions import Fraction
import itertools
import json
from pathlib import Path
import argparse

PLAYERS=("A","B","C","D")

def f(x:dict[str,int],c:int)->Fraction:
    return Fraction(x['A'])+Fraction(7,10)*x['B']+Fraction(4,5)*c*x['A']*x['B']

def teacher(a:int,b:int,c:int)->dict[str,Fraction]:
    return {'A':Fraction(a)+Fraction(2,5)*c*a*b,'B':Fraction(7,10)*b+Fraction(2,5)*c*a*b,'C':Fraction(0),'D':Fraction(0)}

def path(factual,order,repl,c):
    x=dict(factual);prev=f(x,c);out={}
    for p in order:
        x[p]=repl[p];cur=f(x,c);out[p]=prev-cur;prev=cur
    return out

def mean(xs):return sum(xs,Fraction(0))/len(xs)
def var(xs):
    m=mean(xs);return mean([(x-m)**2 for x in xs])

def verify():
    crn_state=[];anti_state=[];unbiased=True;dummy=True;details=[]
    for c,a,b in itertools.product((-1,1),repeat=3):
        factual={'A':a,'B':b,'C':1,'D':-1};t=teacher(a,b,c);crn={p:[] for p in PLAYERS};anti={p:[] for p in PLAYERS}
        for order in itertools.permutations(PLAYERS):
            for bits in itertools.product((-1,1),repeat=4):
                r=dict(zip(PLAYERS,bits,strict=True));q=path(factual,order,r,c);rc={p:-r[p] for p in PLAYERS};q2=path(factual,order,rc,c)
                for p in PLAYERS:
                    crn[p].append(q[p]);anti[p].append((q[p]+q2[p])/2)
        cm={p:mean(crn[p]) for p in PLAYERS};am={p:mean(anti[p]) for p in PLAYERS}
        unbiased &= cm==t and am==t
        dummy &= all(all(x==0 for x in crn[p]) and all(x==0 for x in anti[p]) for p in ('C','D'))
        cv={p:var(crn[p]) for p in PLAYERS};av={p:var(anti[p]) for p in PLAYERS}
        cmse=sum(cv.values(),Fraction(0))/4;amse=sum(av.values(),Fraction(0))/4
        crn_state.append(cmse);anti_state.append(amse)
        details.append({'context':c,'A':a,'B':b,'crn_one_path_vector_mse':float(cmse),'antithetic_one_pair_vector_mse':float(amse)})
    avgc=mean(crn_state);avga=mean(anti_state);ratio=2*avga/avgc
    return {'status':'POST_CONFIRMATORY_ANALYTIC_MECHANISM_CHECK_NO_CLAIM_UPGRADE','enumerated_states':8,'per_state_microstates':384,'total_microstates':3072,'crn_unbiased_exact':bool(unbiased),'structural_null_C_D_exact_per_draw':bool(dummy),'mean_crn_one_path_vector_mse_fraction':f'{avgc.numerator}/{avgc.denominator}','mean_antithetic_one_pair_vector_mse_fraction':f'{avga.numerator}/{avga.denominator}','matched_budget_antithetic_over_crn_mse_ratio_fraction':f'{ratio.numerator}/{ratio.denominator}','matched_budget_antithetic_over_crn_mse_ratio':float(ratio),'details':details}

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=verify();a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n');print(json.dumps(d,indent=2,sort_keys=True))
if __name__=='__main__':main()
