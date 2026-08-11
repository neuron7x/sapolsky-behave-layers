from __future__ import annotations

import hashlib
import json
import random
import subprocess
from pathlib import Path
from typing import Any

from cwc.epistemics.lattice import (
    EpistemicMachine,
    EvidenceKind,
    EvidenceRef,
    EvidenceSource,
)
from cwc.epistemics.self_falsification import (
    FalsificationAttack,
    FalsificationBindingError,
    FalsificationOutcome,
    SelfFalsificationState,
    apply_self_falsification_outcome,
    select_self_falsification_attack,
)
from cwc.memory.epistemic_store import EpistemicMemoryLedger, MemoryStatus
from cwc.planning.proof_carrying import WorldBranch, plan_counterfactual


ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts/cog-self-01"
RES = ROOT / "research/results/COG-SELF-01"
SCOPE = ("COG-SELF-01",)
FAMILIES = tuple(f"S{i}" for i in range(12))
N_PER_FAMILY = 128
COHORT_BASES = {"PRIMARY": 710811, "REPLICATION": 810811}
PREREG_COMMIT = "ee99a9e732e3b4fc408f80a9a3ce71d3178717d6"


def _git_head() -> str:
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def _ev(label: str, kind: EvidenceKind, source: EvidenceSource) -> EvidenceRef:
    return EvidenceRef(
        ref=f"self01://{label}",
        sha256=hashlib.sha256(label.encode()).hexdigest(),
        kind=kind,
        source=source,
        context_scope=SCOPE,
        provenance="COG-SELF-01 synthetic confirmatory harness",
    )


def _record(tag: str):
    m = EpistemicMachine()
    o = m.observe(
        claim_id=f"CLAIM-{tag}", context_scope=SCOPE,
        evidence=[_ev(f"{tag}-obs", EvidenceKind.FACTUAL_OBSERVATION, EvidenceSource.FACTUAL_CHANNEL)],
    )
    p = m.transition(
        o, m.issue_predictive_capability(
            o, evidence=[_ev(f"{tag}-pred", EvidenceKind.PREDICTIVE_VALIDATION, EvidenceSource.HELD_OUT_PREDICTION)],
        ),
    )
    a = m.transition(
        p, m.issue_assumption_capability(
            p, assumption_ids=("A1",),
            evidence=[_ev(f"{tag}-assumption", EvidenceKind.IDENTIFYING_ASSUMPTION, EvidenceSource.ASSUMPTION_CONTRACT)],
        ),
    )
    return m.transition(
        a, m.issue_intervention_capability(
            a, operator_id="do(X)",
            evidence=[_ev(f"{tag}-intervention", EvidenceKind.DIRECT_INTERVENTION, EvidenceSource.DIRECT_SYSTEM_REEXECUTION)],
        ),
    )


def _ledger(tag: str, *, outsider: bool = False):
    rec = _record(tag)
    ledger = EpistemicMemoryLedger()
    parent = ledger.consolidate(memory_id="parent", epistemic_record=rec)
    child = ledger.consolidate(memory_id="child", epistemic_record=rec, dependency_ids=("parent",))
    if outsider:
        ledger.consolidate(memory_id="outsider", epistemic_record=rec)
    return ledger, parent, child


def _worlds(kind: str, jitter: float):
    j = min(0.02, max(0.0, jitter))
    if kind == "same":
        return [
            WorldBranch("BASE", {"A": 1.0 + j, "B": 0.0}, "COG-SELF-01"),
            WorldBranch("CM", {"A": 0.9 + j, "B": 0.1}, "COG-SELF-01"),
        ]
    if kind == "three":
        return [
            WorldBranch("BASE", {"A": 1.0 + j, "B": 0.0}, "COG-SELF-01"),
            WorldBranch("SAME", {"A": 0.9 + j, "B": 0.1}, "COG-SELF-01"),
            WorldBranch("CROSS", {"A": 0.0, "B": 1.0 + j}, "COG-SELF-01"),
        ]
    return [
        WorldBranch("BASE", {"A": 1.0 + j, "B": 0.0}, "COG-SELF-01"),
        WorldBranch("CM", {"A": 0.0, "B": 1.0 + j}, "COG-SELF-01"),
    ]


