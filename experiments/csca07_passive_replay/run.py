from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cwc.replay.passive_identifiability import (
    AR1Law,
    AR1MixtureEProcess,
    ar1_relative_entropy_rate,
    fiber_ambiguity_counterexample,
    hidden_autocatalytic_fixed_point,
    passive_information_certificate,
    replay_authority_state,
    simulate_ar1,
    spectral_topology_counterexample,
)

OUT = ROOT / 'artifacts/csca-07-passive-replay'
RESULT_DIR = ROOT / 'research/results/CSCA-07-PR'
ALPHA = 0.01
TARGET_POWER = 0.95
TRANSITIONS = 256
ALTERNATIVE_COEFFICIENTS = (-0.75, -0.4, 0.0, 0.25, 0.5, 0.68, 0.75, 0.9)
SD = 0.5
FAMILIES = {
    'N0_TRUE_OBSERVED_LAW': (0.75, 0.75),
    'S1_WRONG_DYNAMICS': (0.75, 0.25),
    'S2_WRONG_SIGN': (0.75, -0.40),
    'W1_WEAK_MISSPECIFICATION': (0.75, 0.68),
}
COHORTS = {'PRIMARY': 81000, 'REPLICATION': 91000}
SEEDS_PER_FAMILY = 128


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _finite_or_none(x: float):
    return x if math.isfinite(x) else None


def run_family(true_a: float, candidate_a: float, seed_base: int):
    true = AR1Law(true_a, SD)
    candidate = AR1Law(candidate_a, SD)
    alternatives = [AR1Law(a, SD) for a in ALTERNATIVE_COEFFICIENTS]
    rows = []
    for seed in range(seed_base, seed_base + SEEDS_PER_FAMILY):
        trace = simulate_ar1(true, transitions=TRANSITIONS, seed=seed)
        e = AR1MixtureEProcess(candidate=candidate, alternatives=alternatives, alpha=ALPHA)
        out = e.run(trace)
        rows.append({'seed': seed, **out})
    rate = sum(bool(r['rejected']) for r in rows) / len(rows)
    reject_times = [int(r['reject_transition']) for r in rows if r['reject_transition'] is not None]
    info_rate = ar1_relative_entropy_rate(true, candidate)
    cert = passive_information_certificate(
        alpha=ALPHA,
        target_power=TARGET_POWER,
        information_rate_nats_per_transition=info_rate,
        available_transitions=TRANSITIONS,
    )
    cert_row = asdict(cert)
    cert_row['necessary_transitions'] = _finite_or_none(float(cert.necessary_transitions))
    cert_row['necessary_transitions_is_infinite'] = not math.isfinite(cert.necessary_transitions)
    return {
        'true_coefficient': true_a,
        'candidate_coefficient': candidate_a,
        'rejection_count': sum(bool(r['rejected']) for r in rows),
        'rejection_rate': rate,
        'median_reject_transition': statistics.median(reject_times) if reject_times else None,
        'mean_final_log_e': statistics.fmean(float(r['log_e']) for r in rows),
        'information_rate_nats_per_transition': info_rate,
        'information_certificate': cert_row,
        'rows': rows,
    }


