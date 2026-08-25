from __future__ import annotations

from pathlib import Path

import pytest

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes
from cwc.governance.p19_external_verification_contract import (
    CHECK_METHOD_IDS,
    REGRESSION_TEST_FILES,
    VERIFIER_ENTRYPOINT,
    VERIFIER_RUNTIME_DEPENDENCIES,
    CANONICAL_REGRESSION_COMMAND,
)
from cwc.governance.p19_external_verification_plan import (
    PLAN_GENERATION,
    SCHEMA,
    P19ExternalVerificationPlanError,
    build_activated_p19_external_verification_plan_document,
    build_inactive_p19_external_verification_plan_document,
    load_p19_external_verification_plan,
)
from cwc.governance.p19_external_verifier_regression import (
    build_p19_external_verifier_regression_receipt,
)
from cwc.governance.p19_verification_check_receipt import REQUIRED_CHECKS


PAYLOAD_KEYS = (
    "plan_generation", "frozen_pre_outcome", "activation_authorized",
    "verifier_entrypoint_path", "verifier_entrypoint_sha256",
    "verifier_dependency_manifest_digest", "verifier_dependencies", "check_contracts",
    "all_check_implementations_complete", "activation_regression_receipt_path",
    "activation_regression_receipt_sha256", "activation_regression_receipt_digest",
    "activation_regression_source_commit", "activation_regression_source_tree",
    "activation_regression_test_manifest_digest", "product_qualification_authorized",
)


def _runtime_and_tests(root: Path) -> None:
    entry = root / VERIFIER_ENTRYPOINT
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text("print('verifier')\n", encoding="utf-8")
    for rel in VERIFIER_RUNTIME_DEPENDENCIES:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# frozen dependency: {rel}\n", encoding="utf-8")
    for rel in REGRESSION_TEST_FILES:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# frozen regression test: {rel}\n", encoding="utf-8")


def _write(path: Path, doc: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(doc) + b"\n")


def _redigest(doc: dict[str, object]) -> None:
    doc["plan_digest"] = sha256_bytes(canonical_json_bytes({key: doc[key] for key in PAYLOAD_KEYS}))


def _regression_receipt(root: Path) -> Path:
    stdout = root / "evidence/regression/stdout.bin"
    stderr = root / "evidence/regression/stderr.bin"
    stdout.parent.mkdir(parents=True, exist_ok=True)
    stdout.write_bytes(b"42 passed in 1.23s\n")
    stderr.write_bytes(b"")
    receipt = build_p19_external_verifier_regression_receipt(
        repository_root=root,
        source_commit="1" * 40,
        source_tree="2" * 40,
        command_argv=CANONICAL_REGRESSION_COMMAND,
        stdout_path=stdout.relative_to(root),
        stderr_path=stderr.relative_to(root),
        exit_code=0,
    )
    path = root / "evidence/regression/receipt.json"
    _write(path, receipt.document)
    return path


def _inactive_doc(root: Path) -> dict[str, object]:
    _runtime_and_tests(root)
    return build_inactive_p19_external_verification_plan_document(
        repository_root=root,
        implemented_check_ids=tuple(sorted(REQUIRED_CHECKS)),
    )


def _active_doc(root: Path) -> dict[str, object]:
    _runtime_and_tests(root)
    receipt = _regression_receipt(root)
    return build_activated_p19_external_verification_plan_document(
        repository_root=root,
        regression_receipt_path=receipt.relative_to(root),
    )


def test_inactive_builder_content_addresses_exact_implemented_surface(tmp_path: Path):
    document = _inactive_doc(tmp_path)
    assert document["schema"] == SCHEMA
    assert document["plan_generation"] == PLAN_GENERATION
    assert document["activation_authorized"] is False
    assert document["all_check_implementations_complete"] is True
    assert document["product_qualification_authorized"] is False
    assert {row["method_id"] for row in document["check_contracts"]} == set(CHECK_METHOD_IDS.values())
    for field in (
        "activation_regression_receipt_path", "activation_regression_receipt_sha256",
        "activation_regression_receipt_digest", "activation_regression_source_commit",
        "activation_regression_source_tree", "activation_regression_test_manifest_digest",
    ):
        assert document[field] is None
    path = tmp_path / "plan.json"
    _write(path, document)
    loaded = load_p19_external_verification_plan(path, repository_root=tmp_path, require_active=False)
    assert loaded.plan_digest == document["plan_digest"]
    assert loaded.activation_authorized is False
    with pytest.raises(P19ExternalVerificationPlanError, match="not activated"):
        load_p19_external_verification_plan(path, repository_root=tmp_path, require_active=True)