def _plan(ledger: EpistemicMemoryLedger, child, worlds):
    return plan_counterfactual(
        ledger=ledger,
        plan_id="COG-SELF-01-PLAN",
        context_scope=SCOPE,
        required_memories=[child],
        worlds=worlds,
    ).certificate


def _attack(
    attack_id: str,
    rates: dict[str, float],
    *,
    cost: float = 1.0,
    worlds=("CM",),
    memories=("parent",),
    assumptions=(),
    certificate="CERTIFIED_LOWER_BOUND",
    max_units=None,
) -> FalsificationAttack:
    return FalsificationAttack(
        attack_id=attack_id,
        unit_cost=cost,
        information_rate_lower_bounds=rates,
        rate_certificate=certificate,
        target_world_ids=tuple(worlds),
        target_memory_ids=tuple(memories),
        target_assumption_ids=tuple(assumptions),
        max_units=max_units,
    )


def _base_row(cohort: str, family: str, seed: int) -> dict[str, Any]:
    return {
        "cohort": cohort,
        "family": family,
        "seed": seed,
        "state": None,
        "attack_id": None,
        "passed": False,
        "runtime_error": None,
        "false_spend": False,
        "irrelevant_attack_selected": False,
        "uncertified_attack_selected": False,
        "stale_plan_accepted": False,
        "permutation_disagreement": False,
        "survival_promotion": False,
        "negative_target_violation": False,
        "negative_propagation_pass": None,
        "stale_or_unbound_outcome_accepted": False,
        "necessary_cost_lower_bound": None,
    }


