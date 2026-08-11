from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import time

from cwc.epistemics.lattice import (
    EpistemicMachine,
    EpistemicRecord,
    EpistemicState,
    EvidenceKind,
    EvidenceRef,
    EvidenceSource,
)
from cwc.memory.epistemic_store import EpistemicMemoryLedger, MemoryRecord, MemoryStatus


ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts/cog-memory-01"
RESULT = ROOT / "research/results/COG-MEMORY-01"
COHORTS = {"PRIMARY": 82001, "REPLICATION": 92001}
N = 128
FAMILIES = tuple(f"M{i}" for i in range(12))
UNSAFE_CAUSAL_FAMILIES = {"M0", "M1", "M2", "M3", "M5", "M6", "M7", "M8", "M9", "M10"}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _ev(label: str, kind: EvidenceKind, source: EvidenceSource, scope: tuple[str, ...]) -> EvidenceRef:
    return EvidenceRef(
        ref=f"mem://{label}",
        sha256=_sha(label),
        kind=kind,
        source=source,
        context_scope=scope,
        provenance="COG-MEMORY-01 confirmatory harness",
    )


def _chain(claim: str, scope: tuple[str, ...], assumptions=("A_SHARED",)) -> tuple[EpistemicMachine, EpistemicRecord, EpistemicRecord, EpistemicRecord, EpistemicRecord]:
    m = EpistemicMachine()
    o = m.observe(
        claim_id=claim,
        context_scope=scope,
        evidence=[_ev(claim+":f", EvidenceKind.FACTUAL_OBSERVATION, EvidenceSource.FACTUAL_CHANNEL, scope)],
    )
    p = m.transition(
        o,
        m.issue_predictive_capability(
            o,
            evidence=[_ev(claim+":p", EvidenceKind.PREDICTIVE_VALIDATION, EvidenceSource.HELD_OUT_PREDICTION, scope)],
        ),
    )
    a = m.transition(
        p,
        m.issue_assumption_capability(
            p,
            assumption_ids=assumptions,
            evidence=[_ev(claim+":a", EvidenceKind.IDENTIFYING_ASSUMPTION, EvidenceSource.ASSUMPTION_CONTRACT, scope)],
        ),
    )
    i = m.transition(
        a,
        m.issue_intervention_capability(
            a,
            operator_id="do(X)",
            evidence=[_ev(claim+":i", EvidenceKind.DIRECT_INTERVENTION, EvidenceSource.DIRECT_SYSTEM_REEXECUTION, scope)],
        ),
    )
    return m, o, p, a, i


def _terminal(m: EpistemicMachine, p: EpistemicRecord, state: EpistemicState, claim: str, scope: tuple[str, ...]) -> EpistemicRecord:
    if state is EpistemicState.UNIDENTIFIED:
        ev = _ev(claim+":u", EvidenceKind.COUNTERMODEL, EvidenceSource.COUNTERMODEL_SEARCH, scope)
    elif state is EpistemicState.FALSIFIED:
        ev = _ev(claim+":fals", EvidenceKind.FALSIFICATION, EvidenceSource.DIAGNOSTIC, scope)
    elif state is EpistemicState.OOD:
        ev = _ev(claim+":ood", EvidenceKind.OOD_DIAGNOSTIC, EvidenceSource.DIAGNOSTIC, scope)
    elif state is EpistemicState.ABSTAIN:
        ev = _ev(claim+":abs", EvidenceKind.ABSTENTION_REASON, EvidenceSource.DIAGNOSTIC, scope)
    else:
        raise AssertionError(state)
    return m.transition(p, m.issue_terminal_capability(p, target_state=state, evidence=[ev], reason="terminal harness state"))