def test_inactive_builder_rejects_incomplete_or_duplicate_handler_population(tmp_path: Path):
    _runtime_and_tests(tmp_path)
    missing = tuple(sorted(REQUIRED_CHECKS - {"P19_SEAL_REBUILD"}))
    with pytest.raises(P19ExternalVerificationPlanError, match="exact unique implemented check population"):
        build_inactive_p19_external_verification_plan_document(
            repository_root=tmp_path,
            implemented_check_ids=missing,
        )
    duplicate = tuple(sorted(REQUIRED_CHECKS)) + ("REPOSITORY_IDENTITY",)
    with pytest.raises(P19ExternalVerificationPlanError, match="exact unique implemented check population"):
        build_inactive_p19_external_verification_plan_document(
            repository_root=tmp_path,
            implemented_check_ids=duplicate,
        )


def test_active_complete_plan_requires_and_replays_regression_receipt(tmp_path: Path):
    path = tmp_path / "plan.json"
    doc = _active_doc(tmp_path)
    _write(path, doc)
    plan = load_p19_external_verification_plan(path, repository_root=tmp_path)
    assert plan.activation_authorized is True
    assert plan.all_check_implementations_complete is True
    assert plan.activation_regression_receipt_digest
    assert plan.activation_regression_test_manifest_digest
    assert plan.plan_digest == doc["plan_digest"]


def test_forged_active_flag_without_regression_receipt_fails_closed(tmp_path: Path):
    path = tmp_path / "plan.json"
    doc = _inactive_doc(tmp_path)
    doc["activation_authorized"] = True
    _redigest(doc)
    _write(path, doc)
    with pytest.raises(P19ExternalVerificationPlanError):
        load_p19_external_verification_plan(path, repository_root=tmp_path)


def test_inactive_plan_cannot_carry_dormant_activation_evidence(tmp_path: Path):
    path = tmp_path / "plan.json"
    doc = _inactive_doc(tmp_path)
    doc["activation_regression_receipt_path"] = "evidence/forged.json"
    _redigest(doc)
    _write(path, doc)
    with pytest.raises(P19ExternalVerificationPlanError, match="cannot carry activation regression evidence"):
        load_p19_external_verification_plan(path, repository_root=tmp_path, require_active=False)


def test_plan_generation_substitution_fails_even_with_rehashed_plan(tmp_path: Path):
    path = tmp_path / "plan.json"
    doc = _inactive_doc(tmp_path)
    doc["plan_generation"] = "POST_OUTCOME_RELABELED_PLAN"
    _redigest(doc)
    _write(path, doc)
    with pytest.raises(P19ExternalVerificationPlanError, match="generation mismatch"):
        load_p19_external_verification_plan(path, repository_root=tmp_path, require_active=False)


def test_verifier_runtime_mutation_invalidates_active_regression(tmp_path: Path):
    path = tmp_path / "plan.json"
    doc = _active_doc(tmp_path)
    _write(path, doc)
    (tmp_path / VERIFIER_ENTRYPOINT).write_text("print('mutated')\n", encoding="utf-8")
    with pytest.raises(P19ExternalVerificationPlanError, match="entrypoint bytes differ"):
        load_p19_external_verification_plan(path, repository_root=tmp_path)


def test_regression_test_mutation_invalidates_active_plan(tmp_path: Path):
    path = tmp_path / "plan.json"
    doc = _active_doc(tmp_path)
    _write(path, doc)
    (tmp_path / REGRESSION_TEST_FILES[0]).write_text("# post-regression mutation\n", encoding="utf-8")
    with pytest.raises(P19ExternalVerificationPlanError, match="receipt replay failed"):
        load_p19_external_verification_plan(path, repository_root=tmp_path)


def test_regression_transcript_mutation_invalidates_active_plan(tmp_path: Path):
    path = tmp_path / "plan.json"
    doc = _active_doc(tmp_path)
    _write(path, doc)
    receipt_path = tmp_path / str(doc["activation_regression_receipt_path"])
    import json
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    stdout = tmp_path / str(receipt["stdout_path"])
    stdout.write_bytes(b"forged pass transcript\n")
    with pytest.raises(P19ExternalVerificationPlanError, match="receipt replay failed"):
        load_p19_external_verification_plan(path, repository_root=tmp_path)


def test_method_identity_substitution_fails_even_with_rehashed_plan(tmp_path: Path):
    path = tmp_path / "plan.json"
    doc = _inactive_doc(tmp_path)
    seal = next(row for row in doc["check_contracts"] if row["check_id"] == "P19_SEAL_REBUILD")
    seal["method_id"] = "DGC_P19_EXTERNAL_SEAL_REBUILD_V1"
    _redigest(doc)
    _write(path, doc)
    with pytest.raises(P19ExternalVerificationPlanError, match="method identity mismatch: P19_SEAL_REBUILD"):
        load_p19_external_verification_plan(path, repository_root=tmp_path, require_active=False)


def test_command_template_substitution_fails_even_with_rehashed_plan(tmp_path: Path):
    path = tmp_path / "plan.json"
    doc = _inactive_doc(tmp_path)
    doc["check_contracts"][0]["command_template"] = ["echo", "PASS"]
    _redigest(doc)
    _write(path, doc)
    with pytest.raises(P19ExternalVerificationPlanError, match="command template mismatch"):
        load_p19_external_verification_plan(path, repository_root=tmp_path, require_active=False)