def main() -> int:
    prereg = ROOT / 'experiments/csca07_passive_replay/PREREGISTRATION.md'
    if not prereg.is_file():
        raise RuntimeError('missing preregistration')
    OUT.mkdir(parents=True, exist_ok=True)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    cohorts = {}
    for cohort, base in COHORTS.items():
        c = {}
        for idx, (name, (true_a, cand_a)) in enumerate(FAMILIES.items()):
            c[name] = run_family(true_a, cand_a, base + idx * 1000)
        cohorts[cohort] = c

    spectral = asdict(spectral_topology_counterexample(seed=7007, steps=512))
    hidden = asdict(hidden_autocatalytic_fixed_point())
    fiber = asdict(fiber_ambiguity_counterexample())

    checks = {
        'primary_null_fpr': cohorts['PRIMARY']['N0_TRUE_OBSERVED_LAW']['rejection_rate'] <= 0.02,
        'replication_null_fpr': cohorts['REPLICATION']['N0_TRUE_OBSERVED_LAW']['rejection_rate'] <= 0.02,
        'primary_s1_power': cohorts['PRIMARY']['S1_WRONG_DYNAMICS']['rejection_rate'] >= 0.95,
        'replication_s1_power': cohorts['REPLICATION']['S1_WRONG_DYNAMICS']['rejection_rate'] >= 0.95,
        'primary_s2_power': cohorts['PRIMARY']['S2_WRONG_SIGN']['rejection_rate'] >= 0.95,
        'replication_s2_power': cohorts['REPLICATION']['S2_WRONG_SIGN']['rejection_rate'] >= 0.95,
        'weak_edge_information_veto_primary': cohorts['PRIMARY']['W1_WEAK_MISSPECIFICATION']['information_certificate']['state'] == 'BUDGET_BELOW_NECESSARY_INFORMATION_BOUND',
        'weak_edge_information_veto_replication': cohorts['REPLICATION']['W1_WEAK_MISSPECIFICATION']['information_certificate']['state'] == 'BUDGET_BELOW_NECESSARY_INFORMATION_BOUND',
        'same_observation_path': spectral['max_observation_path_error'] < 1e-12,
        'same_jacobian_spectrum': spectral['spectral_distance'] < 1e-12,
        'different_latent_topology': spectral['adjacency_a'] != spectral['adjacency_b'],
        'hidden_fixed_point_stable': 0.0 < hidden['spectral_radius'] < 1.0,
        'hidden_fixed_point_context_invariant': hidden['context_derivative'] == 0.0,
        'hidden_fixed_point_observational_information_zero': hidden['observational_information_about_hidden_state'] == 0.0,
        'zero_within_model_fiber_entropy': fiber['per_model_fiber_entropy_bits'] == 0.0,
        'model_trace_mutual_information_zero': fiber['mutual_information_model_trace_bits'] == 0.0,
        'cross_model_fiber_ambiguity_positive': fiber['mixture_fiber_entropy_bits'] > 0.0,
    }
    scientific_pass = all(checks.values())
    verdict_name = 'PASSIVE_REPLAY_IDENTIFIABILITY_BOUNDARY_QUALIFIED' if scientific_pass else 'PASSIVE_REPLAY_IDENTIFIABILITY_BOUNDARY_NOT_QUALIFIED'

    compact_cohorts = {}
    for cohort, fams in cohorts.items():
        compact_cohorts[cohort] = {}
        for name, row in fams.items():
            compact_cohorts[cohort][name] = {k: v for k, v in row.items() if k != 'rows'}

    payload = {
        'experiment_id': 'CSCA-07-PR',
        'verdict': verdict_name,
        'scientific_pass': scientific_pass,
        'authority': 'PASSIVE_PREDICTIVE_FALSIFICATION_ONLY',
        'alpha': ALPHA,
        'target_power': TARGET_POWER,
        'transitions_per_trace': TRANSITIONS,
        'seeds_per_family_per_cohort': SEEDS_PER_FAMILY,
        'alternative_coefficients': list(ALTERNATIVE_COEFFICIENTS),
        'preregistration_sha256': sha256(prereg),
        'checks': checks,
        'cohorts': compact_cohorts,
        'spectral_topology_counterexample': spectral,
        'hidden_autocatalytic_counterexample': hidden,
        'fiber_entropy_counterexample': fiber,
        'central_theorem': {
            'statement': 'If candidate latent models induce the same probability law on D_fact, then I(M;D_fact)=0 and no passive test can distinguish their causal semantics. Positive Jacobian stability, invariant replay fixed points, or zero within-model fiber entropy do not override this observational-equivalence veto.',
            'observational_equivalence_information_rate': 0.0,
            'necessary_cost_when_rate_zero': 'INFINITE',
        },
        'runtime_policy': {
            'predictive_rejection': replay_authority_state(passive_rejected=True, causal_assumptions_identified=False),
            'nonrejection_without_identifying_assumptions': replay_authority_state(passive_rejected=False, causal_assumptions_identified=False),
        },
        'promotion': {
            'true_causal_abstraction': False,
            'semantic_causality': False,
            'shadow_causal_authority': False,
            'replay_control': False,
            'active_control': False,
        },
    }

    # Save detailed cohort files separately so the verdict remains reviewable.
    for cohort, fams in cohorts.items():
        p = OUT / f'{cohort.lower()}_traces.json'
        p.write_text(json.dumps(fams, indent=2, sort_keys=True) + '\n')
    verdict_path = OUT / 'verdict.json'
    verdict_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n')
    research_verdict = RESULT_DIR / 'verdict.json'
    research_verdict.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n')

    files = [OUT/'primary_traces.json', OUT/'replication_traces.json', verdict_path]
    (OUT/'SHA256SUMS').write_text(''.join(f'{sha256(p)}  {p.name}\n' for p in files))
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if scientific_pass else 2


if __name__ == '__main__':
    raise SystemExit(main())
