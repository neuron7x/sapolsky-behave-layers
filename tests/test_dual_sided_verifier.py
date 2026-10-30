from __future__ import annotations

import json
import random
from dataclasses import replace

import pytest

from cwc.governance.planner_admission import (
    MAX_INPUT_BYTES,
    AdmissionBlocked,
    critic_planner_document,
    execute_verified_plan,
    verify_planner_document,
)
from cwc.governance.verifier_qualification import (
    VerificationDecision,
    canonical_bytes,
    digest,
    qualify_verifier,
)
from cwc.memory.epistemic_store import EpistemicMemoryLedger
from cwc.planning.proof_carrying import WorldBranch, plan_counterfactual
from scripts.dual_sided_verifier_gate import load_fixtures, mutation_controls, replay_report

FIXTURES = load_fixtures()


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda f: f.fixture_id)
def test_frozen_fixture_matches_independent_expected_decision(fixture):
    assert verify_planner_document(fixture.payload) == fixture.expected
    assert critic_planner_document(fixture.payload) == fixture.expected


def test_complete_suite_separates_artifact_decision_and_coverage():
    report = qualify_verifier(verify_planner_document, critic_planner_document, FIXTURES)
    assert report["verdict"] == "PASS"
    assert report["artifact_quality"] == report["decision_correctness"] == report["execution_integrity"] == "PASS"
    assert report["coverage"] == {"complete": True, "errors": [], "fixture_count": 20, "valid_variants": 3}
    assert report["product_qualified"] is False
    payload = {key: value for key, value in report.items() if key != "evidence_sha256"}
    assert digest(canonical_bytes(payload)) == report["evidence_sha256"]


def test_all_curated_failure_modes_are_killed():
    assert mutation_controls(FIXTURES) == {
        "reject_all": True,
        "accept_all": True,
        "contradiction_to_submit": True,
        "crashed_verifier": True,
    }


@pytest.mark.parametrize("omitted", sorted({f.category for f in FIXTURES}))
def test_missing_coverage_cannot_pass(omitted):
    fixtures = tuple(f for f in FIXTURES if f.category != omitted)
    report = qualify_verifier(verify_planner_document, critic_planner_document, fixtures)
    assert report["coverage"]["complete"] is False
    assert report["verdict"] == "FAIL"


def test_zero_tests_duplicate_ids_duplicate_inputs_and_two_variants_fail():
    for fixtures in (
        (),
        (*FIXTURES, FIXTURES[0]),
        FIXTURES[1:],
        tuple(f for f in FIXTURES if f.fixture_id != "variant-reordered"),
    ):
        assert qualify_verifier(verify_planner_document, critic_planner_document, fixtures)["verdict"] == "FAIL"


def test_variants_must_preserve_canonical_expected_action():
    fixtures = tuple(
        replace(f, expected=VerificationDecision("PASS", "SUBMIT", "B")) if f.category == "VALID_VARIANT" else f
        for f in FIXTURES
    )
    report = qualify_verifier(verify_planner_document, critic_planner_document, fixtures)
    assert "VARIANT_EXPECTATION_DIFFERS_FROM_CANONICAL" in report["coverage"]["errors"]


@pytest.mark.parametrize(
    "category,expected,error",
    [
        ("CANONICAL_VALID", VerificationDecision("FAIL", "STOP"), "POSITIVE_FIXTURE_NOT_EXECUTABLE"),
        ("INVALID", VerificationDecision("PASS", "STOP"), "INVALID_MUST_REJECT_AND_STOP"),
        ("ATTACK", VerificationDecision("UNKNOWN", "UNRESOLVED"), "ATTACK_MUST_REJECT_AND_STOP"),
        ("CONTRADICTION", VerificationDecision("PASS", "SUBMIT", "A"), "CONTRADICTION_MUST_STOP_OR_ESCALATE"),
        ("UNKNOWN", VerificationDecision("FAIL", "STOP"), "UNKNOWN_MUST_REMAIN_UNRESOLVED"),
    ],
)
def test_mislabeled_oracle_cannot_make_a_coverage_claim(category, expected, error):
    fixtures = tuple(replace(f, expected=expected) if f.category == category else f for f in FIXTURES)
    report = qualify_verifier(verify_planner_document, critic_planner_document, fixtures)
    assert error in report["coverage"]["errors"]
    assert report["verdict"] == "FAIL"


