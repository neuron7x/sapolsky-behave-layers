from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import time

from cwc.causal.regime_identifiability import (
    AssumptionClass,
    AssumptionStatus,
    IdentifyingAssumption,
    RegimeIVDecision,
)
from cwc.epistemics.countermodel_search import CountermodelSearchDecision
from cwc.epistemics.lattice import (
    EpistemicMachine,
    EpistemicState,
    EvidenceKind,
    EvidenceSource,
)
from cwc.epistemics.legacy_adapter import adapt_countermodel_decision, adapt_regime_iv_decision
from experiments.cog_epistemic_01.run import (
    FAMILIES,
    N_CASES,
    _attack,
    _digest_checks,
    _ev,
    _legal_chain,
)


ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts/cog-epistemic-01r"
RESULT = ROOT / "research/results/COG-EPISTEMIC-01R"
COHORTS = {
    "PRIMARY": ("R1_PRIMARY", 81001),
    "REPLICATION": ("R1_REPLICATION", 91001),
}


def _legacy_candidate_fixture() -> RegimeIVDecision:
    assumptions = (
        IdentifyingAssumption(
            "A1_RELEVANCE",
            "fixture relevance assumption",
            AssumptionClass.EMPIRICALLY_FALSIFIABLE,
            AssumptionStatus.SURVIVED_AVAILABLE_TESTS,
            "immutable adapter fixture",
        ),
        IdentifyingAssumption(
            "A3_EXCLUSION",
            "fixture exclusion assumption",
            AssumptionClass.UNTESTABLE_FROM_FACTUAL_CHANNEL,
            AssumptionStatus.NOT_TESTABLE_FROM_CHANNEL,
            "immutable adapter fixture",
        ),
    )
    return RegimeIVDecision(
        state="CAUSAL_CANDIDATE_UNDER_ASSUMPTIONS",
        beta_hat=0.8,
        beta_se=0.02,
        z_critical=3.0,
        relevant_instruments=2,
        instrument_moments=(),
        max_overidentification_z=0.0,
        max_negative_control_z=0.0,
        assumptions=assumptions,
        causal_authority_granted=False,
        unresolved_assumption_debt=("A3_EXCLUSION_NOT_TESTABLE_FROM_FACTUAL_CHANNEL",),
    )


def _legacy_violation_fixture() -> RegimeIVDecision:
    assumptions = (
        IdentifyingAssumption(
            "A2_EXOGENEITY",
            "fixture violated exogeneity",
            AssumptionClass.PARTIALLY_FALSIFIABLE,
            AssumptionStatus.VIOLATED,
            "immutable adapter fixture",
        ),
    )
    return RegimeIVDecision(
        state="IDENTIFYING_ASSUMPTION_VIOLATED",
        beta_hat=None,
        beta_se=None,
        z_critical=3.0,
        relevant_instruments=2,
        instrument_moments=(),
        max_overidentification_z=0.0,
        max_negative_control_z=9.0,
        assumptions=assumptions,
        causal_authority_granted=False,
        unresolved_assumption_debt=("A2_EXOGENEITY_VIOLATED",),
    )


def _countermodel_survival_fixture() -> CountermodelSearchDecision:
    return CountermodelSearchDecision(
        state="OBSERVATIONALLY_EQUIVALENT_COUNTERMODEL_SURVIVES",
        reference_beta=0.8,
        min_causal_shift=0.4,
        total_examined=1,
        exact_equivalent_count=1,
        constrained_survivor_count=1,
        pareto_frontier=(),
        nearest_constrained_countermodel=None,
        nearest_unrestricted_countermodel=None,
        unrestricted_beta_set_kind="ALL_REAL_BETA_UNDER_UNRESTRICTED_REPARAMETERIZATION",
        declared_direct_effect_beta_interval=None,
        material_countermodel_within_declared_bounds=True,
        finite_grid_alternative_beta_min=1.3,
        finite_grid_alternative_beta_max=1.3,
        finite_grid_alternative_beta_diameter=0.0,
        causal_authority_granted=False,
        reason="immutable adapter fixture: exact observational countermodel survives",
    )


def _adapt_fixture(machine: EpistemicMachine, decision: RegimeIVDecision, claim: str, scope: tuple[str, ...]):
    return adapt_regime_iv_decision(
        machine,
        decision,
        claim_id=claim,
        factual_evidence=[_ev(claim+":lf", EvidenceKind.FACTUAL_OBSERVATION, EvidenceSource.FACTUAL_CHANNEL, scope)],
        predictive_evidence=[_ev(claim+":lp", EvidenceKind.PREDICTIVE_VALIDATION, EvidenceSource.HELD_OUT_PREDICTION, scope)],
        assumption_evidence=[_ev(claim+":la", EvidenceKind.IDENTIFYING_ASSUMPTION, EvidenceSource.ASSUMPTION_CONTRACT, scope)],
        terminal_evidence=[_ev(claim+":lt", EvidenceKind.IDENTIFYING_ASSUMPTION, EvidenceSource.ASSUMPTION_CONTRACT, scope)],
        context_scope=scope,
    )


