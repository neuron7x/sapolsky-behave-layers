from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
from typing import Iterable

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np

from cwc.counterfactual.falsifiability import (
    AlternativeComponent,
    CompositeNullEProcess,
    GaussianInterventionalLaw,
    InterventionDesign,
    NuisanceEnvelope,
    latent_aleatoric_equivalence,
    model_class_falsifiability_state,
    optimize_minimax_design,
    separation_rate_per_cost,
)

PROTOCOL = json.loads((Path(__file__).with_name('protocol.json')).read_text())
ART = ROOT / 'artifacts/csca-06a-falsifiability'
RES = ROOT / 'research/results/CSCA-06A-IF'

NUIS = NuisanceEnvelope(**PROTOCOL['nuisance_envelope'])
COSTS = {float(k): float(v) for k, v in PROTOCOL['action_costs'].items()}
PRIMARY_DESIGN = InterventionDesign({float(k): int(v) for k, v in PROTOCOL['confirmatory_block'].items()}, COSTS)


@dataclass(frozen=True, slots=True)
class Family:
    family_id: str
    model_slope: float
    true_slope: float
    intercept: float
    gamma: float
    sigma: float
    topology_label: str
    nuisance_scope_certified: bool = True
    weak_signal: bool = False

    @property
    def total_sd(self) -> float:
        return math.sqrt(self.gamma * self.gamma + self.sigma * self.sigma)


FAMILIES = (
    Family('N0_NULL_CLEAN', 0.0, 0.0, 0.0, 0.0, 1.0, 'CORRECT_TOPOLOGY'),
    Family('N1_NULL_LATENT_CONFOUNDING', 0.0, 0.0, 0.0, 1.2, 0.7, 'CORRECT_TOPOLOGY'),
    Family('N2_NULL_ALEATORIC', 0.0, 0.0, 0.0, 0.0, 2.0, 'CORRECT_TOPOLOGY'),
    Family('N3_NULL_MIXED_NUISANCE', 0.0, 0.0, 0.5, 1.0, 0.8, 'CORRECT_TOPOLOGY'),
    Family('S1_MISSING_TRUE_EDGE', 0.0, 0.8, 0.0, 0.8, 0.7, 'WRONG_TOPOLOGY'),
    Family('S2_MISSING_TRUE_EDGE_NEGATIVE', 0.0, -0.8, 0.0, 0.8, 0.7, 'WRONG_TOPOLOGY'),
    Family('W1_WEAK_EDGE_BUDGET_STRESS', 0.0, 0.15, 0.0, 0.8, 0.7, 'WRONG_TOPOLOGY', weak_signal=True),
    Family('S3_SPURIOUS_CANDIDATE_EDGE', 0.8, 0.0, 0.0, 0.8, 0.7, 'WRONG_TOPOLOGY'),
    Family('O1_OUT_OF_ENVELOPE_NOISE', 0.0, 0.0, 0.0, 0.0, 3.2, 'CORRECT_TOPOLOGY', nuisance_scope_certified=False),
)


def _alternative(model_slope: float) -> list[AlternativeComponent]:
    return [
        AlternativeComponent(model_slope + offset, h, sd)
        for offset in PROTOCOL['alternative_slope_offsets']
        for h in (-0.5, 0.0, 0.5)
        for sd in (0.8, 1.2, 1.8)
    ]


def _seed(base: int, family_idx: int, i: int) -> int:
    return int(base + family_idx * 1000 + i)


def _draw_block(rng: np.random.Generator, fam: Family, design: InterventionDesign) -> list[float]:
    out = []
    for action in design.actions:
        u = float(rng.normal())
        eps = float(rng.normal())
        out.append(fam.true_slope * action + fam.intercept + fam.gamma * u + fam.sigma * eps)
    return out