def test_truthy_return_is_not_rejection_evidence():
    report = qualify_verifier(lambda _: True, critic_planner_document, FIXTURES)
    assert report["execution_integrity"] == report["verdict"] == "FAIL"
    assert all(row["errors"] == ["verifier:TypeError"] for row in report["rows"])


@pytest.mark.parametrize(
    "quality,action,selected",
    [
        ("invalid", "STOP", None),
        ("PASS", "invalid", None),
        ("FAIL", "SUBMIT", "A"),
        ("PASS", "SUBMIT", None),
        ("PASS", "SUBMIT", ""),
        ("PASS", "SUBMIT", " "),
        ("PASS", "STOP", "A"),
    ],
)
def test_invalid_decision_cannot_carry_execution(quality, action, selected):
    with pytest.raises(ValueError):
        VerificationDecision(quality, action, selected)


def test_expected_labels_are_never_supplied_to_candidate():
    seen = []

    def verifier(raw):
        assert type(raw) is bytes
        seen.append(raw)
        return verify_planner_document(raw)

    assert qualify_verifier(verifier, critic_planner_document, FIXTURES)["verdict"] == "PASS"
    assert seen == [f.payload for f in FIXTURES]


def test_hash_change_and_false_qualification_cannot_hide_in_same_receipt():
    original = qualify_verifier(verify_planner_document, critic_planner_document, FIXTURES)
    changed = (replace(FIXTURES[0], payload=FIXTURES[0].payload + b" "), *FIXTURES[1:])
    rerun = qualify_verifier(verify_planner_document, critic_planner_document, changed)
    assert rerun["verdict"] == "PASS"  # legal formatting is not a semantic failure
    assert rerun["suite_sha256"] != original["suite_sha256"]
    assert rerun["evidence_sha256"] != original["evidence_sha256"]


@pytest.mark.parametrize("fixture", FIXTURES, ids=lambda f: f.fixture_id)
def test_executor_is_called_once_only_for_agreed_submit(fixture):
    calls = []

    def executor(action):
        calls.append(action)
        return "executed"

    if fixture.expected.action == "SUBMIT":
        assert (
            execute_verified_plan(fixture.payload, expected_input_sha256=digest(fixture.payload), executor=executor)
            == "executed"
        )
        assert calls == [fixture.expected.selected_action]
    else:
        with pytest.raises(AdmissionBlocked):
            execute_verified_plan(fixture.payload, expected_input_sha256=digest(fixture.payload), executor=executor)
        assert calls == []


def test_mutated_request_never_reuses_old_hash():
    raw = FIXTURES[0].payload
    calls = []
    with pytest.raises(AdmissionBlocked, match="frozen input digest"):
        execute_verified_plan(raw + b" ", expected_input_sha256=digest(raw), executor=calls.append)
    assert calls == []


def test_critic_disagreement_blocks_executor(monkeypatch):
    monkeypatch.setattr(
        "cwc.governance.planner_admission.critic_planner_document", lambda _: VerificationDecision("FAIL", "STOP")
    )
    raw = FIXTURES[0].payload
    calls = []
    with pytest.raises(AdmissionBlocked):
        execute_verified_plan(raw, expected_input_sha256=digest(raw), executor=calls.append)
    assert calls == []


@pytest.mark.parametrize("raw", [b"", b"\xff", b"[]", b"null", b"x" * (MAX_INPUT_BYTES + 1), b"[" * 2000])
def test_malformed_and_unbounded_input_stops(raw):
    assert verify_planner_document(raw) == critic_planner_document(raw) == VerificationDecision("FAIL", "STOP")


