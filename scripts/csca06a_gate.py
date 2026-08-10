#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'artifacts/csca-06a-falsifiability'
VERDICT = ROOT / 'research/results/CSCA-06A-IF/verdict.json'


def _load(path: Path):
    return json.loads(path.read_text())


def main() -> int:
    errors = []
    required = [ART/'analytic_design.json', ART/'primary.json', ART/'replication.json', ART/'verdict.json', ART/'SHA256SUMS', VERDICT]
    for p in required:
        if not p.is_file(): errors.append(f'missing {p.relative_to(ROOT)}')
    if errors:
        print('CSCA06A-GATE FAIL')
        for e in errors: print(' -', e)
        return 1
    # checksum every artifact payload before trusting semantics
    for line in (ART/'SHA256SUMS').read_text().splitlines():
        sha, name = line.split('  ',1)
        p = ART/name
        if hashlib.sha256(p.read_bytes()).hexdigest() != sha:
            errors.append(f'checksum mismatch {name}')
    verdict = _load(VERDICT)
    if verdict.get('verdict') != 'INTERVENTIONAL_FALSIFIABILITY_INSTRUMENT_NOT_QUALIFIED': errors.append('negative parent verdict drifted')
    if verdict.get('scientific_pass') is not False: errors.append('negative parent scientific_pass must remain false')
    if verdict.get('primary_pass') is not False: errors.append('negative parent PRIMARY must remain failed')
    if verdict.get('replication_pass') is not True: errors.append('negative parent replication record drifted')
    for key in ('graph_truth_authorized','shadow_inference_promotion_authorized','replay_authorized','active_causal_control_authorized'):
        if verdict.get(key) is not False: errors.append(f'illegal promotion {key}')
    analytic = verdict['analytic']
    if abs(float(analytic['single_action_equivalence_rate'])) > 1e-12: errors.append('equivalence control no longer zero-KL')
    if float(analytic['latent_aleatoric_variance_spread']) > 1e-12: errors.append('latent/aleatoric nonidentifiability construction broken')
    for cohort in ('primary_summary','replication_summary'):
        c=verdict[cohort]
        for k in ('N0_NULL_CLEAN','N1_NULL_LATENT_CONFOUNDING','N2_NULL_ALEATORIC','N3_NULL_MIXED_NUISANCE'):
            if c[k]['rejection_rate'] > 0.02: errors.append(f'{cohort}/{k} excessive false rejection')
        if cohort == 'replication_summary':
            for k in ('S1_MISSING_TRUE_EDGE','S2_MISSING_TRUE_EDGE_NEGATIVE','S3_SPURIOUS_CANDIDATE_EDGE'):
                if c[k]['rejection_rate'] < 0.95: errors.append(f'{cohort}/{k} replication record drifted')
        else:
            # This exact preregistered miss is the scientific reason the parent is negative.
            if abs(float(c['S2_MISSING_TRUE_EDGE_NEGATIVE']['rejection_rate']) - 0.9375) > 1e-12:
                errors.append('PRIMARY S2 negative boundary drifted')
            if c['S2_MISSING_TRUE_EDGE_NEGATIVE']['rejection_rate'] >= 0.95:
                errors.append('PRIMARY S2 no longer records the frozen qualification failure')
        if c['E0_SINGLE_ACTION_EQUIVALENCE']['rejection_count'] != 0: errors.append(f'{cohort}/E0 false graph rejection')
        if any('GRAPH_COMPONENT_FALSIFIED' in s for s in c['O1_OUT_OF_ENVELOPE_NOISE']['authority_states']):
            errors.append(f'{cohort}/O1 topology over-attribution')
    if errors:
        print(f'CSCA06A-GATE FAIL ({len(errors)})')
        for e in errors: print(' -', e)
        return 1
    print('CSCA06A-GATE PASS: parent negative is sealed (PRIMARY S2=0.9375<0.95); no retrospective rescue or graph-truth promotion.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
