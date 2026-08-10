#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'research/results/CSCA-04-SA'


def sha(path: Path) -> str:
    h=hashlib.sha256(); h.update(path.read_bytes()); return h.hexdigest()


def main() -> int:
    required=['CALIBRATION.json','FROZEN_POLICY.json','PRIMARY.json','INDEPENDENT_REPLICATION.json','verdict.json']
    errors=[]
    for name in required:
        if not (BASE/name).exists(): errors.append(f'missing {name}')
    if errors:
        print('CSCA04-GATE FAIL:',*errors,sep='\n - '); return 1
    cal=json.loads((BASE/'CALIBRATION.json').read_text())
    policy=json.loads((BASE/'FROZEN_POLICY.json').read_text())
    primary=json.loads((BASE/'PRIMARY.json').read_text())['summary']
    repl=json.loads((BASE/'INDEPENDENT_REPLICATION.json').read_text())['summary']
    verdict=json.loads((BASE/'verdict.json').read_text())
    if policy['max_cell_idr_threshold'] != cal['primary_max_cell_idr_threshold']:
        errors.append('policy IDR threshold does not match frozen calibration')
    if policy['context_z_threshold'] != cal['primary_context_z_threshold']:
        errors.append('policy context threshold does not match frozen calibration')
    for label,s in [('PRIMARY',primary),('REPLICATION',repl)]:
        if not s['qualification_pass']: errors.append(f'{label} qualification false')
        if s['sensitivity_structural_misspecification'] < 0.95: errors.append(f'{label} sensitivity below gate')
        if s['specificity_known_adequate'] < 0.95: errors.append(f'{label} specificity below gate')
        if s['m6_global_authority'] != 0: errors.append(f'{label} zero-cause false authority')
        if s['m9_global_direction_accept'] != 0: errors.append(f'{label} context sign-flip global authority')
        if s['m10_accepted'] != 0: errors.append(f'{label} collinear-identifiability false acceptance')
    if verdict.get('verdict') != 'STRUCTURAL_ADEQUACY_SYNTHETIC_QUALIFIED': errors.append('unexpected verdict')
    if verdict.get('shadow_inference_qualified') is not False: errors.append('shadow inference illegally promoted')
    for rel,expected in verdict.get('artifact_sha256',{}).items():
        p=ROOT/rel
        if not p.exists() or sha(p)!=expected: errors.append(f'artifact hash mismatch: {rel}')
    if errors:
        print(f'CSCA04-GATE FAIL ({len(errors)})')
        for e in errors: print(' -',e)
        return 1
    print('CSCA04-GATE PASS: frozen thresholds, replicated structural qualification, no shadow promotion.')
    return 0

if __name__=='__main__': sys.exit(main())