def _case(cohort: str, seed_base: int, family: str, i: int) -> dict[str, object]:
    claim = f"COG-MEMORY-01:{cohort}:{family}:{seed_base+i}"
    scope = (f"CTX:{cohort}:{family}:{i:03d}",)
    m, o, p, a, inter = _chain(claim, scope)
    ledger = EpistemicMemoryLedger()
    ok = False
    detail = ""
    false_causal = False
    retraction_ok: bool | None = None
    legacy_injection_accepted: bool | None = None
    tampered_binding_accepted: bool | None = None

    if family == "M0":
        rec = ledger.consolidate(memory_id="m0", epistemic_record=o)
        ok = rec.status is MemoryStatus.ACTIVE and not rec.causal_consolidated
        false_causal = rec.causal_consolidated
        detail = rec.status.value
    elif family == "M1":
        rec = ledger.consolidate(memory_id="m1", epistemic_record=p)
        ok = rec.status is MemoryStatus.ACTIVE and not rec.causal_consolidated
        false_causal = rec.causal_consolidated
        detail = rec.status.value
    elif family == "M2":
        rec = ledger.consolidate(memory_id="m2", epistemic_record=a)
        ok = rec.status is MemoryStatus.QUARANTINED and not rec.causal_consolidated
        false_causal = rec.causal_consolidated
        detail = rec.status.value
    elif family == "M3":
        rec = ledger.consolidate(memory_id="m3", epistemic_record=a, countermodel_ids=("CM-1", "CM-2"))
        ok = rec.status is MemoryStatus.QUARANTINED and not rec.causal_consolidated and len(rec.countermodel_ids) == 2
        false_causal = rec.causal_consolidated
        detail = rec.status.value
    elif family == "M4":
        rec = ledger.consolidate(memory_id="m4", epistemic_record=inter)
        ok = rec.status is MemoryStatus.ACTIVE and rec.causal_consolidated and not rec.countermodel_ids
        detail = rec.status.value
    elif family == "M5":
        rec = ledger.consolidate(memory_id="m5", epistemic_record=inter, countermodel_ids=("CM-SURVIVES",))
        ok = rec.status is MemoryStatus.QUARANTINED and not rec.causal_consolidated
        false_causal = rec.causal_consolidated
        detail = rec.status.value
    elif family == "M6":
        state = (EpistemicState.UNIDENTIFIED, EpistemicState.FALSIFIED, EpistemicState.OOD, EpistemicState.ABSTAIN)[i % 4]
        term = _terminal(m, p, state, claim, scope)
        rec = ledger.consolidate(memory_id="m6", epistemic_record=term)
        ok = rec.status is MemoryStatus.RETRACTED and not rec.causal_consolidated
        false_causal = rec.causal_consolidated
        detail = state.value
    elif family == "M7":
        ledger.consolidate(memory_id="root", epistemic_record=inter)
        ledger.consolidate(memory_id="child", epistemic_record=inter, dependency_ids=("root",))
        ledger.consolidate(memory_id="grand", epistemic_record=inter, dependency_ids=("child",))
        changed = set(ledger.retract("root", reason="root invalidated"))
        retraction_ok = changed == {"root", "child", "grand"} and all(ledger.record(x).status is MemoryStatus.RETRACTED for x in changed)
        false_causal = any(ledger.record(x).causal_consolidated for x in ("root", "child", "grand"))
        ok = bool(retraction_ok) and not false_causal
        detail = ",".join(sorted(changed))
    elif family == "M8":
        ledger.consolidate(memory_id="root", epistemic_record=inter)
        ledger.consolidate(memory_id="d1", epistemic_record=inter, dependency_ids=("root",))
        ledger.consolidate(memory_id="d2", epistemic_record=inter, dependency_ids=("root",))
        changed = set(ledger.invalidate_assumption("A_SHARED", reason="assumption falsified"))
        retraction_ok = changed == {"root", "d1", "d2"} and all(ledger.record(x).status is MemoryStatus.RETRACTED for x in changed)
        false_causal = any(ledger.record(x).causal_consolidated for x in ("root", "d1", "d2"))
        ok = bool(retraction_ok) and not false_causal
        detail = ",".join(sorted(changed))
    elif family == "M9":
        ledger.consolidate(memory_id="bind", epistemic_record=inter)
        tampered_binding_accepted = ledger.verify_binding("bind", p)
        direct_construct_accepted = False
        try:
            MemoryRecord()  # type: ignore[call-arg]
            direct_construct_accepted = True
        except TypeError:
            pass
        ok = not tampered_binding_accepted and not direct_construct_accepted
        false_causal = False
        detail = f"tampered={tampered_binding_accepted},direct={direct_construct_accepted}"
    elif family == "M10":
        legacy_injection_accepted = False
        try:
            ledger.consolidate(memory_id="legacy", epistemic_record="INTERVENTION_SUPPORTED")  # type: ignore[arg-type]
            legacy_injection_accepted = True
        except TypeError:
            pass
        ok = not legacy_injection_accepted
        false_causal = legacy_injection_accepted
        detail = f"legacy_accepted={legacy_injection_accepted}"
    elif family == "M11":
        old = ledger.consolidate(memory_id="old", epistemic_record=p)
        old_digest = old.memory_digest
        new = ledger.consolidate(memory_id="new", epistemic_record=inter, revision_of="old")
        old_now = ledger.record("old")
        ok = (
            old_now.memory_digest == old_digest
            and old_now.epistemic_state is EpistemicState.PREDICTIVE
            and not old_now.causal_consolidated
            and new.causal_consolidated
            and new.revision_of == "old"
        )
        false_causal = old_now.causal_consolidated
        detail = f"old={old_now.epistemic_state.value},new={new.epistemic_state.value}"
    else:
        raise AssertionError(family)

    try:
        ledger.assert_invariants()
        invariant_ok = True
    except Exception as exc:
        invariant_ok = False
        detail += f" invariant_error={type(exc).__name__}:{exc}"
    event_chain_ok = ledger.event_chain_valid()
    ok = bool(ok and invariant_ok and event_chain_ok)
    return {
        "cohort": cohort,
        "family": family,
        "case": i,
        "pass": int(ok),
        "false_causal_consolidation": int(false_causal),
        "retraction_ok": "" if retraction_ok is None else int(retraction_ok),
        "legacy_injection_accepted": "" if legacy_injection_accepted is None else int(legacy_injection_accepted),
        "tampered_binding_accepted": "" if tampered_binding_accepted is None else int(tampered_binding_accepted),
        "event_chain_ok": int(event_chain_ok),
        "invariant_ok": int(invariant_ok),
        "detail": detail,
    }


