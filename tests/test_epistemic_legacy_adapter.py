from __future__ import annotations

import hashlib

import numpy as np

from cwc.causal.regime_identifiability import evaluate_regime_iv
from cwc.epistemics.countermodel_search import search_countermodels
from cwc.epistemics.lattice import EpistemicMachine, EpistemicState, EvidenceKind, EvidenceRef, EvidenceSource
from cwc.epistemics.legacy_adapter import adapt_countermodel_decision, adapt_regime_iv_decision


def _ev(label: str, kind: EvidenceKind, source: EvidenceSource) -> EvidenceRef:
    return EvidenceRef(
        ref=f"mem://{label}",
        sha256=hashlib.sha256(label.encode()).hexdigest(),
        kind=kind,
        source=source,
        context_scope=("SYNTH",),
        provenance="adapter-test",
    )


def _sim(seed: int, *, confound_r: float = 0.0):
    rng = np.random.default_rng(seed)
    n = 4096
    u = rng.normal(size=n)
    e1 = rng.normal(size=n)
    e2 = rng.normal(size=n)
    r1 = np.where(e1 + confound_r * u >= 0, 1.0, -1.0)
    r2 = np.where(e2 + 0.7 * confound_r * u >= 0, 1.0, -1.0)
    r = np.column_stack((r1, r2))
    x = r @ np.array([0.9, 0.5]) + 0.8 * u + rng.normal(scale=0.6, size=n)
    y = 0.8 * x + u + rng.normal(scale=0.8, size=n)
    w = u + rng.normal(scale=0.5, size=n)
    return r, x, y, w


def _adapt(machine: EpistemicMachine, decision, claim_id: str):
    return adapt_regime_iv_decision(
        machine,
        decision,
        claim_id=claim_id,
        factual_evidence=[_ev(claim_id+"-f", EvidenceKind.FACTUAL_OBSERVATION, EvidenceSource.FACTUAL_CHANNEL)],
        predictive_evidence=[_ev(claim_id+"-p", EvidenceKind.PREDICTIVE_VALIDATION, EvidenceSource.HELD_OUT_PREDICTION)],
        assumption_evidence=[_ev(claim_id+"-a", EvidenceKind.IDENTIFYING_ASSUMPTION, EvidenceSource.ASSUMPTION_CONTRACT)],
        terminal_evidence=[_ev(claim_id+"-t", EvidenceKind.IDENTIFYING_ASSUMPTION, EvidenceSource.ASSUMPTION_CONTRACT)],
        context_scope=("SYNTH",),
    )


def test_assumption_violation_maps_to_unidentified_not_causal():
    r, x, y, w = _sim(123, confound_r=2.0)
    decision = evaluate_regime_iv(regimes=r, treatment=x, outcome=y, negative_control=w, alpha=0.01)
    assert decision.state == "IDENTIFYING_ASSUMPTION_VIOLATED"
    out = _adapt(EpistemicMachine(), decision, "C-VIOL")
    assert out.record.state is EpistemicState.UNIDENTIFIED
    assert out.record.unconditional_causal_authority is False


def test_surviving_countermodel_degrades_assumption_candidate_to_unidentified():
    r, x, y, w = _sim(321)
    decision = evaluate_regime_iv(regimes=r, treatment=x, outcome=y, negative_control=w, alpha=0.01)
    assert decision.state == "CAUSAL_CANDIDATE_UNDER_ASSUMPTIONS"
    machine = EpistemicMachine()
    upstream = _adapt(machine, decision, "C-CM").record
    assert upstream.state is EpistemicState.ASSUMPTION_CONDITIONAL
    counter = search_countermodels(
        regimes=r,
        treatment=x,
        outcome=y,
        reference_beta=float(decision.beta_hat),
        beta_grid=(-1.0, -0.5, 0.0, 0.5, 1.3, 1.8, 2.3),
        min_causal_shift=0.4,
        candidate_state=decision.state,
        bounds=None,
    )
    assert counter.state == "OBSERVATIONALLY_EQUIVALENT_COUNTERMODEL_SURVIVES"
    out = adapt_countermodel_decision(
        machine,
        upstream,
        counter,
        countermodel_evidence=[_ev("countermodel", EvidenceKind.COUNTERMODEL, EvidenceSource.COUNTERMODEL_SEARCH)],
    )
    assert out.record.state is EpistemicState.UNIDENTIFIED
    assert out.record.unconditional_causal_authority is False
