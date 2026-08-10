#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, math, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'artifacts/csca-06a-information-converse'

def main()->int:
    errors=[]
    cp=ART/'certificate.json'; sp=ART/'SHA256SUMS'; src=ROOT/'research/results/CSCA-06A-R1/verdict.json'
    for p in (cp,sp,src):
        if not p.is_file(): errors.append('missing '+str(p.relative_to(ROOT)))
    if errors:
        print('CSCA06-INFO-GATE FAIL',*errors,sep='\n - '); return 1
    sha,name=sp.read_text().strip().split('  ',1)
    if name!='certificate.json' or hashlib.sha256(cp.read_bytes()).hexdigest()!=sha: errors.append('certificate checksum mismatch')
    d=json.loads(cp.read_text())
    if hashlib.sha256(src.read_bytes()).hexdigest()!=d.get('source_verdict_sha256'): errors.append('source verdict binding mismatch')
    f=d['families']
    req=4.176898950135489
    if abs(f['S1_MISSING_TRUE_EDGE']['required_information_nats']-req)>1e-12: errors.append('required information drift')
    if f['E0_SINGLE_ACTION_EQUIVALENCE']['state']!='INTERVENTIONALLY_UNFALSIFIABLE_AT_THIS_DESIGN': errors.append('E0 equivalence boundary broken')
    if f['E0_SINGLE_ACTION_EQUIVALENCE']['necessary_cost_lower_bound'] is not None or f['E0_SINGLE_ACTION_EQUIVALENCE'].get('necessary_cost_is_infinite') is not True: errors.append('E0 cost must be represented as infinite/not finite')
    if f['W1_WEAK_EDGE_BUDGET_STRESS']['state']!='BUDGET_BELOW_NECESSARY_INFORMATION_BOUND': errors.append('W1 information veto broken')
    if not f['W1_WEAK_EDGE_BUDGET_STRESS']['necessary_cost_lower_bound']>256: errors.append('W1 bound no longer exceeds budget')
    for k in ('S1_MISSING_TRUE_EDGE','S2_MISSING_TRUE_EDGE_NEGATIVE','S3_SPURIOUS_CANDIDATE_EDGE'):
        if f[k]['state']!='BUDGET_NOT_RULED_OUT_BY_INFORMATION_CONVERSE': errors.append(k+' strong-edge feasibility drift')
    if any(d['authority'].values()): errors.append('illegal authority promotion')
    if errors:
        print('CSCA06-INFO-GATE FAIL',*errors,sep='\n - '); return 1
    print('CSCA06-INFO-GATE PASS: necessary information/cost converse bound; W1 vetoed, E0 unfalsifiable, no sufficiency or graph-truth claim.')
    return 0
if __name__=='__main__': sys.exit(main())