def _attack_r1(family: str, namespace: str, i: int, seed_base: int) -> tuple[bool, str, str]:
    if family not in {"F10_LEGACY_ASSUMPTION_VIOLATION_PROMOTION", "F11_LEGACY_COUNTERMODEL_COLLAPSE"}:
        return _attack(family, namespace, i, seed_base)

    claim = f"COG-EPISTEMIC-01R:{namespace}:{family}:{seed_base+i}"
    scope = (f"CTX:COG-EPISTEMIC-01R:{namespace}:{i:03d}",)
    machine = EpistemicMachine()

    if family == "F10_LEGACY_ASSUMPTION_VIOLATION_PROMOTION":
        out = _adapt_fixture(machine, _legacy_violation_fixture(), claim, scope)
        accepted = out.record.state in {
            EpistemicState.ASSUMPTION_CONDITIONAL,
            EpistemicState.INTERVENTION_SUPPORTED,
        }
        return accepted, "", out.record.state.value

    upstream = _adapt_fixture(machine, _legacy_candidate_fixture(), claim, scope).record
    out = adapt_countermodel_decision(
        machine,
        upstream,
        _countermodel_survival_fixture(),
        countermodel_evidence=[
            _ev(claim+":counter", EvidenceKind.COUNTERMODEL, EvidenceSource.COUNTERMODEL_SEARCH, scope)
        ],
    )
    accepted = out.record.state is not EpistemicState.UNIDENTIFIED
    return accepted, "", out.record.state.value


def run() -> dict:
    started = time.perf_counter()
    rows: list[dict[str, object]] = []
    summaries: dict[str, dict[str, object]] = {}
    for cohort, (namespace, seed_base) in COHORTS.items():
        legal_results = [_legal_chain(namespace, i) for i in range(N_CASES)]
        legal_accepts = sum(int(ok) for ok, _, _ in legal_results)
        family_summary: dict[str, dict[str, object]] = {}
        for family in FAMILIES:
            accepted = 0
            unexpected = 0
            for i in range(N_CASES):
                bad, exc, detail = _attack_r1(family, namespace, i, seed_base)
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
            "namespace": namespace,
            "seed_base": seed_base,
            "legal_chain_n": N_CASES,
            "legal_chain_accept_count": legal_accepts,
            "legal_transition_acceptance_rate": legal_accepts / N_CASES,
            "families": family_summary,
            "digest_checks": _digest_checks(namespace),
        }

    errors: list[str] = []
    for cohort, summary in summaries.items():
        if summary["legal_transition_acceptance_rate"] != 1.0:
            errors.append(f"{cohort}: legal chain acceptance")
        if not all(bool(v) for v in summary["digest_checks"].values()):
            errors.append(f"{cohort}: digest invariant")
        for family, fs in summary["families"].items():
            if fs["forbidden_accept_count"] != 0:
                errors.append(f"{cohort}: {family} accepted forbidden transition")
            if fs["unexpected_or_harness_error_count"] != 0:
                errors.append(f"{cohort}: {family} harness/runtime error")

    scientific_pass = not errors
    return {
        "experiment_id": "COG-EPISTEMIC-01R",
        "parent_experiment": "COG-EPISTEMIC-01",
        "parent_raw_verdict": "TYPED_EPISTEMIC_LATTICE_NOT_QUALIFIED",
        "parent_invalidation_reason": "F11 stochastic upstream precondition not guaranteed; one replication case never exercised target adapter",
        "preconfirmatory_preregistration_commit": "608e629a01490d58645d9c3f7fc73293b83ea3e4",
        "verdict": "TYPED_EPISTEMIC_LATTICE_QUALIFIED_SYNTHETIC_NARROWED" if scientific_pass else "TYPED_EPISTEMIC_LATTICE_R1_NOT_QUALIFIED",
        "scientific_pass": scientific_pass,
        "authority": "EPISTEMIC_RUNTIME_SAFETY_PRIMITIVE_ONLY" if scientific_pass else "NO_PROMOTION",
        "primary_endpoint": "forbidden_transition_acceptance_rate==0 in every family/cohort",
        "repair": {
            "thresholds_weakened": False,
            "frozen_family_semantics_changed": False,
            "F10_F11_preconditions_changed_to_immutable_api_state_fixtures": True,
            "fresh_namespaces": True,
        },
        "positive_chain": [
            "OBSERVED", "PREDICTIVE", "ASSUMPTION_CONDITIONAL", "INTERVENTION_SUPPORTED"
        ],
        "terminal_states": ["UNIDENTIFIED", "FALSIFIED", "OOD", "ABSTAIN"],
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
        writer = csv.DictWriter(
            f,
            fieldnames=("cohort", "family", "case", "forbidden_transition_accepted", "exception_type", "detail"),
        )
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
