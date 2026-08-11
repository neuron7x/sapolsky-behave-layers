from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np

from cwc.causal.regime_identifiability import evaluate_regime_iv
from cwc.epistemics.countermodel_search import search_countermodels
from cwc.epistemics.lattice import (
    CapabilityBindingError,
    EpistemicCapability,
    EpistemicError,
    EpistemicMachine,
    EpistemicRecord,
    EpistemicState,
    EvidenceKind,
    EvidenceRef,
    EvidenceSource,
)
from cwc.epistemics.legacy_adapter import adapt_countermodel_decision, adapt_regime_iv_decision


ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts/cog-epistemic-01"
RESULT = ROOT / "research/results/COG-EPISTEMIC-01"
COHORTS = {
    "PRIMARY": 61001,
    "REPLICATION": 71001,
}
N_CASES = 128
FAMILIES = (
    "F0_DIRECT_CONSTRUCTION_BYPASS",
    "F1_WRONG_CAPABILITY_CLASS",
    "F2_UNIDENTIFIED_RESURRECTION",
    "F3_FALSIFIED_RESURRECTION",
    "F4_NO_DIRECT_INTERVENTION_EVIDENCE",
    "F5_SURROGATE_AS_DIRECT_INTERVENTION",
    "F6_CROSS_CLAIM_TOKEN_REUSE",
    "F7_STALE_PARENT_TOKEN_REUSE",
    "F8_SCOPE_ESCALATION",
    "F9_EVIDENCE_HASH_OR_CLASS_MUTATION",
    "F10_LEGACY_ASSUMPTION_VIOLATION_PROMOTION",
    "F11_LEGACY_COUNTERMODEL_COLLAPSE",
)


def _sha_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _ev(
    label: str,
    kind: EvidenceKind,
    source: EvidenceSource,
    scope: tuple[str, ...],
) -> EvidenceRef:
    return EvidenceRef(
        ref=f"mem://{label}",
        sha256=_sha_text(label),
        kind=kind,
        source=source,
        context_scope=scope,
        provenance="COG-EPISTEMIC-01 synthetic confirmatory harness",
    )


def _base_claim(cohort: str, family: str, i: int) -> tuple[str, tuple[str, ...]]:
    # Independent namespaces ensure PRIMARY/REPLICATION capabilities and record
    # digests cannot accidentally coincide while semantic cases remain matched.
    claim = f"COG-EPISTEMIC-01:{cohort}:{family}:{i:03d}"
    return claim, (f"CTX:{cohort}:{i:03d}",)


def _observed(m: EpistemicMachine, claim: str, scope: tuple[str, ...], suffix: str = "") -> EpistemicRecord:
    return m.observe(
        claim_id=claim,
        context_scope=scope,
        evidence=[_ev(claim + ":fact" + suffix, EvidenceKind.FACTUAL_OBSERVATION, EvidenceSource.FACTUAL_CHANNEL, scope)],
    )


def _predictive(m: EpistemicMachine, o: EpistemicRecord, suffix: str = "") -> EpistemicRecord:
    cap = m.issue_predictive_capability(
        o,
        evidence=[_ev(o.claim_id + ":pred" + suffix, EvidenceKind.PREDICTIVE_VALIDATION, EvidenceSource.HELD_OUT_PREDICTION, o.context_scope)],
    )
    return m.transition(o, cap)


def _assumption(m: EpistemicMachine, p: EpistemicRecord, suffix: str = "") -> EpistemicRecord:
    cap = m.issue_assumption_capability(
        p,
        assumption_ids=("A1_EXOGENEITY", "A2_EXCLUSION"),
        evidence=[_ev(p.claim_id + ":assumption" + suffix, EvidenceKind.IDENTIFYING_ASSUMPTION, EvidenceSource.ASSUMPTION_CONTRACT, p.context_scope)],
    )
    return m.transition(p, cap)


