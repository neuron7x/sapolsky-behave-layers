#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'artifacts/csca-07-passive-replay'
VERDICT = ROOT / 'research/results/CSCA-07-PR/verdict.json'


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _validate(v: dict) -> list[str]:
    e: list[str] = []
    if v.get('verdict') != 'PASSIVE_REPLAY_IDENTIFIABILITY_BOUNDARY_QUALIFIED':
        e.append('verdict drift')
    if v.get('scientific_pass') is not True:
        e.append('scientific_pass drift')
    if v.get('authority') != 'PASSIVE_PREDICTIVE_FALSIFICATION_ONLY':
        e.append('authority drift')
    for key, val in v.get('promotion', {}).items():
        if val is not False:
            e.append('illegal promotion '+key)
    for cohort in ('PRIMARY','REPLICATION'):
        c=v['cohorts'][cohort]
        if c['N0_TRUE_OBSERVED_LAW']['rejection_rate'] > .02:
            e.append(cohort+' null FPR')
        if c['S1_WRONG_DYNAMICS']['rejection_rate'] < .95:
            e.append(cohort+' S1 power')
        if c['S2_WRONG_SIGN']['rejection_rate'] < .95:
            e.append(cohort+' S2 power')
        w=c['W1_WEAK_MISSPECIFICATION']['information_certificate']
        if w['state'] != 'BUDGET_BELOW_NECESSARY_INFORMATION_BOUND':
            e.append(cohort+' W1 information veto')
        if not float(w['necessary_transitions']) > 256:
            e.append(cohort+' W1 necessary cost')
    s=v['spectral_topology_counterexample']
    if not float(s['max_observation_path_error']) < 1e-12:
        e.append('spectral pair no longer observationally equivalent')
    if not float(s['spectral_distance']) < 1e-12:
        e.append('spectral equality broken')
    if s['adjacency_a'] == s['adjacency_b']:
        e.append('latent topology counterexample erased')
    h=v['hidden_autocatalytic_counterexample']
    if not (0 < float(h['spectral_radius']) < 1):
        e.append('hidden fixed point not stable')
    if float(h['context_derivative']) != 0 or float(h['observational_information_about_hidden_state']) != 0:
        e.append('hidden-attractor invisibility boundary broken')
    f=v['fiber_entropy_counterexample']
    if float(f['per_model_fiber_entropy_bits']) != 0:
        e.append('per-model zero fiber entropy counterexample broken')
    if float(f['mutual_information_model_trace_bits']) != 0:
        e.append('observational equivalence MI must remain zero')
    if float(f['mixture_fiber_entropy_bits']) <= 0:
        e.append('cross-model fiber ambiguity erased')
    if v['runtime_policy']['nonrejection_without_identifying_assumptions'] != 'PASSIVE_EQUIVALENCE_UNRESOLVED_CAUSAL_AUTHORITY_BLOCKED':
        e.append('nonrejection promoted to causal authority')
    return e


def main() -> int:
    errors: list[str] = []
    for p in (ART/'primary_traces.json', ART/'replication_traces.json', ART/'verdict.json', ART/'SHA256SUMS', VERDICT):
        if not p.is_file():
            errors.append('missing '+str(p.relative_to(ROOT)))
    if errors:
        print('CSCA07-GATE FAIL', *errors, sep='\n - ')
        return 1
    for line in (ART/'SHA256SUMS').read_text().splitlines():
        sha,name=line.split('  ',1)
        p=ART/name
        if not p.is_file() or _sha(p)!=sha:
            errors.append('checksum '+name)
    if _sha(ART/'verdict.json') != _sha(VERDICT):
        errors.append('artifact/research verdict mismatch')
    v=json.loads(VERDICT.read_text())
    errors.extend(_validate(v))
    if '--self-test' in sys.argv:
        mutants=[]
        m=json.loads(json.dumps(v)); m['promotion']['replay_control']=True; mutants.append(m)
        m=json.loads(json.dumps(v)); m['spectral_topology_counterexample']['spectral_distance']=.1; mutants.append(m)
        m=json.loads(json.dumps(v)); m['fiber_entropy_counterexample']['mutual_information_model_trace_bits']=.2; mutants.append(m)
        m=json.loads(json.dumps(v)); m['runtime_policy']['nonrejection_without_identifying_assumptions']='TRUE_CAUSAL_ABSTRACTION'; mutants.append(m)
        killed=sum(bool(_validate(m)) for m in mutants)
        if killed != len(mutants):
            errors.append(f'self-test killed {killed}/{len(mutants)}')
        else:
            print(f'CSCA07-GATE SELF-TEST: {killed}/{len(mutants)} semantic authority mutations killed')
    if errors:
        print('CSCA07-GATE FAIL', *errors, sep='\n - ')
        return 1
    print('CSCA07-GATE PASS: passive predictive falsification qualified; observational equivalence, spectral/fiber insufficiency, and no-causal-promotion boundary sealed.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