def run() -> dict[str, object]:
    started = time.perf_counter()
    rows: list[dict[str, object]] = []
    cohorts: dict[str, object] = {}
    errors: list[str] = []
    for cohort, base in COHORTS.items():
        fams: dict[str, object] = {}
        for family in FAMILIES:
            rr = [_case(cohort, base, family, i) for i in range(N)]
            rows.extend(rr)
            pass_count = sum(int(r["pass"]) for r in rr)
            false_causal = sum(int(r["false_causal_consolidation"]) for r in rr)
            chain_fail = sum(1-int(r["event_chain_ok"]) for r in rr)
            inv_fail = sum(1-int(r["invariant_ok"]) for r in rr)
            retractions = [int(r["retraction_ok"]) for r in rr if r["retraction_ok"] != ""]
            legacy = [int(r["legacy_injection_accepted"]) for r in rr if r["legacy_injection_accepted"] != ""]
            tamper = [int(r["tampered_binding_accepted"]) for r in rr if r["tampered_binding_accepted"] != ""]
            fs = {
                "n": N,
                "pass_count": pass_count,
                "pass_rate": pass_count/N,
                "false_causal_consolidation_count": false_causal,
                "event_chain_failure_count": chain_fail,
                "invariant_failure_count": inv_fail,
                "required_transitive_retraction_rate": None if not retractions else sum(retractions)/len(retractions),
                "legacy_string_injection_acceptance_rate": None if not legacy else sum(legacy)/len(legacy),
                "tampered_binding_acceptance_rate": None if not tamper else sum(tamper)/len(tamper),
            }
            fams[family] = fs
            if pass_count != N:
                errors.append(f"{cohort}:{family}: family pass {pass_count}/{N}")
            if family in UNSAFE_CAUSAL_FAMILIES and false_causal != 0:
                errors.append(f"{cohort}:{family}: false causal consolidation {false_causal}")
            if chain_fail or inv_fail:
                errors.append(f"{cohort}:{family}: ledger invariant/hash-chain failure")
        cohorts[cohort] = {"seed_base": base, "families": fams}

    scientific_pass = not errors
    return {
        "experiment_id": "COG-MEMORY-01",
        "preconfirmatory_preregistration_commit": "6746ab022fa8cda066ebfe66bcca4634d6881973",
        "verdict": "ASSUMPTION_AWARE_MEMORY_CONSOLIDATION_QUALIFIED_SYNTHETIC_NARROWED" if scientific_pass else "ASSUMPTION_AWARE_MEMORY_CONSOLIDATION_NOT_QUALIFIED",
        "scientific_pass": scientific_pass,
        "authority": "EPISTEMIC_MEMORY_PRIMITIVE_ONLY" if scientific_pass else "NO_PROMOTION",
        "cases_per_family_per_cohort": N,
        "cohorts": cohorts,
        "errors": errors,
        "memory_policy": {
            "observed_predictive_are_causal": False,
            "assumption_conditional_causal_consolidation_allowed": False,
            "intervention_supported_requires_empty_countermodel_set": True,
            "terminal_states_can_create_active_causal_memory": False,
            "transitive_dependency_retraction_required": True,
            "assumption_invalidation_retraction_required": True,
            "legacy_string_authority_allowed": False,
            "in_place_authority_upgrade_allowed": False,
        },
        "non_promotion_boundary": {
            "semantic_causality": False,
            "planning_value": False,
            "replay_control": False,
            "active_control": False,
            "autonomous_self_modification": False,
            "architecture_promotion": False,
        },
        "wall_seconds": time.perf_counter()-started,
        "rows": rows,
    }


def main() -> int:
    ART.mkdir(parents=True, exist_ok=True)
    RESULT.mkdir(parents=True, exist_ok=True)
    payload=run(); rows=payload.pop("rows")
    data=(json.dumps(payload,indent=2,sort_keys=True)+"\n").encode()
    (ART/"verdict.json").write_bytes(data); (RESULT/"verdict.json").write_bytes(data)
    fields=("cohort","family","case","pass","false_causal_consolidation","retraction_ok","legacy_injection_accepted","tampered_binding_accepted","event_chain_ok","invariant_ok","detail")
    with (ART/"memory_matrix.csv").open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
    sums=[]
    for name in ("verdict.json","memory_matrix.csv"):
        p=ART/name; sums.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {name}")
    (ART/"SHA256SUMS").write_text("\n".join(sums)+"\n")
    print(json.dumps(payload,indent=2,sort_keys=True))
    return 0 if payload["scientific_pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