def _legal_chain(cohort: str, i: int) -> tuple[bool, str, str]:
    claim, scope = _base_claim(cohort, "LEGAL", i)
    m = EpistemicMachine()
    try:
        o = _observed(m, claim, scope)
        p = _predictive(m, o)
        a = _assumption(m, p)
        cap = m.issue_intervention_capability(
            a,
            operator_id="do(span=SPACE)",
            evidence=[_ev(claim + ":do", EvidenceKind.DIRECT_INTERVENTION, EvidenceSource.DIRECT_SYSTEM_REEXECUTION, scope)],
        )
        end = m.transition(a, cap)
    except Exception as exc:  # a legal path must never rely on fail-closed exceptions
        return False, type(exc).__name__, str(exc)
    ok = (
        end.state is EpistemicState.INTERVENTION_SUPPORTED
        and end.operator_id == "do(span=SPACE)"
        and bool(end.assumption_ids)
        and end.unconditional_causal_authority is False
    )
    return ok, "", "" if ok else "legal chain ended in wrong state"


def _expect_block(fn) -> tuple[bool, str, str]:
    """Return (forbidden_accepted, exception_type, detail)."""
    try:
        fn()
    except (EpistemicError, TypeError, ValueError) as exc:
        return False, type(exc).__name__, str(exc)
    except Exception as exc:
        # Unexpected crashes are not counted as a safety success.
        return True, "UNEXPECTED_" + type(exc).__name__, str(exc)
    return True, "", "forbidden operation returned without error"


def _simulate_legacy(seed: int, *, confound_r: float) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    n = 1024
    u = rng.normal(size=n)
    e1 = rng.normal(size=n)
    e2 = rng.normal(size=n)
    r1 = np.where(e1 + confound_r * u >= 0.0, 1.0, -1.0)
    r2 = np.where(e2 + 0.7 * confound_r * u >= 0.0, 1.0, -1.0)
    regimes = np.column_stack((r1, r2))
    x = regimes @ np.array([0.9, 0.5]) + 0.8 * u + rng.normal(scale=0.6, size=n)
    y = 0.8 * x + u + rng.normal(scale=0.8, size=n)
    w = u + rng.normal(scale=0.5, size=n)
    return regimes, x, y, w


def _adapt_regime(
    m: EpistemicMachine,
    decision,
    claim: str,
    scope: tuple[str, ...],
):
    return adapt_regime_iv_decision(
        m,
        decision,
        claim_id=claim,
        factual_evidence=[_ev(claim+":lf", EvidenceKind.FACTUAL_OBSERVATION, EvidenceSource.FACTUAL_CHANNEL, scope)],
        predictive_evidence=[_ev(claim+":lp", EvidenceKind.PREDICTIVE_VALIDATION, EvidenceSource.HELD_OUT_PREDICTION, scope)],
        assumption_evidence=[_ev(claim+":la", EvidenceKind.IDENTIFYING_ASSUMPTION, EvidenceSource.ASSUMPTION_CONTRACT, scope)],
        terminal_evidence=[_ev(claim+":lt", EvidenceKind.IDENTIFYING_ASSUMPTION, EvidenceSource.ASSUMPTION_CONTRACT, scope)],
        context_scope=scope,
    )