def _case(cohort: str, family: str, seed: int) -> dict[str, Any]:
    row = _base_row(cohort, family, seed)
    rng = random.Random(seed * 1009 + int(family[1:]) * 9176)
    jitter = rng.uniform(0.001, 0.02)
    try:
        if family == "S0":
            ledger, _, child = _ledger(f"{cohort}-{family}-{seed}")
            worlds = _worlds("same", jitter); cert = _plan(ledger, child, worlds)
            tempting = _attack("tempting", {"CM": 20.0 + jitter})
            d = select_self_falsification_attack(
                ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds,
                candidate_world_id="BASE", attacks=[tempting], available_budget=1000.0,
            )
            row.update(state=d.state.value, attack_id=d.attack_id)
            row["false_spend"] = d.attack_id is not None
            row["passed"] = d.state is SelfFalsificationState.NO_DECISION_RELEVANT_ATTACK and d.attack_id is None

        elif family == "S1":
            ledger, _, child = _ledger(f"{cohort}-{family}-{seed}")
            worlds = _worlds("reverse", jitter); cert = _plan(ledger, child, worlds)
            slow = _attack("slow", {"CM": 0.35 + jitter}, cost=2.0)
            fast = _attack("fast", {"CM": 0.55 + jitter}, cost=1.0)
            d = select_self_falsification_attack(
                ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds,
                candidate_world_id="BASE", attacks=[slow, fast], available_budget=1000.0,
            )
            row.update(state=d.state.value, attack_id=d.attack_id, necessary_cost_lower_bound=d.necessary_cost_lower_bound)
            row["passed"] = d.state is SelfFalsificationState.PROPOSE_BOUNDED_FALSIFICATION and d.attack_id == "fast"

        elif family == "S2":
            ledger, _, child = _ledger(f"{cohort}-{family}-{seed}")
            worlds = _worlds("three", jitter); cert = _plan(ledger, child, worlds)
            nuisance = _attack("nuisance", {"SAME": 50.0, "CROSS": 0.08 + jitter}, worlds=("CROSS",))
            decisive = _attack("decisive", {"SAME": 0.001, "CROSS": 0.60 + jitter}, worlds=("CROSS",))
            d = select_self_falsification_attack(
                ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds,
                candidate_world_id="BASE", attacks=[nuisance, decisive], available_budget=1000.0,
            )
            row.update(state=d.state.value, attack_id=d.attack_id, necessary_cost_lower_bound=d.necessary_cost_lower_bound)
            row["passed"] = (
                d.state is SelfFalsificationState.PROPOSE_BOUNDED_FALSIFICATION
                and d.attack_id == "decisive"
                and d.cross_decision_world_ids == ("CROSS",)
                and d.ignored_same_decision_world_ids == ("SAME",)
            )

        elif family == "S3":
            ledger, _, child = _ledger(f"{cohort}-{family}-{seed}")
            worlds = _worlds("reverse", jitter); cert = _plan(ledger, child, worlds)
            d = select_self_falsification_attack(
                ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds,
                candidate_world_id="BASE", attacks=[_attack("zero", {"CM": 0.0})], available_budget=1000.0,
            )
            row.update(state=d.state.value, attack_id=d.attack_id)
            row["false_spend"] = d.state is SelfFalsificationState.PROPOSE_BOUNDED_FALSIFICATION
            row["passed"] = d.state is SelfFalsificationState.NO_DECISION_IDENTIFYING_ATTACK

        elif family == "S4":
            ledger, _, child = _ledger(f"{cohort}-{family}-{seed}")
            worlds = _worlds("reverse", jitter); cert = _plan(ledger, child, worlds)
            ledger.retract("parent", reason="frozen stale-plan mutation")
            d = select_self_falsification_attack(
                ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds,
                candidate_world_id="BASE", attacks=[_attack("a", {"CM": 1.0})], available_budget=1000.0,
            )
            row.update(state=d.state.value, attack_id=d.attack_id)
            row["stale_plan_accepted"] = d.state is not SelfFalsificationState.REJECT_INVALID_PLAN_CERTIFICATE
            row["passed"] = d.state is SelfFalsificationState.REJECT_INVALID_PLAN_CERTIFICATE

        elif family == "S5":
            ledger, _, child = _ledger(f"{cohort}-{family}-{seed}", outsider=True)
            worlds = _worlds("reverse", jitter); cert = _plan(ledger, child, worlds)
            irrelevant = _attack("irrelevant", {"CM": 100.0}, memories=("outsider",))
            bound = _attack("bound", {"CM": 0.5 + jitter}, memories=("parent",))
            d = select_self_falsification_attack(
                ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds,
                candidate_world_id="BASE", attacks=[irrelevant, bound], available_budget=1000.0,
            )
            row.update(state=d.state.value, attack_id=d.attack_id)
            row["irrelevant_attack_selected"] = d.attack_id == "irrelevant"
            row["passed"] = d.state is SelfFalsificationState.PROPOSE_BOUNDED_FALSIFICATION and d.attack_id == "bound"

        elif family == "S6":
            ledger, _, child = _ledger(f"{cohort}-{family}-{seed}")
            worlds = _worlds("reverse", jitter); cert = _plan(ledger, child, worlds)
            d = select_self_falsification_attack(
                ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds,
                candidate_world_id="BASE", attacks=[_attack("parent-test", {"CM": 1.0 + jitter})], available_budget=1000.0,
            )
            update = apply_self_falsification_outcome(
                decision=d, ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds,
                outcome=FalsificationOutcome.FALSIFIED_MEMORY, target_id="parent", reason="frozen parent falsifier",
            )
            propagation = set(update.changed_memory_ids) == {"parent", "child"} and all(
                ledger.record(mid).status is MemoryStatus.RETRACTED for mid in ("parent", "child")
            )
            row.update(state=d.state.value, attack_id=d.attack_id, negative_propagation_pass=propagation)
            row["survival_promotion"] = update.authority_promoted
            row["passed"] = d.attack_id == "parent-test" and propagation and not update.authority_promoted

        elif family == "S7":
            ledger, _, child = _ledger(f"{cohort}-{family}-{seed}")
            worlds = _worlds("reverse", jitter); cert = _plan(ledger, child, worlds)
            fake = _attack("fake", {"CM": 1000.0}, certificate="POINT_ESTIMATE_ONLY")
            certified = _attack("certified", {"CM": 0.45 + jitter})
            d = select_self_falsification_attack(
                ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds,
                candidate_world_id="BASE", attacks=[fake, certified], available_budget=1000.0,
            )
            row.update(state=d.state.value, attack_id=d.attack_id)
            row["uncertified_attack_selected"] = d.attack_id == "fake"
            row["passed"] = d.state is SelfFalsificationState.PROPOSE_BOUNDED_FALSIFICATION and d.attack_id == "certified"

        elif family == "S8":
            ledger, _, child = _ledger(f"{cohort}-{family}-{seed}")
            worlds = _worlds("reverse", jitter); cert = _plan(ledger, child, worlds)
            if seed % 2 == 0:
                attack = _attack("capacity", {"CM": 0.5 + jitter}, max_units=1)
                budget = 1000.0
                expected = SelfFalsificationState.ATTACK_CAPACITY_BELOW_NECESSARY_BOUND
            else:
                attack = _attack("budget", {"CM": 0.5 + jitter})
                budget = 0.01
                expected = SelfFalsificationState.INSUFFICIENT_ATTACK_BUDGET
            d = select_self_falsification_attack(
                ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds,
                candidate_world_id="BASE", attacks=[attack], available_budget=budget,
            )
            row.update(state=d.state.value, attack_id=d.attack_id)
            row["false_spend"] = d.state is SelfFalsificationState.PROPOSE_BOUNDED_FALSIFICATION
            row["passed"] = d.state is expected and not row["false_spend"]

        elif family == "S9":
            ledger, _, child = _ledger(f"{cohort}-{family}-{seed}")
            worlds = _worlds("reverse", jitter); cert = _plan(ledger, child, worlds)
            a = _attack("a", {"CM": 0.55 + jitter})
            b = _attack("b", {"CM": 0.25 + jitter})
            d1 = select_self_falsification_attack(
                ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds,
                candidate_world_id="BASE", attacks=[a, b], available_budget=1000.0,
            )
            d2 = select_self_falsification_attack(
                ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=list(reversed(worlds)),
                candidate_world_id="BASE", attacks=[b, a], available_budget=1000.0,
            )
            disagreement = not (
                d1.state == d2.state and d1.attack_id == d2.attack_id
                and d1.necessary_cost_lower_bound == d2.necessary_cost_lower_bound
                and d1.decision_digest == d2.decision_digest
            )
            row.update(state=d1.state.value, attack_id=d1.attack_id, permutation_disagreement=disagreement)
            row["passed"] = not disagreement and d1.attack_id == "a"

        elif family == "S10":
            ledger, _, child = _ledger(f"{cohort}-{family}-{seed}")
            worlds = _worlds("reverse", jitter); cert = _plan(ledger, child, worlds)
            mode = seed % 3
            if mode == 0:
                attack = _attack("memory-test", {"CM": 1.0 + jitter})
                outcome = FalsificationOutcome.FALSIFIED_MEMORY; target = "parent"
            elif mode == 1:
                attack = _attack("assumption-test", {"CM": 1.0 + jitter}, memories=(), assumptions=("A1",))
                outcome = FalsificationOutcome.INVALIDATED_ASSUMPTION; target = "A1"
            else:
                attack = _attack("survival-test", {"CM": 1.0 + jitter})
                outcome = FalsificationOutcome.SURVIVED; target = None
            d = select_self_falsification_attack(
                ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds,
                candidate_world_id="BASE", attacks=[attack], available_budget=1000.0,
            )
            before = tuple((mid, ledger.record(mid).memory_digest) for mid in ledger.memory_ids)
            update = apply_self_falsification_outcome(
                decision=d, ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds,
                outcome=outcome, target_id=target, reason="frozen S10 outcome",
            )
            after = tuple((mid, ledger.record(mid).memory_digest) for mid in ledger.memory_ids)
            if outcome is FalsificationOutcome.SURVIVED:
                propagation = before == after and update.changed_memory_ids == ()
            else:
                propagation = set(update.changed_memory_ids) == {"parent", "child"}
            row.update(state=d.state.value, attack_id=d.attack_id, negative_propagation_pass=propagation)
            row["survival_promotion"] = update.authority_promoted
            row["negative_target_violation"] = (
                outcome is FalsificationOutcome.FALSIFIED_MEMORY and target not in d.selected_target_memory_ids
            ) or (
                outcome is FalsificationOutcome.INVALIDATED_ASSUMPTION and target not in d.selected_target_assumption_ids
            )
            row["passed"] = propagation and not update.authority_promoted and not row["negative_target_violation"]

        elif family == "S11":
            ledger, _, child = _ledger(f"{cohort}-{family}-{seed}")
            worlds = _worlds("reverse", jitter); cert = _plan(ledger, child, worlds)
            d = select_self_falsification_attack(
                ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds,
                candidate_world_id="BASE", attacks=[_attack("a", {"CM": 1.0 + jitter})], available_budget=1000.0,
            )
            if seed % 2 == 0:
                ledger.retract("parent", reason="frozen post-selection stale mutation")
                target = "parent"
            else:
                target = "child"  # load-bearing but deliberately not targeted by attack
            before_events = len(ledger.events)
            accepted = False
            try:
                apply_self_falsification_outcome(
                    decision=d, ledger=ledger, plan_certificate=cert, context_scope=SCOPE, worlds=worlds,
                    outcome=FalsificationOutcome.FALSIFIED_MEMORY, target_id=target, reason="must fail closed",
                )
                accepted = True
            except FalsificationBindingError:
                pass
            row.update(state=d.state.value, attack_id=d.attack_id)
            row["stale_or_unbound_outcome_accepted"] = accepted
            row["passed"] = not accepted and len(ledger.events) == before_events

        else:
            raise AssertionError(f"unknown family {family}")
    except Exception as exc:  # confirmatory harness records rather than hides failures
        row["runtime_error"] = f"{type(exc).__name__}: {exc}"
        row["passed"] = False
    return row