@pytest.mark.parametrize(
    "mutation",
    [
        lambda d: d.update(schema=42),
        lambda d: d.update(context_scope=[]),
        lambda d: d.update(context_scope=["CTX", "CTX"]),
        lambda d: d.update(worlds=[]),
        lambda d: d["worlds"][0].update(extra=True),
        lambda d: d["worlds"][0].update(world_id=""),
        lambda d: d["worlds"][1].update(world_id="BASE"),
        lambda d: d["worlds"][0].update(utilities={"A": 1}),
        lambda d: d["worlds"][0]["utilities"].update(A=True),
        lambda d: d["worlds"][0]["utilities"].update(C=0),
        lambda d: d["certificate"].update(robust_margin=0.0),
        lambda d: d["certificate"].update(plan_id=""),
        lambda d: d["certificate"].update(certificate_digest="0" * 64),
        lambda d: d["certificate"].update(context_scope=["OTHER"]),
        lambda d: d["certificate"].pop("memory_bindings"),
        lambda d: d["certificate"].update(unexpected=True),
    ],
)
def test_malformed_shape_and_forged_bindings_reject(mutation):
    doc = json.loads(FIXTURES[0].payload)
    mutation(doc)
    raw = canonical_bytes(doc)
    assert verify_planner_document(raw) == critic_planner_document(raw) == VerificationDecision("FAIL", "STOP")


def test_replay_is_exact_across_two_hash_seeds():
    report = replay_report()
    assert report["verdict"] == "PASS"
    assert report["replay"] == {"process_count": 2, "python_hash_seeds": ["1", "947"], "matched": True}


def test_pairwise_critic_matches_native_on_fresh_finite_panels():
    # New, deterministic panels exercise non-A winners, ties, action insertion
    # order, three actions, several worlds, and both sides of the margin.
    rng = random.Random(30102026)
    states = set()
    for index in range(300):
        actions = list("ABC")
        rng.shuffle(actions)
        worlds = [
            WorldBranch(f"W{i}", {a: rng.randrange(-8, 9) / 8 for a in actions}, "test")
            for i in range(rng.randrange(1, 5))
        ]
        result = plan_counterfactual(
            ledger=EpistemicMemoryLedger(),
            plan_id=f"fresh-{index}",
            context_scope=("CTX",),
            required_memories=(),
            worlds=worlds,
            robust_margin=0.25,
        )
        doc = {
            "schema": "CWC_MEMORY_FREE_PLAN_ADMISSION_V1",
            "context_scope": ["CTX"],
            "worlds": [
                {"world_id": w.world_id, "utilities": dict(w.utilities), "provenance": w.provenance} for w in worlds
            ],
            "certificate": {
                **result.certificate.payload(),
                "certificate_digest": result.certificate.certificate_digest,
            },
        }
        raw = canonical_bytes(doc)
        native, critic = verify_planner_document(raw), critic_planner_document(raw)
        assert native == critic
        assert native.artifact_quality == "PASS"
        states.add(native.action)
    assert states == {"SUBMIT", "STOP", "ESCALATE"}


def test_native_binary64_normalization_is_part_of_the_boundary():
    world = WorldBranch("BASE", {"A": 2**53, "B": 2**53 + 1}, "test")
    result = plan_counterfactual(
        ledger=EpistemicMemoryLedger(),
        plan_id="binary64",
        context_scope=("CTX",),
        required_memories=(),
        worlds=[world],
        robust_margin=1.0,
    )
    doc = {
        "schema": "CWC_MEMORY_FREE_PLAN_ADMISSION_V1",
        "context_scope": ["CTX"],
        "worlds": [{"world_id": "BASE", "utilities": {"A": 2**53, "B": 2**53 + 1}, "provenance": "test"}],
        "certificate": {**result.certificate.payload(), "certificate_digest": result.certificate.certificate_digest},
    }
    assert (
        verify_planner_document(canonical_bytes(doc))
        == critic_planner_document(canonical_bytes(doc))
        == VerificationDecision("PASS", "STOP")
    )


def test_integer_margin_cannot_masquerade_as_native_float_certificate():
    doc = json.loads(FIXTURES[0].payload)
    doc["certificate"]["robust_margin"] = 1
    doc["certificate"].pop("certificate_digest")
    doc["certificate"]["certificate_digest"] = digest(canonical_bytes(doc["certificate"]))
    assert critic_planner_document(canonical_bytes(doc)) == VerificationDecision("FAIL", "STOP")