def _attack(family: str, cohort: str, i: int, seed_base: int) -> tuple[bool, str, str]:
    claim, scope = _base_claim(cohort, family, i)
    m = EpistemicMachine()

    if family == "F0_DIRECT_CONSTRUCTION_BYPASS":
        def op():
            EpistemicRecord()  # type: ignore[call-arg]
        return _expect_block(op)

    o = _observed(m, claim, scope)

    if family == "F1_WRONG_CAPABILITY_CLASS":
        def op():
            m.issue_assumption_capability(
                o,
                assumption_ids=("A1",),
                evidence=[_ev(claim+":wrong-a", EvidenceKind.IDENTIFYING_ASSUMPTION, EvidenceSource.ASSUMPTION_CONTRACT, scope)],
            )
        return _expect_block(op)

    p = _predictive(m, o)

    if family == "F2_UNIDENTIFIED_RESURRECTION":
        t = m.issue_terminal_capability(
            p,
            target_state=EpistemicState.UNIDENTIFIED,
            evidence=[_ev(claim+":cm", EvidenceKind.COUNTERMODEL, EvidenceSource.COUNTERMODEL_SEARCH, scope)],
            reason="equivalent countermodel",
        )
        u = m.transition(p, t)
        def op():
            m.issue_intervention_capability(
                u,
                operator_id="do(X)",
                evidence=[_ev(claim+":do", EvidenceKind.DIRECT_INTERVENTION, EvidenceSource.DIRECT_SYSTEM_REEXECUTION, scope)],
            )
        return _expect_block(op)

    if family == "F3_FALSIFIED_RESURRECTION":
        t = m.issue_terminal_capability(
            p,
            target_state=EpistemicState.FALSIFIED,
            evidence=[_ev(claim+":fals", EvidenceKind.FALSIFICATION, EvidenceSource.DIAGNOSTIC, scope)],
            reason="contradiction",
        )
        f = m.transition(p, t)
        def op():
            m.issue_assumption_capability(
                f,
                assumption_ids=("A1",),
                evidence=[_ev(claim+":a", EvidenceKind.IDENTIFYING_ASSUMPTION, EvidenceSource.ASSUMPTION_CONTRACT, scope)],
            )
        return _expect_block(op)

    a = _assumption(m, p)

    if family == "F4_NO_DIRECT_INTERVENTION_EVIDENCE":
        def op():
            m.issue_intervention_capability(
                a,
                operator_id="do(X)",
                evidence=[_ev(claim+":assumption-only", EvidenceKind.IDENTIFYING_ASSUMPTION, EvidenceSource.ASSUMPTION_CONTRACT, scope)],
            )
        return _expect_block(op)

    if family == "F5_SURROGATE_AS_DIRECT_INTERVENTION":
        def op():
            m.issue_intervention_capability(
                a,
                operator_id="do(X)",
                evidence=[_ev(claim+":surrogate", EvidenceKind.DIRECT_INTERVENTION, EvidenceSource.SURROGATE_MODEL, scope)],
            )
        return _expect_block(op)

    if family == "F6_CROSS_CLAIM_TOKEN_REUSE":
        other = _observed(m, claim+":OTHER", scope, suffix=":other")
        cap = m.issue_predictive_capability(
            o,
            evidence=[_ev(claim+":bound-pred", EvidenceKind.PREDICTIVE_VALIDATION, EvidenceSource.HELD_OUT_PREDICTION, scope)],
        )
        return _expect_block(lambda: m.transition(other, cap))

    if family == "F7_STALE_PARENT_TOKEN_REUSE":
        fresh_o = _observed(m, claim+":STALE", scope, suffix=":stale")
        cap = m.issue_predictive_capability(
            fresh_o,
            evidence=[_ev(claim+":stale-pred", EvidenceKind.PREDICTIVE_VALIDATION, EvidenceSource.HELD_OUT_PREDICTION, scope)],
        )
        fresh_p = m.transition(fresh_o, cap)
        return _expect_block(lambda: m.transition(fresh_p, cap))

    if family == "F8_SCOPE_ESCALATION":
        wider = tuple(sorted(scope + ("GLOBAL",)))
        def op():
            m.issue_predictive_capability(
                o,
                context_scope=wider,
                evidence=[_ev(claim+":wide", EvidenceKind.PREDICTIVE_VALIDATION, EvidenceSource.HELD_OUT_PREDICTION, wider)],
            )
        return _expect_block(op)

    if family == "F9_EVIDENCE_HASH_OR_CLASS_MUTATION":
        def op():
            bad_hash_accepted = False
            try:
                EvidenceRef(
                    ref="mem://bad",
                    sha256="0" * 63,
                    kind=EvidenceKind.PREDICTIVE_VALIDATION,
                    source=EvidenceSource.HELD_OUT_PREDICTION,
                    context_scope=scope,
                    provenance="mutant",
                )
                bad_hash_accepted = True
            except ValueError:
                pass
            try:
                m.issue_intervention_capability(
                    a,
                    operator_id="do(X)",
                    evidence=[_ev(claim+":wrong-kind", EvidenceKind.SURROGATE_COUNTERFACTUAL, EvidenceSource.DIRECT_SYSTEM_REEXECUTION, scope)],
                )
                bad_hash_accepted = True
            except EpistemicError:
                pass
            if bad_hash_accepted:
                return None
            raise ValueError("both evidence mutations rejected")
        accepted, exc, detail = _expect_block(op)
        # `_expect_block` sees our explicit ValueError as the expected block when both mutations fail.
        return accepted, exc, detail

    legacy_seed = seed_base + i

    if family == "F10_LEGACY_ASSUMPTION_VIOLATION_PROMOTION":
        regimes, x, y, w = _simulate_legacy(legacy_seed, confound_r=1.0)
        d = evaluate_regime_iv(regimes=regimes, treatment=x, outcome=y, negative_control=w, alpha=0.01)
        if d.state != "IDENTIFYING_ASSUMPTION_VIOLATED":
            return True, "HARNESS_STATE_ERROR", d.state
        out = _adapt_regime(m, d, claim, scope)
        accepted = out.record.state in {
            EpistemicState.ASSUMPTION_CONDITIONAL,
            EpistemicState.INTERVENTION_SUPPORTED,
        }
        return accepted, "", out.record.state.value

    if family == "F11_LEGACY_COUNTERMODEL_COLLAPSE":
        regimes, x, y, w = _simulate_legacy(legacy_seed, confound_r=0.0)
        d = evaluate_regime_iv(regimes=regimes, treatment=x, outcome=y, negative_control=w, alpha=0.01)
        if d.state != "CAUSAL_CANDIDATE_UNDER_ASSUMPTIONS" or d.beta_hat is None:
            return True, "HARNESS_STATE_ERROR", d.state
        upstream = _adapt_regime(m, d, claim, scope).record
        counter = search_countermodels(
            regimes=regimes,
            treatment=x,
            outcome=y,
            reference_beta=float(d.beta_hat),
            beta_grid=(-1.0, -0.5, 0.0, 0.5, 1.3, 1.8, 2.3),
            min_causal_shift=0.4,
            candidate_state=d.state,
            bounds=None,
        )
        if counter.state != "OBSERVATIONALLY_EQUIVALENT_COUNTERMODEL_SURVIVES":
            return True, "HARNESS_COUNTERMODEL_ERROR", counter.state
        out = adapt_countermodel_decision(
            m,
            upstream,
            counter,
            countermodel_evidence=[_ev(claim+":counter", EvidenceKind.COUNTERMODEL, EvidenceSource.COUNTERMODEL_SEARCH, scope)],
        )
        accepted = out.record.state is not EpistemicState.UNIDENTIFIED
        return accepted, "", out.record.state.value

    raise AssertionError(f"unknown family {family}")