def _generate_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cohort, base in COHORT_BASES.items():
        for family in FAMILIES:
            for offset in range(N_PER_FAMILY):
                rows.append(_case(cohort, family, base + offset))
    return rows


def _rows_hash(rows: list[dict[str, Any]]) -> str:
    raw = "\n".join(json.dumps(r, sort_keys=True, separators=(",", ":")) for r in rows).encode()
    return hashlib.sha256(raw).hexdigest()


def _aggregate(rows: list[dict[str, Any]], implementation_commit: str) -> dict[str, Any]:
    cohorts: dict[str, Any] = {}
    for cohort in COHORT_BASES:
        cr = [r for r in rows if r["cohort"] == cohort]
        families: dict[str, Any] = {}
        for family in FAMILIES:
            fr = [r for r in cr if r["family"] == family]
            families[family] = {
                "n": len(fr),
                "pass_count": sum(bool(r["passed"]) for r in fr),
                "runtime_errors": sum(r["runtime_error"] is not None for r in fr),
            }
        cohorts[cohort] = {
            "n": len(cr),
            "families": families,
            "false_spend_count": sum(bool(r["false_spend"]) for r in cr),
            "irrelevant_attack_selection_count": sum(bool(r["irrelevant_attack_selected"]) for r in cr),
            "uncertified_attack_selection_count": sum(bool(r["uncertified_attack_selected"]) for r in cr),
            "stale_plan_acceptance_count": sum(bool(r["stale_plan_accepted"]) for r in cr),
            "permutation_disagreement_count": sum(bool(r["permutation_disagreement"]) for r in cr),
            "survival_promotion_count": sum(bool(r["survival_promotion"]) for r in cr),
            "negative_target_violation_count": sum(bool(r["negative_target_violation"]) for r in cr),
            "stale_or_unbound_outcome_acceptance_count": sum(bool(r["stale_or_unbound_outcome_accepted"]) for r in cr),
            "runtime_error_count": sum(r["runtime_error"] is not None for r in cr),
            "negative_propagation_pass_count": sum(r["negative_propagation_pass"] is True for r in cr),
            "negative_propagation_evaluated_count": sum(r["negative_propagation_pass"] is not None for r in cr),
        }

    errors: list[str] = []
    for cohort, c in cohorts.items():
        for family, f in c["families"].items():
            if f["n"] != N_PER_FAMILY or f["pass_count"] != N_PER_FAMILY or f["runtime_errors"] != 0:
                errors.append(f"{cohort}:{family}: family endpoint")
        for field in (
            "false_spend_count",
            "irrelevant_attack_selection_count",
            "uncertified_attack_selection_count",
            "stale_plan_acceptance_count",
            "permutation_disagreement_count",
            "survival_promotion_count",
            "negative_target_violation_count",
            "stale_or_unbound_outcome_acceptance_count",
            "runtime_error_count",
        ):
            if c[field] != 0:
                errors.append(f"{cohort}:{field}")
        if c["negative_propagation_pass_count"] != c["negative_propagation_evaluated_count"]:
            errors.append(f"{cohort}:negative propagation")

    return {
        "experiment_id": "COG-SELF-01",
        "verdict": "AUTONOMOUS_DECISION_RELEVANT_FALSIFICATION_GOVERNOR_QUALIFIED_SYNTHETIC_NARROWED" if not errors else "COG_SELF_01_NOT_QUALIFIED",
        "scientific_pass": not errors,
        "authority": "SYNTHETIC_SELF_FALSIFICATION_SAFETY_SELECTION_PRIMITIVE_ONLY",
        "preconfirmatory_preregistration_commit": PREREG_COMMIT,
        "implementation_commit": implementation_commit,
        "n_per_family_per_cohort": N_PER_FAMILY,
        "cohort_seed_bases": COHORT_BASES,
        "alpha": 0.01,
        "target_power": 0.95,
        "robust_margin": 0.05,
        "cohorts": cohorts,
        "errors": errors,
        "runtime_policy": {
            "survival_can_promote_authority": False,
            "negative_outcome_can_only_retract_or_invalidate_bound_target": True,
            "frozen_evidence_rewrite_api_exposed": False,
            "decision_relevant_spend_only": True,
        },
        "novelty_status": "UNKNOWN_OVERLAP_CONCEDED",
        "non_promotion_boundary": {
            "semantic_causal_truth": False,
            "autonomous_scientific_discovery": False,
            "real_model_transfer": False,
            "natural_language_transfer": False,
            "production_active_control": False,
            "matched_compute_architecture_advantage": False,
            "external_independent_replication": False,
            "flagship_result_qualified": False,
        },
    }


def run(*, write: bool = False) -> dict[str, Any]:
    implementation_commit = _git_head()
    rows = _generate_rows()
    replay = _generate_rows()
    verdict = _aggregate(rows, implementation_commit)
    verdict["regeneration_hashes"] = {"generation": _rows_hash(rows), "replay": _rows_hash(replay)}
    if verdict["regeneration_hashes"]["generation"] != verdict["regeneration_hashes"]["replay"]:
        verdict["errors"].append("deterministic regeneration mismatch")
        verdict["scientific_pass"] = False
        verdict["verdict"] = "COG_SELF_01_NOT_QUALIFIED"
    if write:
        ART.mkdir(parents=True, exist_ok=True)
        RES.mkdir(parents=True, exist_ok=True)
        (ART / "results.jsonl").write_text(
            "\n".join(json.dumps(r, sort_keys=True) for r in rows) + "\n"
        )
        payload = json.dumps(verdict, indent=2, sort_keys=True) + "\n"
        (ART / "verdict.json").write_text(payload)
        (RES / "verdict.json").write_text(payload)
    return verdict


if __name__ == "__main__":
    result = run(write=True)
    print(json.dumps(result, indent=2, sort_keys=True))
    raise SystemExit(0 if result["scientific_pass"] else 1)