def _run_one(fam: Family, seed: int, design: InterventionDesign) -> dict:
    law = GaussianInterventionalLaw(fam.true_slope, fam.intercept, fam.total_sd)
    rate = separation_rate_per_cost(law, design, model_slope=fam.model_slope, nuisance=NUIS)
    if design.distinct_actions < 2:
        return {
            'seed': seed,
            'family_id': fam.family_id,
            'rejected': False,
            'blocks': 0,
            'cost': 0.0,
            'log_e': 0.0,
            'separation_rate_per_cost': rate,
            'authority_state': 'UNRESOLVED_INTERVENTIONAL_EQUIVALENCE',
            'nuisance_scope_certified': fam.nuisance_scope_certified,
        }
    rng = np.random.default_rng(seed)
    proc = CompositeNullEProcess(
        model_slope=fam.model_slope,
        nuisance=NUIS,
        alternative=_alternative(fam.model_slope),
        alpha=PROTOCOL['alpha'],
        max_cost=PROTOCOL['max_cost'],
    )
    history = []
    for _ in range(PROTOCOL['max_blocks']):
        if proc.rejected:
            break
        history.append(proc.step(_draw_block(rng, fam, design), design))
    state = model_class_falsifiability_state(
        separation_rate=rate,
        observed_rejection=proc.rejected,
        nuisance_scope_certified=fam.nuisance_scope_certified,
        budget_exhausted=(not proc.rejected and proc.cost >= PROTOCOL['max_cost'] - 1e-12),
    )
    return {
        'seed': seed,
        'family_id': fam.family_id,
        'rejected': proc.rejected,
        'blocks': proc.blocks,
        'cost': proc.cost,
        'log_e': proc.log_e,
        'separation_rate_per_cost': rate,
        'authority_state': state,
        'nuisance_scope_certified': fam.nuisance_scope_certified,
        'history_sha256': hashlib.sha256(json.dumps(history, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
    }


def _metrics(rows: list[dict]) -> dict:
    rejected = [r for r in rows if r['rejected']]
    return {
        'n': len(rows),
        'rejection_count': len(rejected),
        'rejection_rate': len(rejected) / max(len(rows), 1),
        'median_cost_if_rejected': statistics.median([r['cost'] for r in rejected]) if rejected else None,
        'median_blocks_if_rejected': statistics.median([r['blocks'] for r in rejected]) if rejected else None,
        'median_final_log_e': statistics.median(r['log_e'] for r in rows),
        'separation_rate_per_cost': rows[0]['separation_rate_per_cost'] if rows else None,
        'authority_states': {state: sum(r['authority_state'] == state for r in rows) for state in sorted({r['authority_state'] for r in rows})},
    }


def analytic_phase() -> dict:
    alternatives = [
        GaussianInterventionalLaw(slope, h, sd)
        for slope in (-0.8, -0.4, 0.4, 0.8)
        for h, sd in ((0.0, 1.0), (0.4, 1.5), (-0.4, 1.5))
    ]
    best, table = optimize_minimax_design(
        actions=(-1.0, 0.0, 1.0),
        costs={-1.0: 1.0, 0.0: 0.6, 1.0: 1.0},
        alternative_laws=alternatives,
        model_slope=0.0,
        nuisance=NUIS,
        max_samples=6,
    )
    equiv_design = InterventionDesign({1.0: 1}, {1.0: 1.0})
    equiv_rate = separation_rate_per_cost(
        GaussianInterventionalLaw(0.7, 0.0, 1.0), equiv_design, model_slope=0.0, nuisance=NUIS
    )
    variance_pairs = latent_aleatoric_equivalence(1.7, points=17)
    variance_spread = max(g*g+s*s for g,s in variance_pairs) - min(g*g+s*s for g,s in variance_pairs)
    return {
        'best_minimax_design': {str(k): int(v) for k, v in best.counts.items()},
        'best_minimax_cost': best.cost,
        'best_minimax_rate_per_cost': table[0]['min_separation_rate_per_cost'],
        'top_designs': table[:12],
        'single_action_equivalence_rate': equiv_rate,
        'latent_aleatoric_pairs': [{'gamma': g, 'sigma': s, 'total_variance': g*g+s*s} for g,s in variance_pairs],
        'latent_aleatoric_variance_spread': variance_spread,
        'information_statement': 'Evidence is in Y conditional on a chosen intervention; I(M;do(X)) is not a universal falsification threshold. The operational separation object is inf_Q KL(P*_d||Q_d)/Cost(d).',
    }


def run_cohort(name: str, seed_start: int) -> dict:
    family_rows = {}
    all_rows = []
    n = int(PROTOCOL['seeds_per_family'])
    for fi, fam in enumerate(FAMILIES):
        rows = [_run_one(fam, _seed(seed_start, fi, i), PRIMARY_DESIGN) for i in range(n)]
        family_rows[fam.family_id] = {'family': asdict(fam), 'metrics': _metrics(rows)}
        all_rows.extend(rows)
    # E0 support/equivalence control: the execution engine must refuse one-level support.
    e0_fam = Family('E0_SINGLE_ACTION_EQUIVALENCE', 0.0, 0.7, 0.0, 0.0, 1.0, 'INTERVENTIONALLY_EQUIVALENT')
    e0_design = InterventionDesign({1.0: 8}, {1.0: 1.0})
    e0_rows = [_run_one(e0_fam, seed_start + 99000 + i, e0_design) for i in range(n)]
    family_rows[e0_fam.family_id] = {'family': asdict(e0_fam), 'metrics': _metrics(e0_rows)}
    all_rows.extend(e0_rows)
    return {'cohort': name, 'family_results': family_rows, 'rows': all_rows}


def evaluate_gate(cohort: dict) -> tuple[bool, list[str]]:
    f = cohort['family_results']
    errors = []
    null_ids = ['N0_NULL_CLEAN','N1_NULL_LATENT_CONFOUNDING','N2_NULL_ALEATORIC','N3_NULL_MIXED_NUISANCE']
    null_n = sum(f[k]['metrics']['n'] for k in null_ids)
    null_rej = sum(f[k]['metrics']['rejection_count'] for k in null_ids)
    pooled = null_rej / null_n
    if pooled > PROTOCOL['maximum_in_envelope_null_false_rejection_rate']:
        errors.append(f'in-envelope pooled false rejection {pooled:.6f} > 0.01')
    for k in null_ids:
        if f[k]['metrics']['rejection_rate'] > 0.02:
            errors.append(f'{k} false rejection >0.02')
    for k in ['S1_MISSING_TRUE_EDGE','S2_MISSING_TRUE_EDGE_NEGATIVE','S3_SPURIOUS_CANDIDATE_EDGE']:
        if f[k]['metrics']['rejection_rate'] < PROTOCOL['minimum_structural_rejection_rate']:
            errors.append(f'{k} structural rejection below 0.95')
    e0 = f['E0_SINGLE_ACTION_EQUIVALENCE']['metrics']
    if e0['rejection_count'] != PROTOCOL['required_equivalence_false_rejections']:
        errors.append('E0 falsely rejected')
    if abs(float(e0['separation_rate_per_cost'])) > 1e-12:
        errors.append('E0 separation rate not zero')
    o1states = f['O1_OUT_OF_ENVELOPE_NOISE']['metrics']['authority_states']
    if any('GRAPH_COMPONENT_FALSIFIED' in s for s in o1states):
        errors.append('O1 incorrectly attributed out-of-envelope rejection to topology')
    return not errors, errors


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n')


def _sha_manifest(root: Path) -> dict[str, str]:
    out = {}
    for p in sorted(root.rglob('*')):
        if p.is_file() and p.name != 'SHA256SUMS':
            out[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    (root / 'SHA256SUMS').write_text(''.join(f'{sha}  {name}\n' for name, sha in out.items()))
    return out


def main() -> None:
    ART.mkdir(parents=True, exist_ok=True)
    RES.mkdir(parents=True, exist_ok=True)
    analytic = analytic_phase()
    _write(ART / 'analytic_design.json', analytic)

    primary = run_cohort('PRIMARY', int(PROTOCOL['primary_seed_start']))
    replication = run_cohort('REPLICATION', int(PROTOCOL['replication_seed_start']))
    ppass, perr = evaluate_gate(primary)
    rpass, rerr = evaluate_gate(replication)
    _write(ART / 'primary.json', primary)
    _write(ART / 'replication.json', replication)

    verdict = {
        'experiment_id': 'CSCA-06A-IF',
        'verdict': 'INTERVENTIONAL_FALSIFIABILITY_INSTRUMENT_QUALIFIED_NARROWED' if ppass and rpass else 'INTERVENTIONAL_FALSIFIABILITY_INSTRUMENT_NOT_QUALIFIED',
        'scientific_pass': bool(ppass and rpass),
        'primary_pass': ppass,
        'replication_pass': rpass,
        'primary_errors': perr,
        'replication_errors': rerr,
        'graph_truth_authorized': False,
        'shadow_inference_promotion_authorized': False,
        'replay_authorized': False,
        'active_causal_control_authorized': False,
        'falsification_scope': 'DECLARED_INTERVENTIONAL_MODEL_PLUS_NUISANCE_CLASS_ONLY',
        'central_boundary': 'Rejection cannot uniquely distinguish topology error from an omitted nuisance mechanism outside the declared envelope. Latent-confounder variance and aleatoric variance are non-identifiable from scalar interventional Y without additional measurements/assumptions.',
        'information_condition': 'Positive inf_Q KL(P*_d||Q_d)/Cost(d) is the separation condition; if zero, the candidate class is interventionally unfalsifiable under design d. Finite-budget rejection uses the anytime-valid e-process threshold E>=1/alpha.',
        'analytic': analytic,
        'primary_summary': {k:v['metrics'] for k,v in primary['family_results'].items()},
        'replication_summary': {k:v['metrics'] for k,v in replication['family_results'].items()},
    }
    _write(RES / 'verdict.json', verdict)
    _write(ART / 'verdict.json', verdict)
    manifest = _sha_manifest(ART)
    _write(RES / 'artifact_manifest.json', manifest)
    print(json.dumps({'verdict': verdict['verdict'], 'primary_pass': ppass, 'replication_pass': rpass}, indent=2))


if __name__ == '__main__':
    main()