def _digest_checks(cohort: str) -> dict[str, bool]:
    m = EpistemicMachine()
    scope = (f"CTX:{cohort}:DIGEST",)
    e1 = _ev(f"{cohort}:d1", EvidenceKind.FACTUAL_OBSERVATION, EvidenceSource.FACTUAL_CHANNEL, scope)
    e2 = _ev(f"{cohort}:d2", EvidenceKind.FACTUAL_OBSERVATION, EvidenceSource.FACTUAL_CHANNEL, scope)
    a = m.observe(claim_id=f"{cohort}:DIGEST", context_scope=scope, evidence=[e1, e2])
    b = m.observe(claim_id=f"{cohort}:DIGEST", context_scope=scope, evidence=[e2, e1])
    c = m.observe(claim_id=f"{cohort}:DIGEST:CHANGED", context_scope=scope, evidence=[e1, e2])
    return {
        "deterministic_identical_content": a.record_digest == b.record_digest,
        "payload_change_changes_digest": a.record_digest != c.record_digest,
    }


def run() -> dict:
    started = time.perf_counter()
    rows: list[dict[str, object]] = []
    summaries: dict[str, dict[str, object]] = {}

    for cohort, seed_base in COHORTS.items():
        legal_results = [_legal_chain(cohort, i) for i in range(N_CASES)]
        legal_accepts = sum(int(ok) for ok, _, _ in legal_results)
        family_summary: dict[str, dict[str, object]] = {}
        for family in FAMILIES:
            accepted = 0
            unexpected = 0
            for i in range(N_CASES):
                bad, exc, detail = _attack(family, cohort, i, seed_base)
                accepted += int(bad)
                unexpected += int(exc.startswith("UNEXPECTED_") or exc.startswith("HARNESS_"))
                rows.append(
                    {
                        "cohort": cohort,
                        "family": family,
                        "case": i,
                        "forbidden_transition_accepted": int(bad),
                        "exception_type": exc,
                        "detail": detail,
                    }
                )
            family_summary[family] = {
                "n": N_CASES,
                "forbidden_accept_count": accepted,
                "forbidden_acceptance_rate": accepted / N_CASES,
                "unexpected_or_harness_error_count": unexpected,
            }
        summaries[cohort] = {
            "legal_chain_n": N_CASES,
            "legal_chain_accept_count": legal_accepts,
            "legal_transition_acceptance_rate": legal_accepts / N_CASES,
            "families": family_summary,
            "digest_checks": _digest_checks(cohort),
        }

    errors: list[str] = []
    for cohort, summary in summaries.items():
        if summary["legal_transition_acceptance_rate"] != 1.0:
            errors.append(f"{cohort}: legal chain acceptance")
        digest = summary["digest_checks"]
        if not all(bool(v) for v in digest.values()):
            errors.append(f"{cohort}: digest invariant")
        for family, fs in summary["families"].items():
            if fs["forbidden_accept_count"] != 0:
                errors.append(f"{cohort}: {family} accepted forbidden transition")
            if fs["unexpected_or_harness_error_count"] != 0:
                errors.append(f"{cohort}: {family} harness/runtime error")

    scientific_pass = not errors
    return {
        "experiment_id": "COG-EPISTEMIC-01",
        "preconfirmatory_preregistration_commit": "9479c217d1650839a00ba5a4285137a860ec47fd",
        "verdict": "TYPED_EPISTEMIC_LATTICE_QUALIFIED_SYNTHETIC_NARROWED" if scientific_pass else "TYPED_EPISTEMIC_LATTICE_NOT_QUALIFIED",
        "scientific_pass": scientific_pass,
        "authority": "EPISTEMIC_RUNTIME_SAFETY_PRIMITIVE_ONLY" if scientific_pass else "NO_PROMOTION",
        "primary_endpoint": "forbidden_transition_acceptance_rate==0 in every family/cohort",
        "positive_chain": [s.value for s in (
            EpistemicState.OBSERVED,
            EpistemicState.PREDICTIVE,
            EpistemicState.ASSUMPTION_CONDITIONAL,
            EpistemicState.INTERVENTION_SUPPORTED,
        )],
        "terminal_states": [s.value for s in (
            EpistemicState.UNIDENTIFIED,
            EpistemicState.FALSIFIED,
            EpistemicState.OOD,
            EpistemicState.ABSTAIN,
        )],
        "cases_per_family_per_cohort": N_CASES,
        "cohorts": summaries,
        "errors": errors,
        "epistemic_boundary": {
            "intervention_supported_equals_true_causal_model": False,
            "unconditional_causal_truth_state_exists": False,
            "terminal_record_resurrection_allowed": False,
            "surrogate_or_replay_can_mint_direct_intervention_authority": False,
            "semantic_causality": False,
            "real_trace_identification": False,
            "replay_control": False,
            "active_control": False,
            "architecture_promotion": False,
        },
        "wall_seconds": time.perf_counter() - started,
        "rows": rows,
    }


def main() -> int:
    ART.mkdir(parents=True, exist_ok=True)
    RESULT.mkdir(parents=True, exist_ok=True)
    payload = run()
    rows = payload.pop("rows")
    verdict_bytes = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    (ART / "verdict.json").write_bytes(verdict_bytes)
    (RESULT / "verdict.json").write_bytes(verdict_bytes)
    with (ART / "transition_matrix.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=(
            "cohort", "family", "case", "forbidden_transition_accepted", "exception_type", "detail"
        ))
        writer.writeheader()
        writer.writerows(rows)
    checks = []
    for name in ("verdict.json", "transition_matrix.csv"):
        path = ART / name
        checks.append(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {name}")
    (ART / "SHA256SUMS").write_text("\n".join(checks) + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if payload["scientific_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
